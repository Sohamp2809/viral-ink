"""
Profile Builder — creates and updates the persona_dna.yaml from analysis results.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from src.persona.analyzer import VoiceProfile, analyze_posts
from src.utils.config import CONFIG_DIR, load_persona
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)

PERSONA_PATH = CONFIG_DIR / "persona_dna.yaml"


def _merge_profile_into_config(profile: VoiceProfile, existing: dict) -> dict:
    """Merge LLM-analyzed profile into existing config, preserving user edits."""
    # Update tone (LLM analysis wins, but keep any extra keys user added)
    if profile.tone:
        existing.setdefault("tone", {}).update(profile.tone)

    # Update structure
    if profile.structure:
        existing.setdefault("structure", {}).update(profile.structure)

    # Update content patterns
    if profile.content_patterns:
        existing.setdefault("content_patterns", {}).update(profile.content_patterns)

    # Vocabulary: merge carefully — don't overwrite user's avoided_words
    if profile.vocabulary:
        vocab = existing.setdefault("vocabulary", {})
        if "technical_depth" in profile.vocabulary:
            vocab["technical_depth"] = profile.vocabulary["technical_depth"]
        if "signature_phrases" in profile.vocabulary:
            # Merge, deduplicate
            existing_phrases = set(vocab.get("signature_phrases", []))
            new_phrases = set(profile.vocabulary["signature_phrases"])
            vocab["signature_phrases"] = sorted(existing_phrases | new_phrases)
        if "avoided_patterns" in profile.vocabulary:
            existing_avoided = set(vocab.get("avoided_words", []))
            new_avoided = set(profile.vocabulary["avoided_patterns"])
            vocab["avoided_words"] = sorted(existing_avoided | new_avoided)

    return existing


async def build_profile(posts: list[str], llm: BaseLLM) -> dict:
    """
    Analyze posts and build/update persona_dna.yaml.

    Args:
        posts: List of user's sample LinkedIn posts
        llm: LLM for analysis

    Returns:
        The updated persona config dict
    """
    # Analyze posts
    profile = await analyze_posts(posts, llm)

    # Load existing config (or start fresh)
    try:
        existing = load_persona()
    except FileNotFoundError:
        existing = {}

    # Store sample posts in config
    existing["sample_posts"] = posts[:5]  # keep top 5

    # Merge analysis results
    updated = _merge_profile_into_config(profile, existing)

    # Save
    save_persona(updated)
    logger.info(f"Persona DNA saved to {PERSONA_PATH}")
    return updated


def save_persona(config: dict) -> None:
    """Write persona config to YAML."""
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PERSONA_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def get_sample_posts() -> list[str]:
    """Load sample posts from persona config."""
    try:
        persona = load_persona()
        posts = persona.get("sample_posts", [])
        # Filter out placeholder text
        return [
            p for p in posts
            if p and "Paste your" not in p and "sample post" not in p.lower()
        ]
    except FileNotFoundError:
        return []
