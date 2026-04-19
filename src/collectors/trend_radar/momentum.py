"""
Trend Momentum Algorithm — detects topics that are ABOUT TO go viral,
not just topics that already are.

Computes velocity (how fast mentions grow) and acceleration (is growth
speeding up or slowing down) to classify trend phase:

  EMERGING   → velocity high + accelerating    → BEST time to post
  PEAKING    → velocity high + decelerating    → still good, more competition
  SATURATED  → velocity low  + high total      → everyone posted already
  STABLE     → steady mentions, no spike       → evergreen, not time-sensitive
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrendScore:
    """Computed trend analysis for a single topic."""
    topic: str
    momentum: float              # 0.0-1.0 composite score
    phase: str                   # EMERGING | PEAKING | SATURATED | STABLE
    velocity: float              # rate of growth (current window)
    acceleration: float          # change in velocity
    current_mentions: int        # total mentions in latest window
    previous_mentions: int = 0   # mentions in prior window
    first_seen: datetime | None = None

    @property
    def phase_emoji(self) -> str:
        return {
            "EMERGING": "🔴",
            "PEAKING": "🟡",
            "SATURATED": "⚪",
            "STABLE": "🟢",
        }.get(self.phase, "❓")

    @property
    def weight_multiplier(self) -> float:
        """How much to boost/penalize content about this topic."""
        return {
            "EMERGING": 2.0,
            "PEAKING": 1.2,
            "STABLE": 1.0,
            "SATURATED": 0.5,
        }.get(self.phase, 1.0)

    @property
    def display(self) -> str:
        return (
            f"{self.phase_emoji} {self.phase}: {self.topic} "
            f"(momentum: {self.momentum:.2f}, "
            f"mentions: {self.previous_mentions}→{self.current_mentions})"
        )


def compute_momentum(
    topic: str,
    current_mentions: int,
    previous_mentions: int,
    older_mentions: int = 0,
    first_seen: datetime | None = None,
) -> TrendScore:
    """
    Compute trend momentum for a topic based on mention counts across time windows.

    Args:
        topic: The topic/keyword being tracked
        current_mentions: Mentions in the latest window (e.g. last 12h)
        previous_mentions: Mentions in the prior window (e.g. 12-24h ago)
        older_mentions: Mentions in the oldest window (e.g. 24-48h ago)
        first_seen: When this topic first appeared in our data

    Returns:
        TrendScore with momentum, phase classification, and weight multiplier
    """
    # Avoid division by zero
    prev = max(previous_mentions, 1)
    older = max(older_mentions, 1)

    # Velocity: growth rate in current window vs previous
    velocity = (current_mentions - previous_mentions) / prev

    # Acceleration: is growth speeding up or slowing down
    velocity_prior = (previous_mentions - older_mentions) / older
    acceleration = velocity - velocity_prior

    # Phase classification
    if current_mentions <= 1 and previous_mentions <= 1:
        phase = "STABLE"
    elif velocity > 1.5 and acceleration > 0:
        phase = "EMERGING"
    elif velocity > 0.5 and acceleration > 0:
        phase = "EMERGING"
    elif velocity > 0.3 and acceleration <= 0:
        phase = "PEAKING"
    elif velocity < 0.2 and current_mentions > 5:
        phase = "SATURATED"
    else:
        phase = "STABLE"

    # Brand new topics with sudden appearance are EMERGING
    if previous_mentions == 0 and current_mentions >= 3:
        phase = "EMERGING"
        velocity = 2.0

    # Composite momentum score (0-1)
    raw_momentum = (
        max(0, velocity) * 0.45
        + max(0, acceleration) * 0.30
        + min(current_mentions / 10, 1) * 0.25
    )
    momentum = min(1.0, max(0.0, raw_momentum))

    return TrendScore(
        topic=topic,
        momentum=momentum,
        phase=phase,
        velocity=velocity,
        acceleration=acceleration,
        current_mentions=current_mentions,
        previous_mentions=previous_mentions,
        first_seen=first_seen,
    )
