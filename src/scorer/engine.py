"""
Virality Scoring Engine — combines 5 weighted signals into a 0-100% score.

Signals:
  1. Hook strength      (20%) — How scroll-stopping is the opening
  2. Format & structure  (15%) — Post length, paragraphs, readability
  3. Engagement driver   (15%) — CTA quality, shareability, comment bait
  4. Critic quality      (30%) — LLM critic's overall assessment
  5. Topic timeliness    (20%) — Trend radar momentum score

Each signal returns 0-100 independently. The engine computes a weighted
average and provides a breakdown.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.scorer.hook_scorer import score_hook
from src.scorer.format_scorer import score_format
from src.scorer.engagement_scorer import score_engagement

logger = logging.getLogger(__name__)

# Default weights (auto-tuned by post autopsy in Phase 6)
DEFAULT_WEIGHTS = {
    "hook_strength": 0.20,
    "format_structure": 0.15,
    "engagement_driver": 0.15,
    "critic_quality": 0.30,
    "topic_timeliness": 0.20,
}


@dataclass
class ViralityScore:
    """Complete virality prediction for a single post."""
    overall_pct: int              # 0-100%
    breakdown: dict = field(default_factory=dict)  # signal → 0-100
    weights: dict = field(default_factory=dict)
    reasoning: str = ""

    @property
    def tier(self) -> str:
        """Classify into performance tiers."""
        if self.overall_pct >= 80:
            return "EXCELLENT"
        elif self.overall_pct >= 65:
            return "GOOD"
        elif self.overall_pct >= 50:
            return "AVERAGE"
        return "WEAK"

    @property
    def tier_color(self) -> str:
        return {
            "EXCELLENT": "green",
            "GOOD": "cyan",
            "AVERAGE": "yellow",
            "WEAK": "red",
        }.get(self.tier, "white")

    @property
    def bar(self) -> str:
        filled = self.overall_pct // 5
        return "█" * filled + "░" * (20 - filled)

    @property
    def display(self) -> str:
        parts = []
        for signal, value in self.breakdown.items():
            label = signal.replace("_", " ").title()
            weight_pct = int(self.weights.get(signal, 0) * 100)
            parts.append(f"{label}: {value}% ({weight_pct}w)")
        return " · ".join(parts)


def score_post(
    post_text: str,
    hook_line: str = "",
    hashtags: list[str] | None = None,
    critic_score: float = 5.0,
    trend_momentum: float = 0.0,
    trend_phase: str = "",
    weights: dict | None = None,
) -> ViralityScore:
    """
    Score a post's virality potential across all 5 signals.

    Args:
        post_text: Full post text
        hook_line: The first line (or extracted from post)
        hashtags: List of hashtags
        critic_score: The LLM critic's overall score (0-10 scale)
        trend_momentum: Trend radar momentum (0-1)
        trend_phase: EMERGING / PEAKING / SATURATED / STABLE
        weights: Custom signal weights (defaults used if None)

    Returns:
        ViralityScore with overall percentage and breakdown
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()

    # Extract hook from post if not provided
    if not hook_line and post_text:
        lines = [l.strip() for l in post_text.split("\n") if l.strip()]
        hook_line = lines[0] if lines else ""

    # ── Signal 1: Hook strength (0-100) ──────────
    hook_score = score_hook(hook_line)

    # ── Signal 2: Format & structure (0-100) ─────
    format_score = score_format(post_text, hashtags)

    # ── Signal 3: Engagement driver (0-100) ──────
    engagement_score = score_engagement(post_text)

    # ── Signal 4: Critic quality (0-100) ─────────
    # Convert critic's 0-10 scale to 0-100
    critic_pct = int(min(100, max(0, critic_score * 10)))

    # ── Signal 5: Topic timeliness (0-100) ───────
    if trend_phase == "EMERGING":
        timeliness = int(min(100, 60 + trend_momentum * 40))
    elif trend_phase == "PEAKING":
        timeliness = int(min(80, 40 + trend_momentum * 40))
    elif trend_phase == "SATURATED":
        timeliness = int(max(20, 40 - (1 - trend_momentum) * 20))
    elif trend_phase == "STABLE":
        timeliness = 50  # neutral for evergreen
    else:
        timeliness = 50  # no trend data

    # ── Weighted average ─────────────────────────
    breakdown = {
        "hook_strength": hook_score,
        "format_structure": format_score,
        "engagement_driver": engagement_score,
        "critic_quality": critic_pct,
        "topic_timeliness": timeliness,
    }

    weighted_sum = sum(
        breakdown[signal] * weights.get(signal, 0.2)
        for signal in breakdown
    )
    overall = int(max(0, min(100, weighted_sum)))

    # ── Reasoning ────────────────────────────────
    reasons = []
    if hook_score >= 75:
        reasons.append("Strong hook")
    elif hook_score < 50:
        reasons.append("Weak hook — consider a more contrarian or specific opener")

    if engagement_score >= 70:
        reasons.append("Good engagement driver")
    elif engagement_score < 45:
        reasons.append("Weak CTA — end with a specific question")

    if timeliness >= 70:
        reasons.append(f"Timely ({trend_phase} trend)")
    elif timeliness < 40:
        reasons.append("Topic may be oversaturated")

    if format_score >= 70:
        reasons.append("Well structured")
    elif format_score < 45:
        reasons.append("Structure needs work — shorter paragraphs")

    reasoning = ". ".join(reasons) + "." if reasons else ""

    score = ViralityScore(
        overall_pct=overall,
        breakdown=breakdown,
        weights=weights,
        reasoning=reasoning,
    )

    logger.debug(f"Virality score: {overall}% ({score.tier}) — {reasoning}")

    return score
