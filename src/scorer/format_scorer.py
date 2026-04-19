"""
Format & Structure Scorer — evaluates how well a post is optimized
for LinkedIn's reading experience.

Factors:
- Post length (sweet spot: 800-1200 chars)
- Paragraph length (shorter = more scannable)
- Line break density
- Hashtag count and placement
"""

from __future__ import annotations

import re


def score_format(post_text: str, hashtags: list[str] | None = None) -> int:
    """
    Score a post's structural quality from 0-100.

    Args:
        post_text: The full post text
        hashtags: List of hashtags

    Returns:
        Integer score 0-100
    """
    if not post_text:
        return 0

    score = 50  # start at neutral

    # ── Length ────────────────────────────────────
    char_count = len(post_text)

    if 800 <= char_count <= 1200:
        score += 15  # sweet spot
    elif 600 <= char_count < 800:
        score += 8
    elif 1200 < char_count <= 1500:
        score += 5
    elif char_count < 400:
        score -= 15  # too short to be substantive
    elif char_count > 2000:
        score -= 15  # too long, people won't finish

    # ── Paragraph structure ──────────────────────
    paragraphs = [p.strip() for p in post_text.split("\n\n") if p.strip()]
    num_paragraphs = len(paragraphs)

    if num_paragraphs >= 4:
        score += 10  # good chunking
    elif num_paragraphs >= 3:
        score += 5
    elif num_paragraphs <= 1:
        score -= 10  # wall of text

    # Average paragraph length (in words)
    if paragraphs:
        avg_words = sum(len(p.split()) for p in paragraphs) / len(paragraphs)
        if avg_words <= 25:
            score += 8  # nice and scannable
        elif avg_words <= 35:
            score += 3
        elif avg_words > 50:
            score -= 8  # too dense

    # ── Line breaks (single \n within paragraphs) ─
    single_breaks = post_text.count("\n") - post_text.count("\n\n")
    if single_breaks >= 2:
        score += 5  # uses strategic line breaks

    # ── Short punchy lines (1-3 words on their own line)
    lines = [l.strip() for l in post_text.split("\n") if l.strip()]
    punchy_lines = [l for l in lines if 1 <= len(l.split()) <= 3 and not l.startswith("#")]
    if punchy_lines:
        score += min(len(punchy_lines) * 3, 8)  # reward emphasis lines

    # ── Hashtags ─────────────────────────────────
    if hashtags is None:
        hashtags = re.findall(r"#\w+", post_text)

    if 2 <= len(hashtags) <= 3:
        score += 5  # optimal range
    elif len(hashtags) > 5:
        score -= 8  # looks spammy
    elif len(hashtags) == 0:
        score -= 3  # missing discoverability

    # ── No external links in body ────────────────
    if re.search(r"https?://", post_text):
        score -= 10  # LinkedIn penalizes external links

    return max(0, min(100, score))
