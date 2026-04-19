"""
Trend Snapshots — stores topic mention counts between pipeline runs.
Each run saves current counts; the next run compares against them
to detect velocity and acceleration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete

from src.utils.db import get_session, Base
from sqlalchemy import String, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger(__name__)


# ── Database Model ──────────────────────────────────────

class TrendSnapshotDB(Base):
    """Hourly/per-run snapshot of topic mention counts."""

    __tablename__ = "trend_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(50), default="combined")
    mention_count: Mapped[int] = mapped_column(Integer, default=0)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── Dataclass for in-memory use ─────────────────────────

@dataclass
class TopicSnapshot:
    topic: str
    mention_count: int
    source: str = "combined"
    captured_at: datetime | None = None


# ── Storage Functions ───────────────────────────────────

async def init_trend_table():
    """Create the trend_snapshots table if it doesn't exist."""
    from src.utils.db import get_engine
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_snapshot(snapshot: TopicSnapshot) -> None:
    """Save a single topic snapshot to the database."""
    await init_trend_table()
    session = await get_session()
    async with session:
        db_snap = TrendSnapshotDB(
            topic=snapshot.topic,
            source=snapshot.source,
            mention_count=snapshot.mention_count,
            captured_at=snapshot.captured_at or datetime.now(timezone.utc),
        )
        session.add(db_snap)
        await session.commit()


async def save_snapshots_batch(snapshots: list[TopicSnapshot]) -> None:
    """Save multiple snapshots in a single transaction."""
    if not snapshots:
        return
    await init_trend_table()
    session = await get_session()
    async with session:
        for snap in snapshots:
            db_snap = TrendSnapshotDB(
                topic=snap.topic,
                source=snap.source,
                mention_count=snap.mention_count,
                captured_at=snap.captured_at or datetime.now(timezone.utc),
            )
            session.add(db_snap)
        await session.commit()
    logger.debug(f"Saved {len(snapshots)} trend snapshots")


async def get_snapshots(
    hours_back: int = 48,
    source: str | None = None,
) -> list[TopicSnapshot]:
    """
    Retrieve topic snapshots from the last N hours.

    Args:
        hours_back: How far back to look
        source: Filter by source (e.g. 'combined', 'hn')

    Returns:
        List of TopicSnapshot objects, oldest first
    """
    await init_trend_table()
    session = await get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    async with session:
        query = (
            select(TrendSnapshotDB)
            .where(TrendSnapshotDB.captured_at >= cutoff)
            .order_by(TrendSnapshotDB.captured_at.asc())
        )
        if source:
            query = query.where(TrendSnapshotDB.source == source)

        result = await session.execute(query)
        rows = result.scalars().all()

    return [
        TopicSnapshot(
            topic=row.topic,
            mention_count=row.mention_count,
            source=row.source,
            captured_at=row.captured_at,
        )
        for row in rows
    ]


async def get_previous_counts(
    hours_ago_start: int = 12,
    hours_ago_end: int = 24,
) -> dict[str, int]:
    """
    Get aggregated topic counts from a specific time window.
    Used to compare against current counts for velocity calculation.

    Args:
        hours_ago_start: Start of window (e.g. 12 = 12 hours ago)
        hours_ago_end: End of window (e.g. 24 = 24 hours ago)

    Returns:
        Dict of topic → total mention count in that window
    """
    await init_trend_table()
    session = await get_session()
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours_ago_end)
    end = now - timedelta(hours=hours_ago_start)

    async with session:
        query = (
            select(TrendSnapshotDB)
            .where(TrendSnapshotDB.captured_at >= start)
            .where(TrendSnapshotDB.captured_at <= end)
        )
        result = await session.execute(query)
        rows = result.scalars().all()

    counts: dict[str, int] = {}
    for row in rows:
        counts[row.topic] = counts.get(row.topic, 0) + row.mention_count

    return counts


async def cleanup_old_snapshots(keep_hours: int = 72) -> int:
    """Delete snapshots older than keep_hours. Returns count deleted."""
    await init_trend_table()
    session = await get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=keep_hours)

    async with session:
        result = await session.execute(
            delete(TrendSnapshotDB).where(TrendSnapshotDB.captured_at < cutoff)
        )
        await session.commit()
        deleted = result.rowcount

    if deleted:
        logger.info(f"Cleaned up {deleted} old trend snapshots")
    return deleted
