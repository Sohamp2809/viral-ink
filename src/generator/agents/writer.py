"""
Writer Agent — drafts a single LinkedIn post from a content brief,
and can revise based on critic feedback.

Uses the primary LLM (Sonnet/GPT-4o) since writing quality is critical.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from src.generator.agents.researcher import ContentBrief
from src.generator.prompts.writer_prompt import WRITER_SYSTEM, WRITER_PROMPT
from src.generator.prompts.revision_prompt import REVISION_PROMPT
from src.persona.prompt_injector import build_voice_rules, build_sample_posts_block
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class Draft:
    """A post draft produced by the writer."""
    post_text: str = ""
    hook_line: str = ""
    hashtags: list[str] = field(default_factory=list)
    brief: ContentBrief | None = None
    revision_count: int = 0
    changes_made: str = ""

    @property
    def char_count(self) -> int:
        return len(self.post_text)


async def write(
    brief: ContentBrief,
    persona: dict,
    llm: BaseLLM,
) -> Draft:
    """
    Write a single LinkedIn post from a content brief.

    Args:
        brief: ContentBrief from the researcher
        persona: Persona DNA config dict
        llm: Primary LLM (Sonnet/GPT-4o)

    Returns:
        Draft object with the post text
    """
    voice_rules = build_voice_rules(persona)
    sample_block = build_sample_posts_block(persona)

    prompt = WRITER_PROMPT.format(
        topic=brief.topic,
        angle=brief.angle,
        thesis=brief.thesis,
        source_summary=brief.source_summary or brief.source_title,
        source_title=brief.source_title,
        voice_rules=voice_rules,
        sample_posts_block=sample_block or "(No sample posts configured)",
    )

    try:
        result = await llm.generate(
            prompt=prompt,
            system=WRITER_SYSTEM,
            max_tokens=2000,
            temperature=0.8,
        )

        data = _parse_draft(result.text)
        draft = Draft(
            post_text=data.get("post_text", "").strip(),
            hook_line=data.get("hook_line", ""),
            hashtags=data.get("hashtags", []),
            brief=brief,
        )

        logger.debug(
            f"Writer drafted: {brief.topic} ({draft.char_count} chars, "
            f"{result.output_tokens} tokens)"
        )
        return draft

    except Exception as e:
        logger.error(f"Writer failed for '{brief.topic}': {e}")
        return Draft(brief=brief)


async def revise(
    draft: Draft,
    revision_instructions: str,
    issues: list[str],
    avoided_violations: list[str],
    persona: dict,
    llm: BaseLLM,
) -> Draft:
    """
    Revise a draft based on critic feedback.

    Args:
        draft: The original draft to revise
        revision_instructions: Specific instructions from the critic
        issues: List of issues the critic found
        avoided_violations: Avoided words found in the draft
        persona: Persona DNA config dict
        llm: Primary LLM

    Returns:
        Revised Draft object
    """
    voice_rules = build_voice_rules(persona)

    prompt = REVISION_PROMPT.format(
        original_text=draft.post_text,
        revision_instructions=revision_instructions,
        issues="\n".join(f"- {issue}" for issue in issues),
        avoided_violations=", ".join(avoided_violations) if avoided_violations else "None found",
        voice_rules=voice_rules,
    )

    try:
        result = await llm.generate(
            prompt=prompt,
            system=WRITER_SYSTEM,
            max_tokens=2000,
            temperature=0.7,
        )

        data = _parse_draft(result.text)
        revised = Draft(
            post_text=data.get("post_text", draft.post_text).strip(),
            hook_line=data.get("hook_line", ""),
            hashtags=data.get("hashtags", draft.hashtags),
            brief=draft.brief,
            revision_count=draft.revision_count + 1,
            changes_made=data.get("changes_made", ""),
        )

        logger.debug(
            f"Writer revised: {draft.brief.topic} "
            f"(revision #{revised.revision_count}, {revised.char_count} chars)"
        )
        return revised

    except Exception as e:
        logger.error(f"Revision failed for '{draft.brief.topic}': {e}")
        return draft


def _parse_draft(text: str) -> dict:
    """Parse writer's JSON response."""
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Fallback: treat entire text as the post
    logger.warning("Could not parse writer JSON — using raw text as post")
    return {"post_text": cleaned}
