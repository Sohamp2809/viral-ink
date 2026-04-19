"""Product Hunt scraper (no API key needed for public posts)."""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, ContentItem, make_id, utcnow
from src.utils.config import load_sources

_URL = "https://www.producthunt.com"


class ProductHuntCollector(BaseCollector):
    source_type = "producthunt"

    def collect(self) -> list[ContentItem]:
        cfg = load_sources().get("producthunt", {})
        max_items = cfg.get("max_items", 15)
        now = utcnow()
        items: list[ContentItem] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html",
        }

        try:
            with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = client.get(_URL)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Product Hunt renders mostly with JS, but server-side HTML has basic data
            for item_el in soup.select("section[data-test='homepage-section-0'] li")[:max_items]:
                link_el = item_el.find("a", href=True)
                if not link_el:
                    continue
                href = link_el["href"]
                if not href.startswith("/posts/"):
                    continue
                url = f"{_URL}{href}"
                title_el = item_el.find("strong") or item_el.find("h3") or item_el.find("h2")
                title = title_el.get_text(strip=True) if title_el else href.split("/")[-1]
                tagline_el = item_el.find("span", {"class": lambda c: c and "tagline" in c.lower()})
                summary = tagline_el.get_text(strip=True) if tagline_el else ""

                items.append(ContentItem(
                    id=make_id(url),
                    title=title,
                    url=url,
                    source="Product Hunt",
                    source_type="producthunt",
                    published_at=now,
                    summary=summary[:300],
                    tags=["producthunt"],
                    score_breakdown={"source_quality": 0.75},
                ))

        except Exception as exc:
            print(f"[ProductHunt] {exc}")

        return items
