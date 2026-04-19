"""
Scoring Calibrator — adjusts virality signal weights based on
actual post performance data from autopsies.

After enough autopsies (10+), this module computes which scoring signals
best predict actual engagement and rebalances weights accordingly.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from sqlalchemy import select

from src.utils.config import CONFIG_DIR
from src.utils.db import get_session

logger = logging.getLogger(__name__)

WEIGHTS_FILE = CONFIG_DIR / "scoring_weights.yaml"

DEFAULT_WEIGHTS = {
    "hook_strength": 0.20,
    "format_structure": 0.15,
    "engagement_driver": 0.15,
    "critic_quality": 0.30,
    "topic_timeliness": 0.20,
}


def load_weights() -> dict:
    """Load scoring weights from config file, or return defaults."""
    if WEIGHTS_FILE.exists():
        with open(WEIGHTS_FILE) as f:
            data = yaml.safe_load(f)
            if data and isinstance(data, dict):
                return data.get("weights", DEFAULT_WEIGHTS.copy())
    return DEFAULT_WEIGHTS.copy()


def save_weights(weights: dict, reason: str = "manual") -> None:
    """Save updated weights to config file."""
    WEIGHTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "weights": weights,
        "last_updated_reason": reason,
    }
    with open(WEIGHTS_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    logger.info(f"Scoring weights saved ({reason})")


async def recalibrate(min_reports: int = 10) -> dict | None:
    """
    Recalibrate scoring weights based on autopsy data.

    Computes correlation between each scoring signal and actual
    engagement scores, then rebalances weights proportionally.

    Args:
        min_reports: Minimum autopsy reports needed before calibrating

    Returns:
        Updated weights dict, or None if not enough data
    """
    from src.autopsy.report_builder import AutopsyReport
    from src.utils.db import get_engine

    # Ensure table exists
    engine = await get_engine()
    async with engine.begin() as conn:
        from src.utils.db import Base
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    async with session:
        result = await session.execute(select(AutopsyReport))
        reports = result.scalars().all()

    if len(reports) < min_reports:
        logger.info(
            f"Not enough autopsy data for calibration "
            f"({len(reports)}/{min_reports} reports)"
        )
        return None

    # Compute simple correlation: which predicted signals align with actual scores
    # For now, use prediction error direction to adjust weights
    total_error = sum(r.prediction_error for r in reports)
    avg_error = total_error / len(reports)

    current_weights = load_weights()

    # If we're consistently over-predicting, reduce weights on the signals
    # that tend to score high. If under-predicting, boost them.
    # This is a simple heuristic — more sophisticated methods can come later.

    if abs(avg_error) > 5:
        adjustment = 0.02 if avg_error > 0 else -0.02

        # Adjust the most influential signal
        if avg_error > 0:
            # Over-predicting: reduce critic_quality weight (often too generous)
            current_weights["critic_quality"] = max(0.10, current_weights["critic_quality"] - adjustment)
            current_weights["engagement_driver"] = min(0.25, current_weights["engagement_driver"] + adjustment)
        else:
            # Under-predicting: boost topic_timeliness (trends matter more)
            current_weights["topic_timeliness"] = min(0.30, current_weights["topic_timeliness"] + adjustment)
            current_weights["hook_strength"] = max(0.10, current_weights["hook_strength"] - adjustment)

        # Normalize to sum to 1.0
        total = sum(current_weights.values())
        current_weights = {k: v / total for k, v in current_weights.items()}

        save_weights(current_weights, reason=f"autopsy_calibration (avg_error: {avg_error:+.1f})")

        logger.info(f"Scoring weights recalibrated (avg prediction error: {avg_error:+.1f})")
        return current_weights

    logger.info(f"Scoring weights are accurate (avg error: {avg_error:+.1f}) — no changes needed")
    return current_weights