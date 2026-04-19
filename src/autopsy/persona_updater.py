"""
Persona Updater — refines the Persona DNA based on autopsy data.

Tracks which hooks, angles, and writing patterns actually perform
for this user's audience, and adjusts the persona profile accordingly.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import yaml
from sqlalchemy import select

from src.utils.config import CONFIG_DIR
from src.utils.db import get_session

logger = logging.getLogger(__name__)

PERSONA_PATH = CONFIG_DIR / "persona_dna.yaml"


async def update_persona_from_autopsies(
    days: int = 30,
    min_reports: int = 5,
) -> dict | None:
    """
    Analyze autopsy reports and update persona_dna.yaml with learned preferences.

    Updates:
    - strong_angles / weak_angles based on actual performance
    - hook_preferences based on which hook types get engagement
    - content_patterns refined by what actually resonates

    Args:
        days: How many days of data to analyze
        min_reports: Minimum reports needed before updating

    Returns:
        Updated persona dict, or None if not enough data
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

    if len(reports) < min_reports:
        logger.info(f"Not enough autopsy data ({len(reports)}/{min_reports}) to update persona")
        return None

    # Load current persona
    if not PERSONA_PATH.exists():
        logger.warning("persona_dna.yaml not found — skipping update")
        return None

    with open(PERSONA_PATH) as f:
        persona = yaml.safe_load(f) or {}

    # ── Compute angle performance ───────────────
    angle_scores: dict[str, list[float]] = {}
    for r in reports:
        if r.angle:
            angle_scores.setdefault(r.angle, []).append(r.actual_score)

    angle_avgs = {
        angle: sum(scores) / len(scores)
        for angle, scores in angle_scores.items()
        if len(scores) >= 2
    }

    if angle_avgs:
        overall_avg = sum(r.actual_score for r in reports) / len(reports)

        strong = [a for a, avg in angle_avgs.items() if avg > overall_avg * 1.2]
        weak = [a for a, avg in angle_avgs.items() if avg < overall_avg * 0.8]

        persona["learned_preferences"] = persona.get("learned_preferences", {})
        persona["learned_preferences"]["strong_angles"] = strong
        persona["learned_preferences"]["weak_angles"] = weak
        persona["learned_preferences"]["angle_performance"] = {
            a: round(avg, 1) for a, avg in sorted(angle_avgs.items(), key=lambda x: x[1], reverse=True)
        }

        logger.info(f"Persona updated — strong angles: {strong}, weak angles: {weak}")

    # ── Compute engagement patterns ─────────────
    high_performers = [r for r in reports if r.actual_score > 70]
    low_performers = [r for r in reports if r.actual_score < 40]

    if high_performers:
        # What do high performers have in common?
        avg_reactions = sum(r.reactions for r in high_performers) / len(high_performers)
        avg_comments = sum(r.comments for r in high_performers) / len(high_performers)

        persona["learned_preferences"]["high_performer_profile"] = {
            "avg_reactions": round(avg_reactions),
            "avg_comments": round(avg_comments),
            "count": len(high_performers),
            "common_angles": list(set(r.angle for r in high_performers)),
        }

    # ── Compute prediction accuracy ─────────────
    avg_error = sum(r.prediction_error for r in reports) / len(reports)
    abs_error = sum(abs(r.prediction_error) for r in reports) / len(reports)

    persona["learned_preferences"]["prediction_stats"] = {
        "avg_error": round(avg_error, 1),
        "avg_abs_error": round(abs_error, 1),
        "accuracy_pct": round(100 - abs_error, 1),
        "total_reports": len(reports),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    # ── Save updated persona ────────────────────
    with open(PERSONA_PATH, "w") as f:
        yaml.dump(persona, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(f"Persona DNA updated with {len(reports)} autopsy reports")
    return persona


def get_learned_preferences() -> dict:
    """Load learned preferences from persona, if they exist."""
    if not PERSONA_PATH.exists():
        return {}

    with open(PERSONA_PATH) as f:
        persona = yaml.safe_load(f) or {}

    return persona.get("learned_preferences", {})
