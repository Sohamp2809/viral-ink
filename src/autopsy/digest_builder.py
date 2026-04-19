"""
Weekly Digest — summarizes post performance, prediction accuracy,
and agent learning over the past week.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from src.utils.db import get_session, GeneratedPost

logger = logging.getLogger(__name__)


async def build_weekly_digest(days: int = 7) -> dict:
    """
    Build a weekly performance summary.

    Returns a dict with stats, best/worst performers, and insights.
    """
    from src.autopsy.report_builder import AutopsyReport
    from src.utils.db import get_engine, Base

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session:
        # Get generated posts
        gen_result = await session.execute(
            select(GeneratedPost).where(GeneratedPost.created_at >= cutoff)
        )
        generated = gen_result.scalars().all()

        # Get autopsy reports
        autopsy_result = await session.execute(
            select(AutopsyReport).where(AutopsyReport.analyzed_at >= cutoff)
        )
        autopsies = autopsy_result.scalars().all()

    total_generated = len(generated)
    total_selected = sum(1 for p in generated if p.was_selected)
    total_autopsied = len(autopsies)

    # Averages
    avg_predicted = (
        sum(p.virality_score for p in generated) / total_generated
        if total_generated else 0
    )
    avg_actual = (
        sum(a.actual_score for a in autopsies) / total_autopsied
        if total_autopsied else 0
    )
    avg_error = (
        sum(abs(a.prediction_error) for a in autopsies) / total_autopsied
        if total_autopsied else 0
    )

    # Best and worst
    best = max(autopsies, key=lambda a: a.actual_score) if autopsies else None
    worst = min(autopsies, key=lambda a: a.actual_score) if autopsies else None

    # Angle performance
    angle_perf: dict[str, list[float]] = {}
    for a in autopsies:
        angle_perf.setdefault(a.angle, []).append(a.actual_score)
    angle_avg = {
        angle: sum(scores) / len(scores)
        for angle, scores in angle_perf.items()
    }

    digest = {
        "period_days": days,
        "total_generated": total_generated,
        "total_selected": total_selected,
        "selection_rate": total_selected / total_generated if total_generated else 0,
        "total_autopsied": total_autopsied,
        "avg_predicted_score": round(avg_predicted, 1),
        "avg_actual_score": round(avg_actual, 1),
        "avg_prediction_error": round(avg_error, 1),
        "prediction_accuracy": round(100 - avg_error, 1) if avg_error else 0,
        "best_post": {
            "topic": best.topic if best else "",
            "actual_score": best.actual_score if best else 0,
            "reactions": best.reactions if best else 0,
            "what_worked": best.what_worked if best else "",
        },
        "worst_post": {
            "topic": worst.topic if worst else "",
            "actual_score": worst.actual_score if worst else 0,
            "what_didnt": worst.what_didnt if worst else "",
        },
        "angle_performance": angle_avg,
    }

    return digest


def format_digest_text(digest: dict) -> str:
    """Format digest as readable text for console or email."""
    lines = [
        f"{'═' * 50}",
        f"WEEKLY DIGEST — Last {digest['period_days']} days",
        f"{'═' * 50}",
        "",
        f"Posts: {digest['total_generated']} generated · {digest['total_selected']} selected ({digest['selection_rate']:.0%} use rate)",
        f"Autopsied: {digest['total_autopsied']} posts",
        "",
        f"Avg predicted: {digest['avg_predicted_score']}%",
        f"Avg actual:    {digest['avg_actual_score']}%",
        f"Prediction accuracy: {digest['prediction_accuracy']}%",
        "",
    ]

    if digest["best_post"]["topic"]:
        lines.extend([
            f"📈 BEST: {digest['best_post']['topic']} ({digest['best_post']['actual_score']:.0f}%, {digest['best_post']['reactions']} reactions)",
            f"   {digest['best_post']['what_worked'][:100]}",
            "",
        ])

    if digest["worst_post"]["topic"]:
        lines.extend([
            f"📉 WORST: {digest['worst_post']['topic']} ({digest['worst_post']['actual_score']:.0f}%)",
            f"   {digest['worst_post']['what_didnt'][:100]}",
            "",
        ])

    if digest["angle_performance"]:
        lines.append("Angle performance:")
        for angle, avg in sorted(digest["angle_performance"].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {angle}: {avg:.0f}%")

    return "\n".join(lines)