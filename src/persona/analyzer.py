"""
Persona Analyzer — extracts quantified voice dimensions from sample posts.

Feeds user's LinkedIn posts to an LLM and gets back a structured voice profile.
This runs once during onboarding (`pilot onboard`) and can be re-run to update.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are an expert writing analyst. Analyze these LinkedIn posts written by the same person and extract a detailed voice profile.

POSTS TO ANALYZE:
{posts_text}

Analyze these posts and return a JSON object with EXACTLY this structure:
{{
  "tone": {{
    "formality": <float 0-1, 0=very casual, 1=very formal>,
    "humor_frequency": <float 0-1, how often humor/wit appears>,
    "vulnerability": <float 0-1, willingness to share failures>,
    "assertiveness": <float 0-1, strength of opinions>,
    "optimism": <float 0-1, 0=cynical, 1=very positive>
  }},
  "structure": {{
    "avg_post_length": <int, average character count>,
    "avg_paragraph_length": <int, average words per paragraph>,
    "line_break_frequency": <float, line breaks per 100 words>,
    "uses_emojis": <bool>,
    "uses_numbered_lists": <bool>,
    "uses_single_word_lines": <bool>,
    "uses_parenthetical_asides": <bool>
  }},
  "content_patterns": {{
    "storytelling_ratio": <float 0-1, % posts that lead with a story>,
    "data_ratio": <float 0-1, % posts with specific numbers/stats>,
    "opinion_ratio": <float 0-1, % posts taking a clear stance>,
    "question_ending_ratio": <float 0-1, % posts ending with a question>
  }},
  "vocabulary": {{
    "technical_depth": <float 0-1, 0=layperson, 1=deep technical>,
    "signature_phrases": [<list of 3-6 phrases this person uses often>],
    "avoided_patterns": [<list of patterns/styles this person never uses>]
  }},
  "overall_voice_summary": "<2-3 sentence description of this person's writing voice>"
}}

Be precise. Base every value on evidence from the posts, not assumptions."""


@dataclass
class VoiceProfile:
    """Quantified voice dimensions extracted from sample posts."""

    tone: dict = field(default_factory=dict)
    structure: dict = field(default_factory=dict)
    content_patterns: dict = field(default_factory=dict)
    vocabulary: dict = field(default_factory=dict)
    overall_summary: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> VoiceProfile:
        return cls(
            tone=data.get("tone", {}),
            structure=data.get("structure", {}),
            content_patterns=data.get("content_patterns", {}),
            vocabulary=data.get("vocabulary", {}),
            overall_summary=data.get("overall_voice_summary", ""),
        )

    def to_dict(self) -> dict:
        return {
            "tone": self.tone,
            "structure": self.structure,
            "content_patterns": self.content_patterns,
            "vocabulary": self.vocabulary,
            "overall_voice_summary": self.overall_summary,
        }


async def analyze_posts(posts: list[str], llm: BaseLLM) -> VoiceProfile:
    """
    Analyze a list of user's LinkedIn posts and extract a voice profile.

    Args:
        posts: List of post texts (minimum 3, recommended 10-20)
        llm: LLM instance to use for analysis

    Returns:
        VoiceProfile with quantified dimensions
    """
    if len(posts) < 2:
        raise ValueError("Need at least 2 sample posts for analysis. 10+ recommended.")

    # Format posts with numbering
    posts_text = "\n\n".join(
        f"--- Post {i+1} ---\n{post.strip()}"
        for i, post in enumerate(posts)
    )

    prompt = ANALYSIS_PROMPT.format(posts_text=posts_text)

    logger.info(f"Analyzing {len(posts)} posts for voice profile...")
    result = await llm.generate_json(prompt)

    profile = VoiceProfile.from_dict(result)
    logger.info(f"Voice profile extracted: {profile.overall_summary[:100]}...")
    return profile
