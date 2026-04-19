"""
Engagement Driver Scorer — evaluates how likely a post is to generate
comments, shares, and reactions.

Factors:
- CTA quality (open question > yes/no > none)
- Shareability (framework/insight someone would repost)
- Comment bait patterns
- Emotional resonance
"""

from __future__ import annotations

import re


# Strong CTA patterns (higher score)
_STRONG_CTA = [
    (r"what('s| is| are) your (take|thought|experience|view|opinion)", 15),
    (r"agree or disagree", 12),
    (r"what would you (add|change|do)", 12),
    (r"how (do|are|have|did) you", 10),
    (r"what (strategies|steps|challenges|approaches)", 10),
    (r"share your (thoughts|experience|take)", 10),
    (r"i'd love to hear", 8),
    (r"tag someone who", 8),
    (r"drop a .* (below|in the comments)", 8),
]

# Weak CTA patterns
_WEAK_CTA = [
    (r"what do you think\?$", 5),   # too generic
    (r"thoughts\?$", 3),             # lazy
    (r"let me know\b", 3),
]

# Shareability signals
_SHAREABLE = [
    (r"\b(framework|model|checklist|template|playbook)\b", 8),
    (r"\b(step[s]? \d|tip[s]? \d|\d (steps|tips|rules|lessons))\b", 8),
    (r"\b(here'?s (how|what|why))\b", 5),
    (r"\b(the (real|actual|hard) truth)\b", 5),
    (r"\b(nobody talks about|rarely discussed)\b", 6),
]

# Emotional resonance
_EMOTIONAL = [
    (r"\b(failed|mistake|struggled|painful|hard lesson)\b", 5),
    (r"\b(breakthrough|transformed|changed everything)\b", 4),
    (r"\b(honest|truth|confession|admit)\b", 4),
]


def score_engagement(post_text: str) -> int:
    """
    Score a post's engagement potential from 0-100.

    Args:
        post_text: The full post text

    Returns:
        Integer score 0-100
    """
    if not post_text:
        return 0

    score = 40  # base
    text_lower = post_text.lower()

    # ── CTA strength (check last 200 chars) ────
    ending = text_lower[-200:]
    has_question = "?" in ending

    if has_question:
        score += 8  # any question at the end is better than none

    # Check strong CTA patterns
    best_cta = 0
    for pattern, bonus in _STRONG_CTA:
        if re.search(pattern, ending):
            best_cta = max(best_cta, bonus)
    score += best_cta

    # Check weak CTA (only if no strong CTA matched)
    if best_cta == 0:
        for pattern, bonus in _WEAK_CTA:
            if re.search(pattern, ending):
                score += bonus
                break

    # No question at all = penalty
    if not has_question:
        score -= 10

    # ── Shareability ─────────────────────────────
    for pattern, bonus in _SHAREABLE:
        if re.search(pattern, text_lower):
            score += bonus

    # ── Emotional resonance ──────────────────────
    for pattern, bonus in _EMOTIONAL:
        if re.search(pattern, text_lower):
            score += bonus

    # ── Controversy / debate potential ────────────
    if re.search(r"\b(hot take|unpopular opinion|controversial)\b", text_lower):
        score += 8  # controversy drives comments

    if re.search(r"\b(agree or disagree|right or wrong)\b", text_lower):
        score += 6

    # ── Post ends with a strong close ────────────
    lines = [l.strip() for l in post_text.strip().split("\n") if l.strip() and not l.startswith("#")]
    if lines:
        last_line = lines[-1].lower()
        # Single punchy closing line
        if len(last_line.split()) <= 8 and "?" in last_line:
            score += 5
        # Call to action in last line
        if any(w in last_line for w in ["share", "comment", "tell me", "your take"]):
            score += 4

    return max(0, min(100, score))
