"""
Scheduler — runs the pipeline automatically at a configured time daily.
Uses APScheduler for cross-platform cron-like scheduling.
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.utils.config import get_settings

logger = logging.getLogger(__name__)


async def _scheduled_run():
    """The function that runs on schedule."""
    from src.main import run_pipeline
    from src.delivery.sender import send_daily_email

    logger.info("Scheduled pipeline starting...")

    try:
        posts = await run_pipeline()

        if posts:
            # Send email
            # Trends were already computed in the pipeline,
            # but we pass empty list since email_builder handles it gracefully
            await send_daily_email(posts, [])

    except Exception as e:
        logger.error(f"Scheduled pipeline failed: {e}", exc_info=True)


def start_scheduler(
    hour: int | None = None,
    minute: int | None = None,
    timezone_str: str | None = None,
):
    """
    Start the daily scheduler.

    Args:
        hour: Hour to run (24h format, default from .env)
        minute: Minute to run (default from .env)
        timezone_str: Timezone string (default from .env)
    """
    settings = get_settings()

    if hour is None:
        hour = getattr(settings, "pipeline_hour", 5)
    if minute is None:
        minute = getattr(settings, "pipeline_minute", 0)
    if timezone_str is None:
        timezone_str = getattr(settings, "timezone", "UTC")

    scheduler = AsyncIOScheduler()

    trigger = CronTrigger(
        hour=hour,
        minute=minute,
        timezone=timezone_str,
    )

    scheduler.add_job(
        _scheduled_run,
        trigger=trigger,
        id="daily_pipeline",
        name="Daily LinkedIn Post Pipeline",
        replace_existing=True,
    )

    delivery_time = f"{hour:02d}:{minute:02d}"
    email_time = f"{hour + 2:02d}:{minute:02d}" if hour + 2 < 24 else f"{(hour + 2) % 24:02d}:{minute:02d}"

    logger.info(f"Scheduler started — pipeline runs daily at {delivery_time} {timezone_str}")
    logger.info(f"Email delivery expected by ~{email_time} {timezone_str}")

    scheduler.start()

    # Keep alive
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")
        scheduler.shutdown()