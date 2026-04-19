"""
Autopsy Analyzer — performs deep analysis on post performance data.

Goes beyond single-post analysis to detect PATTERNS across multiple posts:
- Which hooks perform best for this user's audience
- Which angles consistently over/underperform
- Which topics get the most engagement
- How prediction accuracy changes over time
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from src.utils.db import get_session
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class PerformancePattern:
    """A detected pattern in post performance data."""
    pattern_type: str     # "angle", "hook", "topic", "timing"
    description: str      # human-readable description
    evidence: str         # supporting data
    recommendation: str   # what to do about it
    confidence: float     # 0-1 how confident we are


@dataclass
class AnalysisReport:
    """Complete analysis across multiple autopsy reports."""
    total_posts: int = 0
    avg_predicted: float = 0.0
    avg_actual: float = 0.0
    accuracy: float = 0.0
    patterns: list[PerformancePattern] = field(default_factory=list)
    best_angle: str = ""
    worst_angle: str = ""
    best_hook_type: str = ""
    recommendations: list[str] = field(default_factory=list)


PATTERN_ANALYSIS_PROMPT = """Analyze these LinkedIn post performance results and identify actionable patterns.

POST PERFORMANCE DATA:
{performance_data}

SUMMARY STATS:
- Total posts analyzed: {total_posts}
- Average predicted virality: {avg_predicted:.0f}%
- Average actual engagement: {avg_actual:.0f}%
- Prediction accuracy: {accuracy:.0f}%

For each post you have: topic, angle, predicted score, actual score, reactions, comments, what worked, what didn't.

Identify SPECIFIC PATTERNS — not generic advice. Look for:
1. Which ANGLES (hot_take, story, tutorial, etc.) consistently perform above/below average?
2. Are there TOPIC CATEGORIES that this audience responds to more?
3. Do posts with certain HOOK TYPES get more engagement?
4. Are there STRUCTURAL PATTERNS (length, paragraph count, question endings) that correlate with performance?
5. Where is the SCORING MODEL most inaccurate and why?

