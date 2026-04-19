"""GitHub trending scraper (no API key needed)."""
from __future__ import annotations


import httpx
from bs4 import BeautifulSoup

from src.collectors.base import BaseCollector, ContentItem, make_id, utcnow
from src.utils.config import load_sources

_BASE = "https://github.com/trending"


class GitHubCollector(BaseCollector):
    source_type = "github"

    def collect(self) -> list[ContentItem]:
        cfg = load_sources().get("github", {})
        since = cfg.get("since", "daily")
        languages = cfg.get("languages", ["", "python"])
        max_items = cfg.get("max_items", 15)

        items: list[ContentItem] = []
        seen: set[str] = set()
        now = utcnow()

        headers = {"Accept": "text/html", "User-Agent": "linkedin-post-pilot/0.1"}

        with httpx.Client(timeout=15, headers=headers, follow_redirects=True) as client:
            for lang in languages:
                if len(items) >= max_items:
                    break
                try:
                    params = {"since": since}
                    if lang:
                        params["spoken_language_code"] = ""
                        url = f"{_BASE}/{lang}"
                    else:
                        url = _BASE

                    resp = client.get(url, params={"since": since})
                    resp.raise_for_status()
                    soup = BeautifulSoup(resp.text, "html.parser")

                    for repo_el in soup.select("article.Box-row"):
                        h2 = repo_el.find("h2")
                        if not h2:
                            continue
                        link_el = h2.find("a")
                        if not link_el:
                            continue
                        path = link_el.get("href", "").strip("/")
                        repo_url = f"https://github.com/{path}"
                        if repo_url in seen:
                            continue
                        seen.add(repo_url)

                        title = path.replace("/", " / ")
                        desc_el = repo_el.find("p")
                        summary = (desc_el.get_text(strip=True) if desc_el else "")[:300]

                        items.append(ContentItem(
                            id=make_id(repo_url),
                            title=title,
                            url=repo_url,
                            source="GitHub Trending",
                            source_type="github",
                            published_at=now,  # trending doesn't expose publish date
                            summary=summary,
                            tags=["github", lang or "all"],
                            score_breakdown={"source_quality": 0.8},
                        ))
                        if len(items) >= max_items:
                            break
                except Exception as exc:
                    print(f"[GitHub] lang={lang!r}: {exc}")

        return items
