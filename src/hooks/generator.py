"""
Hook Variant Generator — creates 2 alternative opening hooks for each post.
The user sees 3 options (original + 2 variants) and picks the strongest.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from src.hooks.classifier import (
    classify_hook,
    HOOK_TECHNIQUES,
    TECHNIQUE_DESCRIPTIONS,
)
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class HookVariant:
    """A single hook option."""
    label: str          # "A (original)", "B", "C"
    text: str           # The hook line text
    technique: str      # contrarian, statistic, personal_story, etc.


HOOK_GENERATION_PROMPT = """Generate 2 alternative opening hooks for this LinkedIn post.

FULL POST:
{post_text}

CURRENT OPENING HOOK (Hook A — {original_technique}):
"{original_hook}"

Generate 2 COMPLETELY DIFFERENT hooks using different persuasion techniques.

Available techniques (pick 2 that are DIFFERENT from "{original_technique}"):
{techniques_list}

RULES:
- Each hook must be 1-2 lines max
- Each must lead naturally into the rest of the post
- Each must use a genuinely different approach than Hook A
- Match this voice profile: {voice_summary}
- Do NOT fabricate statistics unless they come from the post's source material

Return valid JSON:
{{
  "hook_b": {{
    "text": "<the hook text>",
    "technique": "<technique name>"
  }},
  "hook_c": {{
    "text": "<the hook text>",
    "technique": "<technique name>"
  }}
}}"""


async def generate_hook_variants(
    post_text: str,
    original_hook: str,
    voice_summary: str,
    llm: BaseLLM,
) -> list[HookVariant]:
    """
    Generate 2 alternative hooks for a post.

    Args:
        post_text: The full post text
        original_hook: The current first line
        voice_summary: Brief voice description for tone matching
        llm: Cheap LLM (Haiku/GPT-4o-mini)

    Returns:
        List of 3 HookVariants: [A (original), B, C]
    """
    original_technique = classify_hook(original_hook)

    # Build techniques list excluding the original
    available = [
        t for t in HOOK_TECHNIQUES
        if t != original_technique
    ]
    techniques_list = "\n".join(
        f"- {t}: {TECHNIQUE_DESCRIPTIONS.get(t, '')}"
        for t in available
    )

    prompt = HOOK_GENERATION_PROMPT.format(
        post_text=post_text[:1500],
        original_hook=original_hook,
        original_technique=original_technique,
        techniques_list=techniques_list,
        voice_summary=voice_summary[:300],
    )

    variants = [
        HookVariant(
            label="A (original)",
            text=original_hook,
            technique=original_technique,
        )
    ]

    try:
        result = await llm.generate(
            prompt=prompt,
            system="You are an expert LinkedIn copywriter who specializes in scroll-stopping opening hooks. Return only valid JSON.",
            max_tokens=500,
            temperature=0.9,  # high creativity for diverse hooks
        )

        data = _parse_hooks(result.text)

        if "hook_b" in data:
            variants.append(HookVariant(
                label="B",
                text=data["hook_b"].get("text", "").strip(),
                technique=data["hook_b"].get("technique", "general"),
            ))

        if "hook_c" in data:
            variants.append(HookVariant(
                label="C",
                text=data["hook_c"].get("text", "").strip(),
                technique=data["hook_c"].get("technique", "general"),
            ))

        logger.debug(
            f"Generated {len(variants)} hook variants "
            f"(techniques: {[v.technique for v in variants]})"
        )

    except Exception as e:
        logger.warning(f"Hook generation failed: {e} — using original only")

    return variants


def _parse_hooks(text: str) -> dict:
    """Parse hook generator JSON response."""
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            pass

    return {}
