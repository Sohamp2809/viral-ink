"""
Phase 2 tests — multi-agent pipeline components.
Run with: pytest tests/test_phase2.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass


class TestResearcher:
    def test_parse_briefs_json_array(self):
        from src.generator.agents.researcher import _parse_briefs
        text = '[{"source_title": "Test", "topic": "AI", "angle": "hot_take", "thesis": "AI is cool"}]'
        result = _parse_briefs(text)
        assert len(result) == 1
        assert result[0]["angle"] == "hot_take"

    def test_parse_briefs_with_fences(self):
        from src.generator.agents.researcher import _parse_briefs
        text = '```json\n[{"topic": "AI"}]\n```'
        result = _parse_briefs(text)
        assert len(result) == 1

    def test_parse_briefs_embedded(self):
        from src.generator.agents.researcher import _parse_briefs
        text = 'Here are the opportunities:\n[{"topic": "AI"}]\nDone.'
        result = _parse_briefs(text)
        assert len(result) == 1

    def test_content_brief_dataclass(self):
        from src.generator.agents.researcher import ContentBrief
        brief = ContentBrief(
            topic="AI Trends",
            angle="hot_take",
            thesis="AI will replace meetings",
            source_title="TechCrunch article",
        )
        assert brief.topic == "AI Trends"
        assert brief.confidence == "MEDIUM"


class TestWriterAgent:
    def test_parse_draft_json(self):
        from src.generator.agents.writer import _parse_draft
        text = '{"post_text": "Hello world", "hook_line": "Hello", "hashtags": ["#AI"]}'
        result = _parse_draft(text)
        assert result["post_text"] == "Hello world"

    def test_parse_draft_with_fences(self):
        from src.generator.agents.writer import _parse_draft
        text = '```json\n{"post_text": "Test"}\n```'
        result = _parse_draft(text)
        assert result["post_text"] == "Test"

    def test_parse_draft_fallback_to_raw(self):
        from src.generator.agents.writer import _parse_draft
        text = "This is just plain text, not JSON at all."
        result = _parse_draft(text)
        assert result["post_text"] == text

    def test_draft_char_count(self):
        from src.generator.agents.writer import Draft
        draft = Draft(post_text="Hello world")
        assert draft.char_count == 11


class TestCritic:
    def test_parse_critique_json(self):
        from src.generator.agents.critic import _parse_critique
        text = json.dumps({
            "scores": {"hook_strength": 8, "voice_match": 7},
            "overall_score": 7.5,
            "verdict": "PUBLISH",
            "issues": [],
            "revision_instructions": "",
            "avoided_word_violations": [],
        })
        result = _parse_critique(text)
        assert result["verdict"] == "PUBLISH"
        assert result["overall_score"] == 7.5

    def test_parse_critique_fallback(self):
        from src.generator.agents.critic import _parse_critique
        text = "This is not JSON"
        result = _parse_critique(text)
        assert result["verdict"] == "REVISE"

    def test_critique_passed_property(self):
        from src.generator.agents.critic import Critique
        c1 = Critique(verdict="PUBLISH")
        assert c1.passed is True
        c2 = Critique(verdict="REVISE")
        assert c2.passed is False

    @pytest.mark.asyncio
    async def test_critic_catches_avoided_words(self):
        from src.generator.agents.critic import critique
        from src.generator.agents.writer import Draft
        from src.generator.agents.researcher import ContentBrief

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(
            text=json.dumps({
                "scores": {"hook_strength": 8},
                "overall_score": 8.0,
                "verdict": "PUBLISH",
                "issues": [],
                "revision_instructions": "",
                "avoided_word_violations": [],
            }),
            input_tokens=100,
            output_tokens=100,
        ))

        draft = Draft(
            post_text="This is a game-changer for the industry and will leverage synergy.",
            brief=ContentBrief(topic="Test", angle="hot_take", thesis="Test thesis"),
        )

        persona = {
            "vocabulary": {
                "avoided_words": ["game-changer", "synergy", "leverage"]
            }
        }

        result = await critique(draft, persona, llm=mock_llm)

        # Hard check should catch avoided words even if LLM misses them
        assert "game-changer" in result.avoided_word_violations
        assert "synergy" in result.avoided_word_violations
        assert "leverage" in result.avoided_word_violations
        assert result.verdict == "REVISE"  # downgraded from PUBLISH


class TestFinalPost:
    def test_final_post_display(self):
        from src.generator.orchestrator import FinalPost
        post = FinalPost(
            post_text="Test post content here",
            topic="AI Trends",
            angle="hot_take",
            hashtags=["#AI", "#Tech"],
            critic_scores={"hook_strength": 8, "voice_match": 7},
            critic_verdict="PUBLISH",
            overall_score=7.5,
        )
        assert post.char_count == 22
        display = post.display
        assert "AI Trends" in display
        assert "✅" in display


class TestOrchestrator:
    def test_build_context_window(self):
        from src.generator.orchestrator import _build_context_window
        from src.collectors.base import ContentItem
        from datetime import datetime, timezone

        items = [
            ContentItem(
                title="Test Article",
                summary="This is a test summary",
                source_name="TestSource",
                published_at=datetime.now(timezone.utc),
                weight=1.5,
            )
        ]
        context = _build_context_window(items)
        assert "Test Article" in context
        assert "TestSource" in context

    def test_attach_summaries(self):
        from src.generator.orchestrator import _attach_summaries
        from src.generator.agents.researcher import ContentBrief
        from src.collectors.base import ContentItem

        briefs = [ContentBrief(source_title="Test Article", topic="Test")]
        items = [ContentItem(title="Test Article", summary="Full summary here")]

        _attach_summaries(briefs, items)
        assert briefs[0].source_summary == "Full summary here"