Return JSON:
{{
  "patterns": [
    {{
      "pattern_type": "<angle|hook|topic|structure|timing>",
      "description": "<what the pattern is>",
      "evidence": "<specific numbers supporting this>",
      "recommendation": "<exactly what to change>",
      "confidence": <0.0-1.0>
    }}
  ],
  "best_angle": "<angle that performs best>",
  "worst_angle": "<angle that performs worst>",
  "top_recommendation": "<single most impactful change to make>",
  "scoring_adjustment": "<what scoring signal needs the most adjustment>"
}}"""


async def analyze_performance(
    days: int = 30,
    llm: BaseLLM | None = None,
) -> AnalysisReport:
    """
    Analyze all autopsy data to find performance patterns.

    Args:
        days: How many days of data to analyze
        llm: Cheap LLM for pattern analysis

    Returns:
        AnalysisReport with patterns and recommendations
    """
    from src.autopsy.report_builder import AutopsyReport
    from src.utils.db import get_engine, Base

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session:
        result = await session.execute(
            select(AutopsyReport).where(AutopsyReport.analyzed_at >= cutoff)
        )
        reports = result.scalars().all()

    if not reports:
        return AnalysisReport(recommendations=["No autopsy data yet. Run `pilot autopsy` after publishing posts."])

    report = AnalysisReport(total_posts=len(reports))

    # Compute basic stats
    report.avg_predicted = sum(r.predicted_score for r in reports) / len(reports)
    report.avg_actual = sum(r.actual_score for r in reports) / len(reports)
    errors = [abs(r.prediction_error) for r in reports]
    report.accuracy = 100 - (sum(errors) / len(errors)) if errors else 0

    # Angle performance
    angle_scores: dict[str, list[float]] = {}
    for r in reports:
        if r.angle:
            angle_scores.setdefault(r.angle, []).append(r.actual_score)

    if angle_scores:
        angle_avgs = {a: sum(s) / len(s) for a, s in angle_scores.items()}
        report.best_angle = max(angle_avgs, key=angle_avgs.get)
        report.worst_angle = min(angle_avgs, key=angle_avgs.get)

    # LLM pattern analysis (if enough data)
    if len(reports) >= 5 and llm:
        patterns = await _llm_pattern_analysis(reports, report, llm)
        report.patterns = patterns.get("patterns", [])
        report.recommendations = [patterns.get("top_recommendation", "")]
        if patterns.get("best_angle"):
            report.best_angle = patterns["best_angle"]

    elif len(reports) >= 3:
        # Simple heuristic patterns without LLM
        report.patterns = _compute_simple_patterns(reports, angle_scores)
        report.recommendations = [
            p.recommendation for p in report.patterns[:3]
        ]

    else:
        report.recommendations = [
            f"Only {len(reports)} autopsy reports. Need 5+ for pattern analysis."
        ]

    return report


async def _llm_pattern_analysis(
    reports: list,
    summary: AnalysisReport,
    llm: BaseLLM,
) -> dict:
    """Run LLM analysis on performance data."""
    perf_lines = []
    for r in reports:
        perf_lines.append(
            f"- Topic: {r.topic} | Angle: {r.angle} | "
            f"Predicted: {r.predicted_score:.0f}% | Actual: {r.actual_score:.0f}% | "
            f"Reactions: {r.reactions} | Comments: {r.comments} | "
            f"Worked: {r.what_worked[:80]} | Didn't: {r.what_didnt[:80]}"
        )

    prompt = PATTERN_ANALYSIS_PROMPT.format(
        performance_data="\n".join(perf_lines),
        total_posts=summary.total_posts,
        avg_predicted=summary.avg_predicted,
        avg_actual=summary.avg_actual,
        accuracy=summary.accuracy,
    )

    try:
        result = await llm.generate_json(prompt)
        return result
    except Exception as e:
        logger.warning(f"LLM pattern analysis failed: {e}")
        return {}


def _compute_simple_patterns(
    reports: list,
    angle_scores: dict[str, list[float]],
) -> list[PerformancePattern]:
    """Compute basic patterns without LLM."""
    patterns = []

    # Angle performance pattern
    if angle_scores:
        angle_avgs = {a: sum(s) / len(s) for a, s in angle_scores.items() if len(s) >= 2}

        if angle_avgs:
            best = max(angle_avgs, key=angle_avgs.get)
            worst = min(angle_avgs, key=angle_avgs.get)

            if angle_avgs[best] - angle_avgs[worst] > 10:
                patterns.append(PerformancePattern(
                    pattern_type="angle",
                    description=f"'{best}' posts outperform '{worst}' posts",
                    evidence=f"{best}: {angle_avgs[best]:.0f}% avg vs {worst}: {angle_avgs[worst]:.0f}% avg",
                    recommendation=f"Generate more '{best}' angle posts and fewer '{worst}'",
                    confidence=min(0.5 + len(angle_scores.get(best, [])) * 0.1, 0.9),
                ))

    # Prediction accuracy pattern
    over_predictions = [r for r in reports if r.prediction_error > 15]
    under_predictions = [r for r in reports if r.prediction_error < -15]

    if len(over_predictions) > len(reports) * 0.4:
        patterns.append(PerformancePattern(
            pattern_type="scoring",
            description="Scoring model consistently over-predicts",
            evidence=f"{len(over_predictions)}/{len(reports)} posts scored 15+ points above actual",
            recommendation="Reduce critic_quality weight — the critic may be too generous",
            confidence=0.7,
        ))

    if len(under_predictions) > len(reports) * 0.4:
        patterns.append(PerformancePattern(
            pattern_type="scoring",
            description="Scoring model consistently under-predicts",
            evidence=f"{len(under_predictions)}/{len(reports)} posts scored 15+ points below actual",
            recommendation="Boost topic_timeliness weight — trending topics matter more than expected",
            confidence=0.7,
        ))

    # Engagement pattern
    high_comment = [r for r in reports if r.comments > 20]
    if high_comment:
        high_angles = [r.angle for r in high_comment]
        if len(set(high_angles)) <= 2:
            top_angle = max(set(high_angles), key=high_angles.count)
            patterns.append(PerformancePattern(
                pattern_type="engagement",
                description=f"'{top_angle}' posts drive the most comments",
                evidence=f"{len(high_comment)} posts with 20+ comments, mostly '{top_angle}' angle",
                recommendation=f"Prioritize '{top_angle}' angle when comment engagement is the goal",
                confidence=0.6,
            ))

    return patterns
