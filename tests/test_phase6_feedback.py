"""
Phase 6 feedback loop tests.
Run with: pytest tests/test_phase6_feedback.py -v
"""

import pytest


class TestScraper:
    def test_metrics_from_manual(self):
        from src.autopsy.scraper import metrics_from_manual
        m = metrics_from_manual(reactions=100, comments=20, shares=5)
        assert m.total_engagement == 125
        assert m.has_data is True

    def test_empty_metrics(self):
        from src.autopsy.scraper import metrics_from_manual
        m = metrics_from_manual()
        assert m.total_engagement == 0
        assert m.has_data is False

    def test_post_metrics_dataclass(self):
        from src.autopsy.scraper import PostMetrics
        m = PostMetrics(reactions=50, comments=10)
        assert m.total_engagement == 60


class TestAnalyzer:
    def test_simple_patterns_empty(self):
        from src.autopsy.analyzer import _compute_simple_patterns
        patterns = _compute_simple_patterns([], {})
        assert patterns == []

    def test_analysis_report_defaults(self):
        from src.autopsy.analyzer import AnalysisReport
        report = AnalysisReport()
        assert report.total_posts == 0
        assert report.patterns == []
        assert report.best_angle == ""

    def test_performance_pattern_dataclass(self):
        from src.autopsy.analyzer import PerformancePattern
        p = PerformancePattern(
            pattern_type="angle",
            description="hot_take outperforms tutorial",
            evidence="hot_take: 80% avg vs tutorial: 45% avg",
            recommendation="Use more hot_take angles",
            confidence=0.8,
        )
        assert p.pattern_type == "angle"
        assert p.confidence == 0.8


class TestPersonaUpdater:
    def test_get_learned_preferences_no_file(self):
        from src.autopsy.persona_updater import get_learned_preferences
        # Should return empty dict gracefully if no file
        prefs = get_learned_preferences()
        assert isinstance(prefs, dict)


class TestMemoryUpdater:
    @pytest.mark.asyncio
    async def test_get_topic_performance_empty(self):
        from src.autopsy.memory_updater import get_topic_performance
        result = await get_topic_performance()
        assert isinstance(result, dict)


class TestFeedbackIntegration:
    def test_engagement_score_high(self):
        from src.autopsy.report_builder import compute_engagement_score
        score = compute_engagement_score(500, 50, 20, 5000)
        assert score > 60

    def test_engagement_score_zero(self):
        from src.autopsy.report_builder import compute_engagement_score
        assert compute_engagement_score(0, 0, 0, 0) == 0.0

    def test_engagement_score_no_impressions_estimates(self):
        from src.autopsy.report_builder import compute_engagement_score
        score = compute_engagement_score(100, 10, 5, 0)
        assert score > 0
