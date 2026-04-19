"""
Topic Tracker — extracts topic keywords from collected content,
counts mentions across time windows, and computes trend momentum.

Works with data the agent already collects (RSS, news) — no extra APIs needed.
Optionally enhanced with HN point counts and Google Trends data.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import datetime, timezone

from src.collectors.base import ContentItem
from src.collectors.trend_radar.momentum import TrendScore, compute_momentum
from src.collectors.trend_radar.snapshots import (
    save_snapshot,
    TopicSnapshot,
)

logger = logging.getLogger(__name__)

# Common words to ignore when extracting topics
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "under", "about",
    "up", "out", "off", "over", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "just", "because", "but", "and", "or", "if", "while",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "it", "its", "my", "your", "his", "her", "our", "their",
    "new", "says", "said", "also", "get", "gets", "got", "like",
    "one", "two", "first", "last", "now", "still", "even", "back",
    "make", "makes", "made", "way", "much", "many", "well", "part",
    "take", "takes", "use", "uses", "used", "want", "wants", "need",
    "needs", "help", "helps", "show", "shows", "work", "works",
}

# Known tech topic patterns to boost detection
TECH_PATTERNS = [
    r"\bAI\b", r"\bartificial intelligence\b", r"\bmachine learning\b",
    r"\bLLM\b", r"\bGPT[\s-]?\w*\b", r"\bClaude\b", r"\bGemini\b",
    r"\bopen[\s-]?source\b", r"\bstartup\b", r"\bfunding\b",
    r"\bseries [A-Z]\b", r"\bIPO\b", r"\bacquisition\b",
    r"\bcybersecurity\b", r"\bdata privacy\b", r"\bblockchain\b",
    r"\bkubernetes\b", r"\bdevops\b", r"\bcloud\b",
    r"\bself[\s-]?hosted\b", r"\bRAG\b", r"\bvector database\b",
    r"\btransformer\b", r"\bfine[\s-]?tun\w*\b", r"\breasoning\b",
    r"\bagent\w*\b", r"\brobotics\b", r"\bautonomous\b",
]


def extract_topics(items: list[ContentItem], max_topics: int = 30) -> Counter:
    """
    Extract topic keywords from article titles and summaries.
    Returns a Counter of topic → mention count.
    """
    topic_counts: Counter = Counter()

    for item in items:
        text = f"{item.title} {item.summary[:200]}".lower()

        # Extract known tech patterns
        for pattern in TECH_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                normalized = match.strip().lower()
                topic_counts[normalized] += 1

        # Extract capitalized multi-word phrases (likely proper nouns / products)
        original_text = f"{item.title} {item.summary[:200]}"
        phrases = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+", original_text)
        for phrase in phrases:
            if len(phrase) > 4 and phrase.lower() not in STOP_WORDS:
                topic_counts[phrase.lower()] += 1

        # Extract significant bigrams from title
        words = [
            w.lower().strip(".,;:!?\"'()[]")
            for w in item.title.split()
            if len(w) > 2 and w.lower() not in STOP_WORDS
        ]
        for i in range(len(words) - 1):
            bigram = f"{words[i]} {words[i+1]}"
            if len(bigram) > 5:
                topic_counts[bigram] += 1

    # Filter: keep topics with 2+ mentions
    filtered = Counter({
        topic: count for topic, count in topic_counts.items()
        if count >= 2
    })

    return Counter(dict(filtered.most_common(max_topics)))


async def compute_trends(
    current_items: list[ContentItem],
    previous_items: list[ContentItem] | None = None,
    older_items: list[ContentItem] | None = None,
) -> list[TrendScore]:
    """
    Compute trend momentum for all detected topics.

    Args:
        current_items: Articles from the latest collection (last 12h)
        previous_items: Articles from the prior window (12-24h ago), or None
        older_items: Articles from the oldest window (24-48h ago), or None

    Returns:
        List of TrendScore objects, sorted by momentum (highest first)
    """
    current_topics = extract_topics(current_items)

    previous_topics = extract_topics(previous_items) if previous_items else Counter()
    older_topics = extract_topics(older_items) if older_items else Counter()

    # Compute momentum for each topic
    all_topics = set(current_topics.keys()) | set(previous_topics.keys())
    trends: list[TrendScore] = []

    for topic in all_topics:
        current = current_topics.get(topic, 0)
        previous = previous_topics.get(topic, 0)
        older = older_topics.get(topic, 0)

        # Skip topics with no current mentions
        if current == 0:
            continue

        score = compute_momentum(
            topic=topic,
            current_mentions=current,
            previous_mentions=previous,
            older_mentions=older,
        )

        trends.append(score)

    # Sort by momentum (highest first)
    trends.sort(key=lambda t: t.momentum, reverse=True)

    # Save snapshots for next run's comparison
    now = datetime.now(timezone.utc)
    for topic, count in current_topics.items():
        await save_snapshot(TopicSnapshot(
            topic=topic,
            mention_count=count,
            source="combined",
            captured_at=now,
        ))

    logger.info(
        f"Trend radar: {len(trends)} topics tracked, "
        f"{sum(1 for t in trends if t.phase == 'EMERGING')} emerging, "
        f"{sum(1 for t in trends if t.phase == 'PEAKING')} peaking"
    )

    return trends


def format_trend_radar(trends: list[TrendScore], max_display: int = 8) -> str:
    """Format trend data for display and context injection."""
    if not trends:
        return "No trend data available yet. Trends will appear after multiple collection runs."

    lines = ["TREND RADAR — Today's topic momentum:"]

    for trend in trends[:max_display]:
        lines.append(f"  {trend.display}")

    emerging = [t for t in trends if t.phase == "EMERGING"]
    if emerging:
        lines.append(f"\n  → {len(emerging)} EMERGING topics detected — prioritize these!")

    return "\n".join(lines)


def apply_trend_weights(
    items: list[ContentItem],
    trends: list[TrendScore],
) -> list[ContentItem]:
    """
    Boost or penalize content items based on trend phase.
    EMERGING topics get 2x weight, SATURATED get 0.5x.
    """
    # Build topic → TrendScore lookup
    trend_map: dict[str, TrendScore] = {}
    for trend in trends:
        trend_map[trend.topic.lower()] = trend

    for item in items:
        title_lower = item.title.lower()
        summary_lower = (item.summary[:200]).lower()
        text = f"{title_lower} {summary_lower}"

        best_multiplier = 1.0
        matched_trend = None

        for topic, trend in trend_map.items():
            if topic in text:
                if trend.weight_multiplier > best_multiplier:
                    best_multiplier = trend.weight_multiplier
                    matched_trend = trend
                elif trend.weight_multiplier < 1.0 and best_multiplier == 1.0:
                    best_multiplier = trend.weight_multiplier
                    matched_trend = trend

        if matched_trend:
            item.weight *= best_multiplier
            item.metadata["trend_phase"] = matched_trend.phase
            item.metadata["trend_momentum"] = matched_trend.momentum
            logger.debug(
                f"  Trend weight: {item.title[:50]} "
                f"→ {matched_trend.phase} ({best_multiplier}x)"
            )

    return items
