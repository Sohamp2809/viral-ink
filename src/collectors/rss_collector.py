"""
RSS Collector — fetches articles from configured RSS feeds.

Supports any standard RSS/Atom feed. Configurable via config/sources.yaml.
Uses feedparser for robust feed parsing across formats.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp
import feedparser

from src.collectors.base import BaseCollector, ContentItem
from src.utils.config import load_sources

logger = logging.getLogger(__name__)

# feedparser is synchronous, so we run it in a thread
_TIMEOUT = aiohttp.ClientTimeout(total=15)
_HEADERS = {
    "User-Agent": "LinkedInPostPilot/0.1 (+https://github.com/yourname/linkedin-post-pilot)"
}


def _parse_date(entry: dict) -> datetime | None:
    """Extract publication date from a feed entry."""
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                from time import mktime
                return datetime.fromtimestamp(mktime(parsed), tz=timezone.utc)
            except (ValueError, OverflowError):
                continue

    for field in ("published", "updated"):
        raw = entry.get(field, "")
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                continue

    return None


def _extract_summary(entry: dict) -> str:
    """Get the best available summary text from a feed entry."""
    # Try summary first, then content
    summary = entry.get("summary", "")

    # Some feeds put full content in content:encoded
    content_list = entry.get("content", [])
    if content_list and isinstance(content_list, list):
        content = content_list[0].get("value", "")
        if len(content) > len(summary):
            summary = content

    # Strip HTML tags (basic)
    if "<" in summary:
        from html import unescape
        import re
        summary = re.sub(r"<[^>]+>", "", unescape(summary))

    # Truncate to reasonable length
    if len(summary) > 1000:
        summary = summary[:997] + "..."

    return summary.strip()


async def _fetch_feed(session: aiohttp.ClientSession, url: str) -> str | None:
    """Fetch raw feed XML."""
    try:
        async with session.get(url, headers=_HEADERS, timeout=_TIMEOUT) as resp:
            if resp.status == 200:
                return await resp.text()
            logger.warning(f"Feed {url} returned status {resp.status}")
            return None
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


class RSSCollector(BaseCollector):
    """Collects content from RSS/Atom feeds defined in sources.yaml."""

    @property
    def name(self) -> str:
        return "RSS Feeds"

    async def collect(self) -> list[ContentItem]:
        sources = load_sources()
        feeds_config = sources.get("rss_feeds", [])

        if not feeds_config:
            logger.warning("No RSS feeds configured in sources.yaml")
            return []

        items: list[ContentItem] = []

        async with aiohttp.ClientSession() as session:
            # Fetch all feeds concurrently
            tasks = []
            for feed_cfg in feeds_config:
                tasks.append(
                    _fetch_feed(session, feed_cfg["url"])
                )

            results = await asyncio.gather(*tasks)

        # Parse each feed
        for feed_cfg, raw_xml in zip(feeds_config, results):
            if not raw_xml:
                continue

            try:
                # feedparser is sync — run in thread for large feeds
                feed = await asyncio.to_thread(feedparser.parse, raw_xml)
            except Exception as e:
                logger.warning(f"Failed to parse {feed_cfg['name']}: {e}")
                continue

            for entry in feed.entries[:15]:  # cap per feed
                title = entry.get("title", "").strip()
                if not title:
                    continue

                items.append(ContentItem(
                    title=title,
                    summary=_extract_summary(entry),
                    url=entry.get("link", ""),
                    source_name=feed_cfg["name"],
                    category=feed_cfg.get("category", "tech"),
                    published_at=_parse_date(entry),
                    weight=feed_cfg.get("weight", 1.0),
                    metadata={
                        "feed_url": feed_cfg["url"],
                        "author": entry.get("author", ""),
                    },
                ))

        # Deduplicate by URL
        seen_urls: set[str] = set()
        unique: list[ContentItem] = []
        for item in items:
            if item.url and item.url not in seen_urls:
                seen_urls.add(item.url)
                unique.append(item)
            elif not item.url:
                unique.append(item)

        return unique
