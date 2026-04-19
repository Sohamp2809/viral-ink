"""
Base collector interface — every content source implements this.

Adding a new source? Create a new file, subclass BaseCollector, implement collect().
That's it. The pipeline discovers all collectors automatically.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ContentItem:
    """A single piece of collected content — article, post, paper, etc."""

    title: str
    summary: str = ""
    content: str = ""
    url: str = ""
    source_name: str = ""
    category: str = "tech"
    published_at: datetime | None = None
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)

    @property
    def age_hours(self) -> float:
        """Hours since publication."""
        if not self.published_at:
            return 48.0  # assume 2 days if unknown
        pub = self.published_at
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - pub
        return max(0.0, delta.total_seconds() / 3600)

    @property
    def display_text(self) -> str:
        """Best available text for processing."""
        return self.summary or self.content[:500] or self.title


class BaseCollector(ABC):
    """
    Abstract base for all content collectors.

    Subclasses must implement:
        name: str property
        collect() -> list[ContentItem]
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this collector."""
        ...

    @abstractmethod
    async def collect(self) -> list[ContentItem]:
        """
        Fetch content from this source.

        Returns a list of ContentItem objects. Should handle its own errors
        gracefully — a failing collector should not crash the pipeline.
        """
        ...

    async def safe_collect(self) -> list[ContentItem]:
        """
        Wrapper that catches errors so one broken source doesn't kill the pipeline.
        """
        try:
            items = await self.collect()
            logger.info(f"[{self.name}] Collected {len(items)} items")
            return items
        except Exception as e:
            logger.error(f"[{self.name}] Collection failed: {e}")
            return []
