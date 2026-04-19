"""
Phase 4 tests — A/B hook variants + virality scoring.
Run with: pytest tests/test_phase4.py -v
"""

import pytest


class TestHookClassifier:
    def test_question_hook(self):
        from src.hooks.classifier import classify_hook
        assert classify_hook("Are we ready for AI to take over?") == "question"

    def test_statistic_hook(self):
        from src.hooks.classifier import classify_hook
        assert classify_hook("72% of engineers now use AI daily") == "statistic"

    def test_contrarian_hook(self):
        from src.hooks.classifier import classify_hook
        assert classify_hook("Everything you know about RAG is wrong") == "contrarian"

    def test_personal_story_hook(self):
        from src.hooks.classifier import classify_hook
        assert classify_hook("I spent 4 months building a pipeline. Then deleted it.") == "personal_story"

    def test_prediction_hook(self):
        from src.hooks.classifier import classify_hook
        assert classify_hook("By 2027, most SaaS products will ship AI features") == "prediction"

    def test_empty_hook(self):
        from src.hooks.classifier import classify_hook
        assert classify_hook("") == "general"


class TestHookScorer:
    def test_strong_contrarian_hook(self):
        from src.scorer.hook_scorer import score_hook
        score = score_hook("Everything you know about microservices is wrong")
        assert score >= 70

    def test_weak_generic_hook(self):
        from src.scorer.hook_scorer import score_hook
        score = score_hook("I'm excited to share some thoughts on AI")
        assert score < 50

    def test_hook_with_stat(self):
        from src.scorer.hook_scorer import score_hook
        score = score_hook("€54k in 13 hours — one API key mistake")
        assert score >= 70

    def test_empty_hook(self):
        from src.scorer.hook_scorer import score_hook
        assert score_hook("") == 20


class TestFormatScorer:
    def test_well_formatted_post(self):
        from src.scorer.format_scorer import score_format
        post = (
            "Strong opening line here.\n\n"
            "Short paragraph one. Just two sentences.\n\n"
            "Another short paragraph. Gets to the point.\n\n"
            "A single punchy line.\n\n"
            "Final thought with a question?\n\n"
            "#AI #Software"
        )
        score = score_format(post, ["#AI", "#Software"])
        assert score >= 60

    def test_wall_of_text(self):
        from src.scorer.format_scorer import score_format
        post = "This is a very long paragraph " * 30
        score = score_format(post)
        assert score < 50

    def test_too_short(self):
        from src.scorer.format_scorer import score_format
        score = score_format("Hi.")
        assert score < 40


class TestEngagementScorer:
    def test_strong_cta(self):
        from src.scorer.engagement_scorer import score_engagement
        post = (
            "Great insight about AI.\n\n"
            "What's your take on this? Share your experience below."
        )
        score = score_engagement(post)
        assert score >= 55

    def test_no_question(self):
        from src.scorer.engagement_scorer import score_engagement
        post = "Just stating facts about AI. No question. No CTA. The end."
        score = score_engagement(post)
        assert score < 45

    def test_hot_take_bonus(self):
        from src.scorer.engagement_scorer import score_engagement
        post = "Hot take: AI will replace 80% of coding. Agree or disagree?"
        score = score_engagement(post)
        assert score >= 60


class TestViralityEngine:
    def test_full_scoring(self):
        from src.scorer.engine import score_post
        result = score_post(
            post_text=(
                "Everything you know about RAG is wrong.\n\n"
                "Here's the thing: most teams build RAG pipelines "
                "that actually make accuracy worse.\n\n"
                "The real problem isn't retrieval — it's chunking.\n\n"
                "What's your experience with RAG accuracy?"
            ),
            hook_line="Everything you know about RAG is wrong.",
            hashtags=["#AI", "#RAG"],
            critic_score=7.5,
            trend_momentum=0.8,
            trend_phase="EMERGING",
        )
        assert 0 <= result.overall_pct <= 100
        assert result.tier in ("EXCELLENT", "GOOD", "AVERAGE", "WEAK")
        assert "hook_strength" in result.breakdown
        assert "topic_timeliness" in result.breakdown
        assert len(result.bar) == 20

    def test_weak_post_scores_low(self):
        from src.scorer.engine import score_post
        result = score_post(
            post_text="I'm excited to share that AI is important.",
            hook_line="I'm excited to share that AI is important.",
            critic_score=3.0,
        )
        assert result.overall_pct < 50

    def test_emerging_trend_boosts_score(self):
        from src.scorer.engine import score_post
        base = score_post(
            post_text="AI agents are changing workflows.",
            hook_line="AI agents are changing workflows.",
            critic_score=7.0,
            trend_phase="STABLE",
        )
        boosted = score_post(
            post_text="AI agents are changing workflows.",
            hook_line="AI agents are changing workflows.",
            critic_score=7.0,
            trend_momentum=0.9,
            trend_phase="EMERGING",
        )
        assert boosted.overall_pct > base.overall_pct

    def test_virality_score_display(self):
        from src.scorer.engine import ViralityScore
        v = ViralityScore(
            overall_pct=75,
            breakdown={"hook_strength": 80, "format_structure": 70},
            weights={"hook_strength": 0.2, "format_structure": 0.15},
        )
        assert "Hook Strength: 80%" in v.display
        assert v.tier == "GOOD"


class TestHookVariant:
    def test_hook_variant_dataclass(self):
        from src.hooks.generator import HookVariant
        hv = HookVariant(label="A (original)", text="Bold opener", technique="contrarian")
        assert hv.label == "A (original)"
        assert hv.technique == "contrarian"

    def test_parse_hooks_json(self):
        from src.hooks.generator import _parse_hooks
        text = '{"hook_b": {"text": "Alt hook", "technique": "question"}, "hook_c": {"text": "Another", "technique": "statistic"}}'
        result = _parse_hooks(text)
        assert "hook_b" in result
        assert "hook_c" in result
        assert result["hook_b"]["technique"] == "question"

    def test_parse_hooks_empty(self):
        from src.hooks.generator import _parse_hooks
        assert _parse_hooks("not json at all") == {}
