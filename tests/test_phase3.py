"""
Phase 3 tests — trend prediction radar.
Run with: pytest tests/test_phase3.py -v
"""

import pytest
from datetime import datetime, timezone
from collections import Counter


class TestMomentum:
    def test_emerging_high_velocity_accelerating(self):
        from src.collectors.trend_radar.momentum import compute_momentum
        score = compute_momentum(
            topic="new ai model",
            current_mentions=10,
            previous_mentions=2,
            older_mentions=1,
        )
        assert score.phase == "EMERGING"
        assert score.momentum > 0.5
        assert score.weight_multiplier == 2.0

    def test_peaking_high_velocity_decelerating(self):
        from src.collectors.trend_radar.momentum import compute_momentum
        score = compute_momentum(
            topic="gpt release",
            current_mentions=8,
            previous_mentions=5,
            older_mentions=1,
        )
        # velocity = (8-5)/5 = 0.6, prior velocity = (5-1)/1 = 4.0
        # acceleration = 0.6 - 4.0 = -3.4 (decelerating)
        assert score.phase == "PEAKING"
        assert score.weight_multiplier == 1.2

    def test_saturated_low_velocity_high_total(self):
        from src.collectors.trend_radar.momentum import compute_momentum
        score = compute_momentum(
            topic="old topic",
            current_mentions=10,
            previous_mentions=9,
            older_mentions=8,
        )
        assert score.phase in ("STABLE", "SATURATED")

    def test_stable_no_mentions(self):
        from src.collectors.trend_radar.momentum import compute_momentum
        score = compute_momentum(
            topic="quiet topic",
            current_mentions=1,
            previous_mentions=1,
            older_mentions=1,
        )
        assert score.phase == "STABLE"
        assert score.weight_multiplier == 1.0

    def test_brand_new_topic_is_emerging(self):
        from src.collectors.trend_radar.momentum import compute_momentum
        score = compute_momentum(
            topic="brand new thing",
            current_mentions=5,
            previous_mentions=0,
            older_mentions=0,
        )
        assert score.phase == "EMERGING"

    def test_trend_score_display(self):
        from src.collectors.trend_radar.momentum import TrendScore
        ts = TrendScore(
            topic="AI agents",
            momentum=0.85,
            phase="EMERGING",
            velocity=2.0,
            acceleration=0.5,
            current_mentions=10,
            previous_mentions=3,
        )
        display = ts.display
        assert "EMERGING" in display
        assert "AI agents" in display
        assert "🔴" in display

    def test_phase_emoji(self):
        from src.collectors.trend_radar.momentum import TrendScore
        ts = TrendScore(topic="t", momentum=0, phase="PEAKING",
                        velocity=0, acceleration=0, current_mentions=0)
        assert ts.phase_emoji == "🟡"


class TestTopicExtraction:
    def test_extracts_known_patterns(self):
        from src.collectors.trend_radar.tracker import extract_topics
        from src.collectors.base import ContentItem
        items = [
            ContentItem(title="OpenAI launches new AI model", summary="A new LLM for biology"),
            ContentItem(title="AI startup raises funding", summary="Machine learning company"),
            ContentItem(title="AI revolution continues", summary="Artificial intelligence grows"),
        ]
        topics = extract_topics(items)
        # "ai" should appear multiple times
        assert any("ai" in topic for topic in topics.keys())

    def test_filters_low_count_topics(self):
        from src.collectors.trend_radar.tracker import extract_topics
        from src.collectors.base import ContentItem
        items = [
            ContentItem(title="Unique one-off topic xyz", summary="Nothing else like it"),
        ]
        topics = extract_topics(items)
        # Single mention topics should be filtered out (need 2+)
        assert "unique one-off topic xyz" not in topics

    def test_extracts_bigrams(self):
        from src.collectors.trend_radar.tracker import extract_topics
        from src.collectors.base import ContentItem
        items = [
            ContentItem(title="Open source AI tools are great", summary=""),
            ContentItem(title="Best open source projects", summary="open source community"),
        ]
        topics = extract_topics(items)
        assert any("open source" in topic for topic in topics.keys())


class TestTrendWeights:
    def test_apply_trend_weights_boosts_emerging(self):
        from src.collectors.trend_radar.tracker import apply_trend_weights
        from src.collectors.trend_radar.momentum import TrendScore
        from src.collectors.base import ContentItem

        items = [
            ContentItem(title="New AI breakthrough announced", summary="AI model", weight=10.0),
        ]
        trends = [
            TrendScore(topic="ai", momentum=0.9, phase="EMERGING",
                        velocity=2.0, acceleration=1.0, current_mentions=10),
        ]

        apply_trend_weights(items, trends)
        assert items[0].weight == 20.0  # 10.0 * 2.0x
        assert items[0].metadata["trend_phase"] == "EMERGING"

    def test_apply_trend_weights_penalizes_saturated(self):
        from src.collectors.trend_radar.tracker import apply_trend_weights
        from src.collectors.trend_radar.momentum import TrendScore
        from src.collectors.base import ContentItem

        items = [
            ContentItem(title="Old saturated topic discussion", summary="saturated topic", weight=10.0),
        ]
        trends = [
            TrendScore(topic="saturated topic", momentum=0.1, phase="SATURATED",
                        velocity=0.1, acceleration=-0.5, current_mentions=20),
        ]

        apply_trend_weights(items, trends)
        assert items[0].weight == 5.0  # 10.0 * 0.5x


class TestFormatting:
    def test_format_trend_radar_with_trends(self):
        from src.collectors.trend_radar.tracker import format_trend_radar
        from src.collectors.trend_radar.momentum import TrendScore

        trends = [
            TrendScore(topic="AI agents", momentum=0.9, phase="EMERGING",
                        velocity=2.0, acceleration=1.0, current_mentions=10),
            TrendScore(topic="cloud costs", momentum=0.5, phase="PEAKING",
                        velocity=0.5, acceleration=-0.1, current_mentions=8),
        ]

        output = format_trend_radar(trends)
        assert "TREND RADAR" in output
        assert "AI agents" in output
        assert "EMERGING" in output

    def test_format_trend_radar_empty(self):
        from src.collectors.trend_radar.tracker import format_trend_radar
        output = format_trend_radar([])
        assert "No trend data" in output
