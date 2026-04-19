"""
Persona Calibrator — generates test posts and measures how well they match
the user's actual voice. Used during onboarding and periodic re-calibration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.persona.prompt_injector import build_voice_rules, build_sample_posts_block
from src.utils.llm import BaseLLM

logger = logging.getLogger(__name__)


@dataclass
class CalibrationResult:
    """Result of a calibration test."""
    generated_posts: list[str]
    user_posts: list[str]
    voice_match_scores: list[float]
    avg_score: float
    feedback: str

    @property
    def passed(self) -> bool:
        return self.avg_score >= 0.65


CALIBRATION_PROMPT = """Write {n} short LinkedIn posts about these topics: {topics}

Each post should be 600-1000 characters. Write them as if YOU are the person
whose voice is described below. They should be indistinguishable from the
reference posts.

{voice_rules}

{sample_posts}

Write exactly {n} posts, separated by "---POST---" on its own line.
Nothing else — no numbering, no labels, just the post text."""


SCORING_PROMPT = """You are evaluating whether AI-generated posts match a person's authentic writing voice.

REAL POSTS by the person:
{real_posts}

GENERATED POSTS (attempting to match their voice):
{generated_posts}

For each generated post, score how well it matches the person's voice on a 0.0-1.0 scale:
- 1.0 = indistinguishable from the person's real writing
- 0.7 = very close, minor differences a careful reader might notice
- 0.5 = captures some elements but clearly different in places
- 0.3 = gets the topic right but voice is clearly off
- 0.0 = doesn't match at all

Return JSON:
{{
  "scores": [<float for each generated post>],
  "overall_feedback": "<what to adjust to improve the match>"
}}"""


async def run_calibration(
    persona: dict,
    llm: BaseLLM,
    topics: list[str] | None = None,
    n_posts: int = 3,
) -> CalibrationResult:
    """
    Generate test posts and score them against the user's real voice.

    Args:
        persona: The persona_dna config dict
        llm: LLM to use for generation and scoring
        topics: Optional list of topics to write about
        n_posts: Number of test posts to generate

    Returns:
        CalibrationResult with scores and feedback
    """
    if topics is None:
        topics = ["AI trends in 2026", "a lesson learned from a failed project", "developer productivity"]

    # Get user's real posts
    real_posts = [
        p for p in persona.get("sample_posts", [])
        if p and "Paste your" not in p
    ]
    if len(real_posts) < 2:
        return CalibrationResult(
            generated_posts=[],
            user_posts=[],
            voice_match_scores=[],
            avg_score=0.0,
            feedback="Need at least 2 sample posts in persona_dna.yaml to calibrate.",
        )

    # Generate test posts
    voice_rules = build_voice_rules(persona)
    sample_block = build_sample_posts_block(persona)

    gen_prompt = CALIBRATION_PROMPT.format(
        n=n_posts,
        topics=", ".join(topics[:n_posts]),
        voice_rules=voice_rules,
        sample_posts=sample_block,
    )

    logger.info(f"Generating {n_posts} calibration posts...")
    gen_response = await llm.generate(gen_prompt, temperature=0.8)
    generated = [
        p.strip() for p in gen_response.text.split("---POST---")
        if p.strip()
    ]

    if not generated:
        # Fallback: split by double newline
        generated = [p.strip() for p in gen_response.text.split("\n\n\n") if len(p.strip()) > 100]

    # Score them
    real_text = "\n\n".join(f"--- Real post {i+1} ---\n{p}" for i, p in enumerate(real_posts[:3]))
    gen_text = "\n\n".join(f"--- Generated post {i+1} ---\n{p}" for i, p in enumerate(generated))

    score_prompt = SCORING_PROMPT.format(real_posts=real_text, generated_posts=gen_text)

    logger.info("Scoring voice match...")
    score_result = await llm.generate_json(score_prompt)

    scores = score_result.get("scores", [0.5] * len(generated))
    feedback = score_result.get("overall_feedback", "No feedback generated.")
    avg = sum(scores) / len(scores) if scores else 0.0

    result = CalibrationResult(
        generated_posts=generated,
        user_posts=real_posts[:3],
        voice_match_scores=scores,
        avg_score=avg,
        feedback=feedback,
    )

    status = "PASSED" if result.passed else "NEEDS ADJUSTMENT"
    logger.info(f"Calibration {status}: avg voice match = {avg:.2f}")
    return result
