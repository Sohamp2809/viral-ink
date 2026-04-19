"""
Memory Updater — feeds autopsy results back into the content memory graph.

After enough autopsies, we know which TOPICS perform well for this user.
This module updates the memory nodes so the context engine can:
- Boost topics that historically perform well
- Avoid topics that consistently underperform
- Track which topic + angle combos have been exhausted
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from src.utils.db import get_session, MemoryNode, Base

logger = logging.getLogger(__name__)


async def update_memory_from_autopsies(days: int = 60) -> int:
    """
    Scan autopsy reports and update memory nodes with performance data.

    For each topic that has autopsy data:
    - Updates avg_performance with actual engagement scores
    - Tracks which angles have been used
    - Marks high-performing topics for priority

    Returns:
        Number of memory nodes updated
    """
    from src.autopsy.report_builder import AutopsyReport
    from src.utils.db import get_engine

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session:
        # Get autopsy reports
        result = await session.execute(
            select(AutopsyReport).where(AutopsyReport.analyzed_at >= cutoff)
        )
        reports = result.scalars().all()

        if not reports:
            logger.info("No autopsy data to update memory with")
            return 0

        # Group by topic
        topic_data: dict[str, dict] = {}
        for r in reports:
            topic = r.topic.strip().lower()
            if not topic:
                continue

            if topic not in topic_data:
                topic_data[topic] = {
                    "scores": [],
                    "angles": set(),
                    "reactions": [],
                    "last_used": r.analyzed_at,
                }

            topic_data[topic]["scores"].append(r.actual_score)
            topic_data[topic]["angles"].add(r.angle)
            topic_data[topic]["reactions"].append(r.reactions)

            if r.analyzed_at and r.analyzed_at > topic_data[topic]["last_used"]:
                topic_data[topic]["last_used"] = r.analyzed_at

        # Update or create memory nodes
        updated = 0
        for topic, data in topic_data.items():
            avg_perf = sum(data["scores"]) / len(data["scores"])

            # Check if node exists
            result = await session.execute(
                select(MemoryNode).where(MemoryNode.topic == topic)
            )
            node = result.scalar_one_or_none()

            if node:
                # Update existing
                node.avg_performance = avg_perf
                node.times_covered = len(data["scores"])
                node.angles_used = list(data["angles"])
                node.last_covered = data["last_used"]
            else:
                # Create new
                node = MemoryNode(
                    topic=topic,
                    category="",
                    times_covered=len(data["scores"]),
                    last_covered=data["last_used"],
                    angles_used=list(data["angles"]),
                    avg_performance=avg_perf,
                )
                session.add(node)

            updated += 1

        await session.commit()

    logger.info(f"Updated {updated} memory nodes from autopsy data")
    return updated


async def get_topic_performance(min_autopsies: int = 2) -> dict[str, float]:
    """
    Get average performance scores per topic.
    Only includes topics with enough autopsy data.

    Returns:
        Dict of topic → average actual engagement score
    """
    from src.autopsy.report_builder import AutopsyReport
    from src.utils.db import get_engine

    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()

    async with session:
        result = await session.execute(select(AutopsyReport))
        reports = result.scalars().all()

    topic_scores: dict[str, list[float]] = {}
    for r in reports:
        topic = r.topic.strip().lower()
        if topic:
            topic_scores.setdefault(topic, []).append(r.actual_score)

    return {
        topic: sum(scores) / len(scores)
        for topic, scores in topic_scores.items()
        if len(scores) >= min_autopsies
    }
