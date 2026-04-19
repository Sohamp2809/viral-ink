"""
Phase 5+6 tests — email delivery, scheduling, autopsy, calibration.
Run with: pytest tests/test_phase5_6.py -v
"""

import pytest
from datetime import datetime, timezone


class TestEmailBuilder:
    def test_build_email_html(self):
        from src.delivery.email_builder import build_email_html
        from src.generator.orchestrator import FinalPost
        from src.scorer.engine import ViralityScore
        from src.hooks.generator import HookVariant

        posts = [
            FinalPost(
                post_text="Test post about AI agents.",
                topic="AI Agents",
                angle="hot_take",
                source_title="Test Source",
                hashtags=["#AI"],
                critic_scores={"hook_strength": 8},
                critic_verdict="PUBLISH",
                overall_score=7.5,
                hook_variants=[
                    HookVariant(label="A (original)", text="Bold opener", technique="contrarian"),
                    HookVariant(label="B", text="Alt hook", technique="question"),
                ],
                virality=ViralityScore(
                    overall_pct=75,
                    breakdown={"hook_strength": 80, "format_structure": 70},
                    weights={"hook_strength": 0.2, "format_structure": 0.15},
                ),
            )
        ]

        subject, html = build_email_html(posts, [])

        assert "LinkedIn posts" in subject
        assert "75%" in subject or "Top pick" in subject
        assert "AI Agents" in html
        assert "Test post about AI agents" in html
        assert "#AI" in html
        assert "Bold opener" in html
        assert "Alt hook" in html

    def test_build_email_with_trends(self):
        from src.delivery.email_builder import build_email_html
        from src.collectors.trend_radar.momentum import TrendScore

        trends = [
            TrendScore(
                topic="AI agents", momentum=0.9, phase="EMERGING",
                velocity=2.0, acceleration=1.0, current_mentions=10,
            ),
        ]

        subject, html = build_email_html([], trends)
        assert "AI agents" in html
        assert "Trend radar" in html

    def test_score_color(self):
        from src.delivery.email_builder import _score_color
        assert _score_color(80) == "#059669"  # emerald
        assert _score_color(65) == "#2563eb"  # blue
        assert _score_color(50) == "#d97706"  # amber
        assert _score_color(30) == "#dc2626"  # red


class TestTracker:
    @pytest.mark.asyncio
    async def test_get_pipeline_stats_empty(self):
        from src.delivery.tracker import get_pipeline_stats
        stats = await get_pipeline_stats(days=1)
        assert "total_generated" in stats
        assert "selection_rate" in stats


class TestAutopsyReport:
    def test_engagement_score_computation(self):
        from src.autopsy.report_builder import compute_engagement_score

        # High engagement
        score = compute_engagement_score(
            reactions=500, comments=50, shares=20, impressions=5000
        )
        assert score > 60

        # Low engagement
        score = compute_engagement_score(
            reactions=5, comments=0, shares=0, impressions=5000
        )
        assert score < 30

        # Zero everything
        score = compute_engagement_score(0, 0, 0, 0)
        assert score == 0.0

    def test_engagement_score_no_impressions(self):
        from src.autopsy.report_builder import compute_engagement_score
        # Should estimate impressions from reactions
        score = compute_engagement_score(
            reactions=100, comments=10, shares=5, impressions=0
        )
        assert score > 0


class TestCalibrator:
    def test_load_default_weights(self):
        from src.autopsy.calibrator import load_weights, DEFAULT_WEIGHTS
        weights = load_weights()
        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)
        assert "hook_strength" in weights

    def test_default_weights_sum_to_one(self):
        from src.autopsy.calibrator import DEFAULT_WEIGHTS
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0, abs=0.001)


class TestDigestBuilder:
    @pytest.mark.asyncio
    async def test_build_empty_digest(self):
        from src.autopsy.digest_builder import build_weekly_digest, format_digest_text
        digest = await build_weekly_digest(days=1)
        assert digest["total_generated"] >= 0
        text = format_digest_text(digest)
        assert "WEEKLY DIGEST" in text


class TestScheduler:
    def test_scheduler_import(self):
        from src.delivery.scheduler import start_scheduler
        # Just verify import works — don't actually start it
        assert callable(start_scheduler)