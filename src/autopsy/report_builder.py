"""
Post Autopsy — analyzes how published posts actually performed
and generates learning insights to improve future generation.

The autopsy compares predicted virality vs actual engagement,
identifies what worked and what didn't, and feeds data back
into the scoring engine and persona profile.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.utils.llm import BaseLLM
from src.utils.db import get_session, GeneratedPost, Base
from sqlalchemy import String, Integer, Float, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger(__name__)


# ── Database Model ──────────────────────────────────────

class AutopsyReport(Base):
    """Stored autopsy result for a published post."""

    __tablename__ = "autopsy_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer)
    post_text: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(255), default="")
    angle: Mapped[str] = mapped_column(String(50), default="")
    predicted_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Actual performance (entered manually or scraped)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    actual_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Analysis
    prediction_error: Mapped[float] = mapped_column(Float, default=0.0)
    what_worked: Mapped[str] = mapped_column(Text, default="")
    what_didnt: Mapped[str] = mapped_column(Text, default="")
    lesson: Mapped[str] = mapped_column(Text, default="")
    analysis_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── In-Memory Report ───────────────────────────────────

@dataclass
class PostAutopsy:
    """Analysis of a single post's performance."""
    post_id: int
    topic: str
    angle: str
    predicted_score: float
    actual_score: float
    prediction_error: float
    reactions: int = 0
    comments: int = 0
    shares: int = 0
    impressions: int = 0
    what_worked: str = ""
    what_didnt: str = ""
    lesson: str = ""
    hook_used: str = ""


AUTOPSY_PROMPT = """Analyze this LinkedIn post's performance and explain why it performed the way it did.

POST TEXT:
{post_text}

TOPIC: {topic} | ANGLE: {angle}
PREDICTED VIRALITY: {predicted}%
ACTUAL PERFORMANCE:
- Reactions: {reactions}
- Comments: {comments}
- Shares: {shares}
- Impressions: {impressions}
- Computed engagement score: {actual_score}%

Was the prediction accurate? If not, what did the scoring model miss?

Return JSON:
{{
  "what_worked": "<specific elements that drove engagement — be concrete>",
  "what_didnt": "<specific weaknesses — be concrete>",
  "lesson": "<one actionable lesson for future posts>",
  "hook_assessment": "<was the opening strong enough? what would be better>",
  "angle_assessment": "<was this the right angle for this topic?>"
}}"""


def compute_engagement_score(
    reactions: int, comments: int, shares: int, impressions: int
) -> float:
    """
    Convert raw engagement metrics into a 0-100 score.
    Uses weighted engagement rate normalized to LinkedIn averages.
    """
    if impressions <= 0:
        # No impression data — estimate from reactions
        if reactions == 0:
            return 0.0
        # Rough estimate: typical post gets 3-5% engagement rate
        estimated_impressions = reactions * 25
        impressions = max(estimated_impressions, 1)

    # Weighted engagement
    engagement = (reactions * 1.0) + (comments * 3.0) + (shares * 5.0)
    rate = engagement / impressions

    # Normalize: 2% = average (50), 5% = good (75), 10%+ = excellent (95)
    if rate >= 0.10:
        return min(100, 90 + (rate - 0.10) * 100)
    elif rate >= 0.05:
        return 70 + (rate - 0.05) * 400
    elif rate >= 0.02:
        return 40 + (rate - 0.02) * 1000
    else:
        return max(0, rate * 2000)


async def create_autopsy(
    post_id: int,
    reactions: int,
    comments: int,
    shares: int = 0,
    impressions: int = 0,
    llm: BaseLLM | None = None,
) -> PostAutopsy | None:
    """
    Create an autopsy report for a published post.

    Args:
        post_id: Database ID of the generated post
        reactions: LinkedIn reaction count
        comments: Comment count
        shares: Share/repost count
        impressions: Impression count (0 if unknown)
        llm: Cheap LLM for analysis

    Returns:
        PostAutopsy with insights, or None if post not found
    """
    # Load the post from database
    session = await get_session()
    async with session:
        from sqlalchemy import select
        result = await session.execute(
            select(GeneratedPost).where(GeneratedPost.id == post_id)
        )
        post = result.scalar_one_or_none()

    if not post:
        logger.error(f"Post {post_id} not found")
        return None

    actual_score = compute_engagement_score(reactions, comments, shares, impressions)
    predicted = post.virality_score
    error = predicted - actual_score

    autopsy = PostAutopsy(
        post_id=post_id,
        topic=post.topic,
        angle=post.angle,
        predicted_score=predicted,
        actual_score=actual_score,
        prediction_error=error,
        reactions=reactions,
        comments=comments,
        shares=shares,
        impressions=impressions,
    )

    # LLM analysis
    if llm is None:
        from src.utils.llm import get_cheap_llm
        llm = get_cheap_llm()

    try:
        prompt = AUTOPSY_PROMPT.format(
            post_text=post.post_text,
            topic=post.topic,
            angle=post.angle,
            predicted=predicted,
            reactions=reactions,
            comments=comments,
            shares=shares,
            impressions=impressions,
            actual_score=f"{actual_score:.0f}",
        )

        result = await llm.generate_json(prompt)

        autopsy.what_worked = result.get("what_worked", "")
        autopsy.what_didnt = result.get("what_didnt", "")
        autopsy.lesson = result.get("lesson", "")

    except Exception as e:
        logger.warning(f"LLM autopsy analysis failed: {e}")
        autopsy.what_worked = "Analysis unavailable"
        autopsy.what_didnt = "Analysis unavailable"
        autopsy.lesson = "Analysis unavailable"

    # Save to database
    await _save_autopsy(autopsy, post.post_text)

    logger.info(
        f"Autopsy: {post.topic} — predicted {predicted:.0f}% vs actual {actual_score:.0f}% "
        f"(error: {error:+.0f})"
    )

    return autopsy


async def _save_autopsy(autopsy: PostAutopsy, post_text: str) -> None:
    """Persist autopsy to database."""
    from src.utils.db import get_engine
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    async with session:
        report = AutopsyReport(
            post_id=autopsy.post_id,
            post_text=post_text,
            topic=autopsy.topic,
            angle=autopsy.angle,
            predicted_score=autopsy.predicted_score,
            reactions=autopsy.reactions,
            comments=autopsy.comments,
            shares=autopsy.shares,
            impressions=autopsy.impressions,
            actual_score=autopsy.actual_score,
            prediction_error=autopsy.prediction_error,
            what_worked=autopsy.what_worked,
            what_didnt=autopsy.what_didnt,
            lesson=autopsy.lesson,
        )
        session.add(report)
        await session.commit()