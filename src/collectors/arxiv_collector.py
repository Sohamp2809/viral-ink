"""arXiv collector — no API key required."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector, ContentItem, make_id, utcnow
from src.utils.config import load_sources

_API = "https://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _parse_date(s: str | None) -> datetime:
    if not s:
        return utcnow()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return utcnow()


class ArxivCollector(BaseCollector):
    source_type = "arxiv"

    def collect(self) -> list[ContentItem]:
        cfg = load_sources().get("arxiv", {})
        categories = cfg.get("categories", ["cs.AI", "cs.LG", "cs.CL"])
        max_results = cfg.get("max_results", 20)
        max_age_h = cfg.get("max_age_hours", 48)

        query = " OR ".join(f"cat:{c}" for c in categories)
        items: list[ContentItem] = []
        now = utcnow()

        try:
            with httpx.Client(timeout=20) as client:
                resp = client.get(_API, params={
                    "search_query": query,
                    "sortBy": "lastUpdatedDate",
                    "sortOrder": "descending",
                    "max_results": max_results,
                })
                resp.raise_for_status()

            root = ET.fromstring(resp.text)
            for entry in root.findall("atom:entry", _NS):
                title_el = entry.find("atom:title", _NS)
                summary_el = entry.find("atom:summary", _NS)
                updated_el = entry.find("atom:updated", _NS)
                id_el = entry.find("atom:id", _NS)

                url = (id_el.text or "").strip() if id_el is not None else ""
                title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
                summary = (summary_el.text or "").strip().replace("\n", " ")[:400] if summary_el is not None else ""
                pub = _parse_date(updated_el.text if updated_el is not None else None)

                age_h = (now - pub).total_seconds() / 3600
                if age_h > max_age_h or not url or not title:
                    continue

                # Extract author tags
                authors = [
                    (a.find("atom:name", _NS).text or "").strip()
                    for a in entry.findall("atom:author", _NS)
                    if a.find("atom:name", _NS) is not None
                ][:3]

                items.append(ContentItem(
                    id=make_id(url),
                    title=title,
                    url=url,
                    source="arXiv",
                    source_type="arxiv",
                    published_at=pub,
                    summary=summary,
                    tags=["ai_research"] + authors,
                    score_breakdown={"source_quality": 0.85},
                ))

        except Exception as exc:
            print(f"[arXiv] {exc}")

        return items
