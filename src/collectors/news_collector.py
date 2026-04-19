"""
News API Collector — fetches breaking tech news from NewsAPI.org.

Free tier: 100 requests/day. We use ~5 per run (one per query keyword).
Get your key at https://newsapi.org/register
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import aiohttp

from src.collectors.base import BaseCollector, ContentItem
from src.utils.config import get_settings, load_sources

logger = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2/everything"
_TIMEOUT = aiohttp.ClientTimeout(total=15)


class NewsCollector(BaseCollector):
    """Collects breaking tech news from NewsAPI.org."""

    @property
    def name(self) -> str:
        return "NewsAPI"

    async def collect(self) -> list[ContentItem]:
        api_key = get_settings().newsapi_key
        if not api_key or api_key == "your_newsapi_key_here":
            logger.warning("NewsAPI key not configured — skipping news collection")
            return []

        sources = load_sources()
        news_cfg = sources.get("news_api", {})
        queries = news_cfg.get("queries", ["artificial intelligence"])
        page_size = news_cfg.get("page_size", 20)
        language = news_cfg.get("language", "en")

        # Only fetch last 48 hours
        from_date = (datetime.now(timezone.utc) - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

        items: list[ContentItem] = []

        async with aiohttp.ClientSession() as session:
            for query in queries:
                try:
                    params = {
                        "q": query,
                        "from": from_date,
                        "sortBy": "relevancy",
                        "language": language,
                        "pageSize": min(page_size, 20),
                        "apiKey": api_key,
                    }

                    async with session.get(
                        NEWSAPI_BASE, params=params, timeout=_TIMEOUT
                    ) as resp:
                        if resp.status != 200:
                            body = await resp.text()
                            logger.warning(f"NewsAPI error for '{query}': {resp.status} — {body[:200]}")
                            continue

                        data = await resp.json()

                    articles = data.get("articles", [])
                    logger.debug(f"NewsAPI '{query}': {len(articles)} articles")

                    for article in articles:
                        title = (article.get("title") or "").strip()
                        # Skip removed/placeholder articles
                        if not title or "[Removed]" in title:
                            continue

                        published_at = None
                        raw_date = article.get("publishedAt", "")
                        if raw_date:
                            try:
                                published_at = datetime.fromisoformat(
                                    raw_date.replace("Z", "+00:00")
                                )
                            except ValueError:
                                pass

                        description = (article.get("description") or "").strip()
                        content = (article.get("content") or "").strip()
                        # NewsAPI truncates content at ~200 chars — prefer description
                        summary = description or content

                        items.append(ContentItem(
                            title=title,
                            summary=summary,
                            url=article.get("url", ""),
                            source_name=f"NewsAPI ({article.get('source', {}).get('name', 'Unknown')})",
                            category="tech",
                            published_at=published_at,
                            weight=1.0,
                            metadata={
                                "query": query,
                                "source_id": article.get("source", {}).get("id", ""),
                                "author": article.get("author", ""),
                                "image_url": article.get("urlToImage", ""),
                            },
                        ))

                except Exception as e:
                    logger.warning(f"NewsAPI query '{query}' failed: {e}")
                    continue

        # Deduplicate by URL
        seen: set[str] = set()
        unique: list[ContentItem] = []
        for item in items:
            if item.url and item.url not in seen:
                seen.add(item.url)
                unique.append(item)

        return unique
