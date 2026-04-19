"""
Post Tracker — records which generated posts the user actually publishes.
Feeds into the autopsy system for performance tracking.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update

from src.utils.db import get_session, GeneratedPost

logger = logging.getLogger(__name__)


async def mark_post_selected(post_id: int, hook_variant: str = "A") -> bool:
    """
    Mark a post as selected by the user for publishing.

    Args:
        post_id: Database ID of the generated post
        hook_variant: Which hook variant was used ("A", "B", or "C")

    Returns:
        True if successfully marked
    """
    session = await get_session()
    try:
        async with session:
            result = await session.execute(
                update(GeneratedPost)
                .where(GeneratedPost.id == post_id)
                .values(
                    was_selected=True,
                )
            )
            await session.commit()

            if result.rowcount > 0:
                logger.info(f"Post {post_id} marked as selected (hook: {hook_variant})")
                return True
            else:
                logger.warning(f"Post {post_id} not found")
                return False

    except Exception as e:
        logger.error(f"Failed to mark post {post_id}: {e}")
        return False


async def get_selected_posts(days: int = 7) -> list[dict]:
    """
    Get all posts selected by the user in the last N days.

    Returns list of dicts with post data.
    """
    session = await get_session()
    cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0
    )

    from datetime import timedelta
    cutoff = cutoff - timedelta(days=days)

    async with session:
        result = await session.execute(
            select(GeneratedPost)
            .where(GeneratedPost.was_selected == True)
            .where(GeneratedPost.created_at >= cutoff)
            .order_by(GeneratedPost.created_at.desc())
        )
        posts = result.scalars().all()

    return [
        {
            "id": p.id,
            "topic": p.topic,
            "angle": p.angle,
            "post_text": p.post_text,
            "virality_score": p.virality_score,
            "source_title": p.source_title,
            "created_at": p.created_at,
        }
        for p in posts
    ]


async def get_pipeline_stats(days: int = 30) -> dict:
    """Get summary statistics of pipeline usage."""
    session = await get_session()

    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session:
        result = await session.execute(
            select(GeneratedPost).where(GeneratedPost.created_at >= cutoff)
        )
        all_posts = result.scalars().all()

    total = len(all_posts)
    selected = sum(1 for p in all_posts if p.was_selected)
    avg_score = (
        sum(p.virality_score for p in all_posts) / total
        if total else 0
    )

    return {
        "total_generated": total,
        "total_selected": selected,
        "selection_rate": selected / total if total else 0,
        "avg_virality_score": avg_score,
        "days": days,
    }