"""Trend Prediction Radar — detects emerging topics before they peak."""

from src.collectors.trend_radar.momentum import TrendScore, compute_momentum
from src.collectors.trend_radar.tracker import (
    compute_trends,
    format_trend_radar,
    apply_trend_weights,
    extract_topics,
)

__all__ = [
    "TrendScore",
    "compute_momentum",
    "compute_trends",
    "format_trend_radar",
    "apply_trend_weights",
    "extract_topics",
]
