"""
LinkedIn Performance Scraper — extracts engagement metrics from published posts.

Three modes:
  1. MANUAL — user enters metrics via CLI (always works)
  2. COOKIE — scrape your own LinkedIn profile with session cookies
  3. API — use LinkedIn API with OAuth (requires approved app)

Mode 1 is the default and most reliable. Modes 2-3 are optional
enhancements for users who want full automation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class PostMetrics:
    """Raw engagement metrics from a LinkedIn post."""
    reactions: int = 0
    comments: int = 0
    shares: int = 0
    impressions: int = 0
    post_url: str = ""
    scraped_at: datetime | None = None

    @property
    def total_engagement(self) -> int:
        return self.reactions + self.comments + self.shares

    @property
    def has_data(self) -> bool:
        return self.total_engagement > 0


def metrics_from_manual(
    reactions: int = 0,
    comments: int = 0,
    shares: int = 0,
    impressions: int = 0,
    post_url: str = "",
) -> PostMetrics:
    """Create metrics from manual user input (CLI or API)."""
    return PostMetrics(
        reactions=reactions,
        comments=comments,
        shares=shares,
        impressions=impressions,
        post_url=post_url,
        scraped_at=datetime.now(timezone.utc),
    )


async def scrape_profile_posts(
    profile_url: str = "",
    cookies: dict | None = None,
    max_posts: int = 5,
) -> list[PostMetrics]:
    """
    Scrape recent post metrics from a LinkedIn profile page.

    This is OPTIONAL and requires LinkedIn session cookies.
    Falls back gracefully if scraping fails.

    Args:
        profile_url: LinkedIn profile URL
        cookies: LinkedIn session cookies (li_at, JSESSIONID)
        max_posts: Maximum number of recent posts to scrape

    Returns:
        List of PostMetrics for recent posts
    """
    if not cookies or not cookies.get("li_at"):
        logger.info(
            "LinkedIn scraping requires session cookies. "
            "Use manual input instead: pilot autopsy <id> -r <reactions> -c <comments>"
        )
        return []

    try:
        import aiohttp

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }

        cookie_jar = aiohttp.CookieJar()
        async with aiohttp.ClientSession(
            headers=headers,
            cookie_jar=cookie_jar,
        ) as session:
            # Set LinkedIn cookies
            for name, value in cookies.items():
                cookie_jar.update_cookies({name: value})

            async with session.get(
                profile_url,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"LinkedIn returned status {resp.status}")
                    return []

                html = await resp.text()

        # Parse engagement numbers from HTML
        metrics = _parse_linkedin_html(html, max_posts)
        logger.info(f"Scraped {len(metrics)} posts from LinkedIn profile")
        return metrics

    except ImportError:
        logger.warning("aiohttp required for LinkedIn scraping")
        return []
    except Exception as e:
        logger.warning(f"LinkedIn scraping failed: {e}")
        return []


def _parse_linkedin_html(html: str, max_posts: int = 5) -> list[PostMetrics]:
    """
    Extract post metrics from LinkedIn profile HTML.

    Note: LinkedIn frequently changes their HTML structure.
    This parser handles common patterns but may need updates.
    """
    metrics_list = []

    # Pattern: look for reaction counts in common LinkedIn HTML patterns
    # These patterns may need updating as LinkedIn changes their markup
    reaction_patterns = [
        r'(\d+)\s*(?:reactions?|likes?)',
        r'(\d+)\s*(?:comments?)',
        r'(\d+)\s*(?:reposts?|shares?)',
    ]

    # Simple extraction — LinkedIn's actual HTML is heavily obfuscated
    # This works with basic profile pages but not SPAs
    for pattern in reaction_patterns:
        matches = re.findall(pattern, html, re.IGNORECASE)
        if matches and len(metrics_list) < max_posts:
            for match in matches[:max_posts]:
                try:
                    count = int(match)
                    # We can't reliably map these to specific posts
                    # from HTML alone — this is a best-effort extraction
                    metrics_list.append(PostMetrics(
                        reactions=count,
                        scraped_at=datetime.now(timezone.utc),
                    ))
                except ValueError:
                    continue

    return metrics_list[:max_posts]


def match_post_to_metrics(
    post_text: str,
    metrics_list: list[PostMetrics],
    threshold: float = 0.5,
) -> PostMetrics | None:
    """
    Match a generated post to scraped metrics by text similarity.
    Uses simple word overlap since we don't want heavy NLP deps.

    Args:
        post_text: The generated post text
        metrics_list: Scraped metrics to search through
        threshold: Minimum similarity score (0-1)

    Returns:
        Best matching PostMetrics, or None if no good match
    """
    if not metrics_list:
        return None

    post_words = set(post_text.lower().split())

    best_match = None
    best_score = 0.0

    for metrics in metrics_list:
        # This requires that scraped metrics include post text
        # For manual input, matching isn't needed
        if not hasattr(metrics, "post_text_snippet"):
            continue

        snippet_words = set(getattr(metrics, "post_text_snippet", "").lower().split())
        if not snippet_words:
            continue

        overlap = len(post_words & snippet_words)
        score = overlap / max(len(post_words), len(snippet_words))

        if score > best_score and score >= threshold:
            best_score = score
            best_match = metrics

    return best_match
