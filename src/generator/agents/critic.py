"""
Critic Agent — V2. Evaluates drafts and catches AI patterns.
Includes hard-coded pattern detection that doesn't rely on the LLM.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from src.generator.agents.writer import Draft
from src.generator.prompts.critic_prompt import CRITIC_SYSTEM, CRITIC_PROMPT
from src.persona.prompt_injector import build_voice_rules
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)

# Hard-coded AI patterns — if found, force REVISE regardless of LLM opinion
AI_PATTERNS = [
    (r"here'?s the thing[:\s]", "REJECT", "Contains 'Here's the thing' — top AI cliché"),
    (r"let me break this down[:\s]", "REVISE", "Contains 'Let me break this down'"),
    (r"^hot take:", "REVISE", "Labels hot takes instead of just being hot"),
    (r"what do you think\?\s*$", "REVISE", "Ends with generic 'What do you think?'"),
    (r"what'?s your take\?\s*$", "REVISE", "Ends with generic 'What's your take?'"),
    (r"^in today'?s (fast-paced|ever|rapidly)", "REVISE", "Cliché opener 'In today's...'"),
    (r"^in a world where", "REVISE", "Cliché opener 'In a world where...'"),
    (r"\blandscape\b", "REVISE", "'Landscape' is corporate fluff"),
    (r"\becosystem\b", "REVISE", "'Ecosystem' is overused"),
    (r"\bparadigm\b", "REVISE", "'Paradigm' is corporate jargon"),
    (r"i'?m excited to (share|announce)", "REVISE", "AI-typical excited opener"),
    (r"without further ado", "REVISE", "Cliché transition"),
    (r"it'?s important to note", "REVISE", "AI filler phrase"),
]


@dataclass
class Critique:
    scores: dict = field(default_factory=dict)
    overall_score: float = 0.0
    verdict: str = "REVISE"
    issues: list[str] = field(default_factory=list)
    revision_instructions: str = ""
    avoided_word_violations: list[str] = field(default_factory=list)
    ai_patterns_found: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.verdict == "PUBLISH"


def _detect_ai_patterns(text: str) -> list[tuple[str, str]]:
    """Detect AI patterns in text. Returns list of (severity, description)."""
    found = []
    text_lower = text.lower().strip()

    for pattern, severity, description in AI_PATTERNS:
        if re.search(pattern, text_lower, re.MULTILINE | re.IGNORECASE):
            found.append((severity, description))

    return found


async def critique(
    draft: Draft,
    persona: dict,
    llm: BaseLLM | None = None,
) -> Critique:
    if llm is None:
        from src.utils.llm import get_cheap_llm
        llm = get_cheap_llm()

    if not draft.post_text or not draft.brief:
        return Critique(verdict="REJECT", issues=["Empty draft or missing brief"])

    voice_rules = build_voice_rules(persona)
    avoided = persona.get("vocabulary", {}).get("avoided_words", [])
    avoided_str = ", ".join(f'"{w}"' for w in avoided) if avoided else "None specified"

    prompt = CRITIC_PROMPT.format(
        draft_text=draft.post_text,
        topic=draft.brief.topic,
        angle=draft.brief.angle,
        thesis=draft.brief.thesis,
        voice_summary=voice_rules,
        avoided_words=avoided_str,
        source_summary=draft.brief.source_summary or draft.brief.source_title,
    )

    try:
        result = await llm.generate(
            prompt=prompt,
            system=CRITIC_SYSTEM,
            max_tokens=2000,
            temperature=0.3,
        )

        data = _parse_critique(result.text)

        crit = Critique(
            scores=data.get("scores", {}),
            overall_score=data.get("overall_score", 5.0),
            verdict=data.get("verdict", "REVISE").upper(),
            issues=data.get("issues", []),
            revision_instructions=data.get("revision_instructions", ""),
            avoided_word_violations=data.get("avoided_word_violations", []),
            ai_patterns_found=data.get("ai_patterns_found", []),
        )

    except Exception as e:
        logger.error(f"Critic failed for '{draft.brief.topic}': {e}")
        crit = Critique(
            verdict="REVISE",
            issues=["Critic evaluation failed — defaulting to revision"],
            revision_instructions="Rewrite the opening to be more specific. End with a sharp declaration instead of a question.",
        )

    # ── Hard-coded checks (override LLM if needed) ──────

    # Check avoided words
    post_lower = draft.post_text.lower()
    for word in avoided:
        if word.lower() in post_lower:
            if word not in crit.avoided_word_violations:
                crit.avoided_word_violations.append(word)
            if crit.verdict == "PUBLISH":
                crit.verdict = "REVISE"
            crit.issues.append(f"Contains avoided word: '{word}'")
            crit.revision_instructions += f" Remove '{word}' and rephrase the sentence."

    # Check AI patterns
    ai_hits = _detect_ai_patterns(draft.post_text)
    for severity, description in ai_hits:
        crit.ai_patterns_found.append(description)
        crit.issues.append(f"AI pattern: {description}")

        if severity == "REJECT" and crit.verdict != "REJECT":
            crit.verdict = "REJECT"
            crit.revision_instructions = (
                "This post uses 'Here's the thing' which is the most recognizable AI pattern "
                "on LinkedIn. Rewrite completely without this phrase. Start with a specific "
                "scene, number, or bold claim instead."
            )
        elif severity == "REVISE" and crit.verdict == "PUBLISH":
            crit.verdict = "REVISE"

    if ai_hits:
        patterns_str = "; ".join(desc for _, desc in ai_hits)
        if "rewrite" not in crit.revision_instructions.lower():
            crit.revision_instructions += (
                f" AI patterns detected: {patterns_str}. "
                "Rewrite the affected sections to sound human — use specific details, "
                "varied sentence lengths, and a genuine point of view."
            )

    logger.debug(
        f"Critic: {draft.brief.topic} → {crit.verdict} "
        f"(score: {crit.overall_score:.1f}, "
        f"AI patterns: {len(ai_hits)}, issues: {len(crit.issues)})"
    )
    return crit


def _parse_critique(text: str) -> dict:
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

    logger.warning("Could not parse critic JSON — defaulting to REVISE")
    return {"verdict": "REVISE", "issues": ["Failed to parse critic response"]}
