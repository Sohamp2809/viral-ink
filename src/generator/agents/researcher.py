"""
Researcher Agent — analyzes the context window and selects
the best content opportunities with specific angles.

Uses the cheap LLM (Haiku/GPT-4o-mini) since this is analysis, not writing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.collectors.base import ContentItem
from src.generator.prompts.researcher_prompt import RESEARCHER_SYSTEM, RESEARCHER_PROMPT
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class ContentBrief:
    """A content opportunity selected by the researcher."""
    source_index: int = 0
    source_title: str = ""
    source_url: str = ""
    source_summary: str = ""
    topic: str = ""
    angle: str = ""
    thesis: str = ""
    why_it_works: str = ""
    confidence: str = "MEDIUM"


async def research(
    context_window: str,
    voice_summary: str,
    n_posts: int = 7,
    llm: BaseLLM | None = None,
    memory_summary: str = "No content memory yet — all topics are available.",
) -> list[ContentBrief]:
    """
    Analyze context and select the best content opportunities.

    Args:
        context_window: Formatted string of today's collected content
        voice_summary: Brief description of user's voice/expertise
        n_posts: Number of opportunities to select
        llm: Cheap LLM instance (Haiku/GPT-4o-mini)
        memory_summary: Summary of recently covered topics

    Returns:
        List of ContentBrief objects for the writer
    """
    if llm is None:
        from src.utils.llm import get_cheap_llm
        llm = get_cheap_llm()

    min_angles = min(5, n_posts)

    prompt = RESEARCHER_PROMPT.format(
        n_posts=n_posts,
        context_window=context_window,
        voice_summary=voice_summary or "Tech professional with strong opinions on AI and engineering.",
        memory_summary=memory_summary,
        min_angles=min_angles,
    )

    logger.info(f"Researcher analyzing context for {n_posts} opportunities...")

    try:
        result = await llm.generate(
            prompt=prompt,
            system=RESEARCHER_SYSTEM,
            max_tokens=4000,
            temperature=0.6,
        )

        briefs_data = _parse_briefs(result.text)
        logger.info(f"Researcher selected {len(briefs_data)} opportunities")
        logger.debug(f"Researcher tokens: {result.input_tokens} in / {result.output_tokens} out")

    except Exception as e:
        logger.error(f"Researcher failed: {e}")
        return []

    briefs = []
    for data in briefs_data[:n_posts]:
        briefs.append(ContentBrief(
            source_index=data.get("source_index", 0),
            source_title=data.get("source_title", ""),
            source_url=data.get("source_url", ""),
            topic=data.get("topic", ""),
            angle=data.get("angle", "hot_take"),
            thesis=data.get("thesis", ""),
            why_it_works=data.get("why_it_works", ""),
            confidence=data.get("confidence", "MEDIUM"),
        ))

    # Validate angle diversity
    angles_used = [b.angle for b in briefs]
    unique_angles = set(angles_used)
    if len(unique_angles) < min_angles and len(briefs) >= min_angles:
        logger.warning(
            f"Researcher only used {len(unique_angles)} angles "
            f"(minimum {min_angles}). Consider re-running."
        )

    return briefs


def _parse_briefs(text: str) -> list[dict]:
    """Robustly parse researcher JSON output."""
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "opportunities" in result:
            return result["opportunities"]
        return [result]
    except json.JSONDecodeError:
        pass

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Could not parse researcher output")
    return []
