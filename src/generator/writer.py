"""
Writer — generates LinkedIn posts from collected content + persona DNA.

Phase 1: Single-agent generation with persona injection.
Phase 2 will upgrade this to multi-agent (researcher → writer → critic).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.collectors.base import ContentItem
from src.generator.prompts.system import (
    WRITER_SYSTEM,
    GENERATION_PROMPT,
    CONTEXT_TEMPLATE,
)
from src.persona.prompt_injector import build_voice_rules, build_sample_posts_block
from src.utils.config import load_persona
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class GeneratedPost:
    """A LinkedIn post produced by the writer."""
    post_text: str
    source_title: str = ""
    source_url: str = ""
    topic: str = ""
    angle: str = ""
    hashtags: list[str] = field(default_factory=list)
    hook_line: str = ""
    virality_score: float = 0.0
    voice_match_score: float = 0.0

    @property
    def char_count(self) -> int:
        return len(self.post_text)

    @property
    def display(self) -> str:
        """Pretty-print for console output."""
        score_bar = "█" * int(self.virality_score / 5) + "░" * (20 - int(self.virality_score / 5))
        # Strip hashtags from post text if already in hashtags list
        text = self.post_text
        for tag in self.hashtags:
            text = text.replace(tag, "").strip()
        # Clean up any trailing whitespace/newlines left behind
        while text.endswith("\n"):
            text = text.rstrip()
        tags = " ".join(self.hashtags)
        return (
            f"{'─' * 60}\n"
            f"Topic: {self.topic} | Angle: {self.angle}\n"
            f"Score: [{score_bar}] {self.virality_score:.0f}%\n"
            f"Source: {self.source_title}\n"
            f"{'─' * 60}\n"
            f"{text}\n\n"
            f"{tags}\n"
            f"({self.char_count} chars)\n"
        )


def _build_context_window(items: list[ContentItem], max_items: int = 15) -> str:
    """Format collected content into a context window for the LLM."""
    # Sort by weight * recency
    scored = []
    for item in items:
        recency = max(0, 1.0 - (item.age_hours / 72))  # decay over 72h
        score = item.weight * (0.6 + 0.4 * recency)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_items = [item for _, item in scored[:max_items]]

    blocks = []
    for i, item in enumerate(top_items, 1):
        published = "Unknown"
        if item.published_at:
            hours = item.age_hours
            if hours < 1:
                published = "Just now"
            elif hours < 24:
                published = f"{hours:.0f}h ago"
            else:
                published = f"{hours / 24:.0f}d ago"

        blocks.append(CONTEXT_TEMPLATE.format(
            i=i,
            title=item.title,
            source=item.source_name,
            published=published,
            summary=item.display_text[:500],
        ))

    return "\n".join(blocks)


async def generate_posts(
    content: list[ContentItem],
    llm: BaseLLM,
    n_posts: int = 7,
    persona: dict | None = None,
) -> list[GeneratedPost]:
    """
    Generate LinkedIn posts from collected content.

    Args:
        content: List of collected ContentItems from all sources
        llm: Primary LLM instance (Sonnet-level quality)
        n_posts: Number of posts to generate
        persona: Persona DNA config dict (loads from file if None)

    Returns:
        List of GeneratedPost objects
    """
    if not content:
        logger.error("No content available for generation")
        return []

    # Build persona injection
    if persona is None:
        try:
            persona = load_persona()
        except FileNotFoundError:
            persona = {}

    voice_rules = build_voice_rules(persona)
    sample_block = build_sample_posts_block(persona)

    # Build context window
    context = _build_context_window(content, max_items=15)

    # Assemble the generation prompt
    prompt = GENERATION_PROMPT.format(
        n_posts=n_posts,
        voice_rules=voice_rules,
        sample_posts_block=sample_block or "(No sample posts configured yet)",
        context_window=context,
    )

    logger.info(f"Generating {n_posts} posts from {len(content)} content items...")

    # Call LLM
    try:
        result = await llm.generate(
            prompt=prompt,
            system=WRITER_SYSTEM,
            max_tokens=8000,
            temperature=0.8,
        )

        # Parse JSON response
        posts_data = _parse_posts_json(result.text)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Raw response: {result.text[:500]}")
        return []
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        return []

    # Convert to GeneratedPost objects
    posts = []
    for data in posts_data:
        post = GeneratedPost(
            post_text=data.get("post_text", "").strip(),
            source_title=data.get("source_title", ""),
            source_url=data.get("source_url", ""),
            topic=data.get("topic", ""),
            angle=data.get("angle", ""),
            hashtags=data.get("hashtags", []),
            hook_line=data.get("hook_line", ""),
        )
        if post.post_text and post.char_count >= 100:
            posts.append(post)

    logger.info(f"Generated {len(posts)} valid posts (requested {n_posts})")

    # Log token usage
    logger.info(
        f"Tokens used: {result.input_tokens} in / {result.output_tokens} out "
        f"({result.total_tokens} total)"
    )

    return posts


def _parse_posts_json(text: str) -> list[dict]:
    """Robustly parse the LLM's JSON response."""
    cleaned = text.strip()

    # Strip markdown fences
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "posts" in result:
            return result["posts"]
        return [result]
    except json.JSONDecodeError:
        pass

    # Try to find JSON array in the text
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.error("Could not parse any JSON from LLM response")
    return []
