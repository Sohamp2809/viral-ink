"""
Multi-Agent Orchestrator — Phase 4.

    Researcher → Writer → Critic → Revision → Hook Variants → Virality Score

Now generates 3 hook variants per post and scores virality 0-100%.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from src.collectors.base import ContentItem
from src.generator.agents.researcher import ContentBrief, research
from src.generator.agents.writer import Draft, write, revise
from src.generator.agents.critic import Critique, critique
from src.generator.prompts.system import CONTEXT_TEMPLATE
from src.hooks import generate_hook_variants, HookVariant
from src.scorer import score_post, ViralityScore
from src.persona.prompt_injector import build_voice_rules
from src.utils.config import load_persona
from src.utils.llm import BaseLLM, get_llm, get_cheap_llm

logger = logging.getLogger(__name__)


@dataclass
class FinalPost:
    """A finished post with hook variants and virality score."""
    post_text: str
    hook_line: str = ""
    topic: str = ""
    angle: str = ""
    source_title: str = ""
    source_url: str = ""
    hashtags: list[str] = field(default_factory=list)
    critic_scores: dict = field(default_factory=dict)
    critic_verdict: str = ""
    overall_score: float = 0.0
    revision_count: int = 0
    issues_fixed: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    # Phase 4 additions
    hook_variants: list[HookVariant] = field(default_factory=list)
    virality: ViralityScore | None = None

    @property
    def char_count(self) -> int:
        return len(self.post_text)

    @property
    def virality_pct(self) -> int:
        return self.virality.overall_pct if self.virality else 0

    @property
    def display(self) -> str:
        verdict = {"PUBLISH": "✅", "REVISE": "🔄", "REJECT": "❌"}.get(self.critic_verdict, "❓")
        return f"{verdict} {self.topic} [{self.angle}] — {self.virality_pct}%"


def _build_context_window(items: list[ContentItem], max_items: int = 15) -> str:
    scored = []
    for item in items:
        recency = max(0, 1.0 - (item.age_hours / 72))
        score = item.weight * (0.6 + 0.4 * recency)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_items = [item for _, item in scored[:max_items]]

    blocks = []
    for i, item in enumerate(top_items, 1):
        if item.published_at:
            hours = item.age_hours
            published = f"{hours:.0f}h ago" if hours < 48 else f"{hours / 24:.0f}d ago"
        else:
            published = "Unknown"

        trend_note = ""
        if item.metadata.get("trend_phase"):
            phase = item.metadata["trend_phase"]
            momentum = item.metadata.get("trend_momentum", 0)
            trend_note = f" | Trend: {phase} (momentum: {momentum:.2f})"

        blocks.append(CONTEXT_TEMPLATE.format(
            i=i,
            title=item.title,
            source=item.source_name,
            published=f"{published}{trend_note}",
            summary=item.display_text[:500],
        ))

    return "\n".join(blocks)


def _attach_summaries(briefs: list[ContentBrief], items: list[ContentItem]) -> None:
    title_map = {item.title.lower().strip(): item for item in items}

    for brief in briefs:
        title_key = brief.source_title.lower().strip()
        if title_key in title_map:
            item = title_map[title_key]
            brief.source_summary = item.display_text[:800]
            if not brief.source_url:
                brief.source_url = item.url
        else:
            for key, item in title_map.items():
                if title_key[:30] in key or key[:30] in title_key:
                    brief.source_summary = item.display_text[:800]
                    if not brief.source_url:
                        brief.source_url = item.url
                    break


async def _process_single_post(
    brief: ContentBrief,
    persona: dict,
    writer_llm: BaseLLM,
    critic_llm: BaseLLM,
    content_items: list[ContentItem],
) -> FinalPost | None:
    """Process a single brief through writer → critic → revision → hooks → scoring."""

    # Step 1: Writer drafts
    draft = await write(brief, persona, writer_llm)
    if not draft.post_text:
        logger.warning(f"Writer produced empty draft for '{brief.topic}' — skipping")
        return None

    # Step 2: Critic evaluates
    crit = await critique(draft, persona, critic_llm)

    # Step 3: Handle verdict
    if crit.verdict == "PUBLISH":
        logger.info(f"  ✅ {brief.topic} — PUBLISH (score: {crit.overall_score:.1f})")

    elif crit.verdict == "REVISE":
        logger.info(
            f"  🔄 {brief.topic} — REVISE (score: {crit.overall_score:.1f}, "
            f"issues: {len(crit.issues)})"
        )
        draft = await revise(
            draft=draft,
            revision_instructions=crit.revision_instructions,
            issues=crit.issues,
            avoided_violations=crit.avoided_word_violations,
            persona=persona,
            llm=writer_llm,
        )
        # Hard replace remaining avoided words
        avoided = persona.get("vocabulary", {}).get("avoided_words", [])
        for word in avoided:
            if word.lower() in draft.post_text.lower():
                draft.post_text = draft.post_text.replace(word, "significant shift")
                draft.post_text = draft.post_text.replace(
                    word.replace("-", " "), "significant shift"
                )
                logger.info(f"  🔧 Hard-replaced avoided word: '{word}'")

    elif crit.verdict == "REJECT":
        logger.info(f"  ❌ {brief.topic} — REJECT (score: {crit.overall_score:.1f})")
        draft = await write(brief, persona, writer_llm)
        if not draft.post_text:
            return None

    # Step 4: Generate hook variants
    voice_summary = build_voice_rules(persona)[:200]
    hook_line = draft.hook_line or draft.post_text.split("\n")[0].strip()

    hooks = await generate_hook_variants(
        post_text=draft.post_text,
        original_hook=hook_line,
        voice_summary=voice_summary,
        llm=critic_llm,  # cheap model for hooks
    )

    # Step 5: Virality scoring
    trend_momentum = 0.0
    trend_phase = ""
    for item in content_items:
        if item.title.lower().strip() == brief.source_title.lower().strip():
            trend_momentum = item.metadata.get("trend_momentum", 0.0)
            trend_phase = item.metadata.get("trend_phase", "")
            break

    virality = score_post(
        post_text=draft.post_text,
        hook_line=hook_line,
        hashtags=draft.hashtags,
        critic_score=crit.overall_score,
        trend_momentum=trend_momentum,
        trend_phase=trend_phase,
    )

    logger.info(f"  📊 {brief.topic} — Virality: {virality.overall_pct}% ({virality.tier})")

    return FinalPost(
        post_text=draft.post_text,
        hook_line=hook_line,
        topic=brief.topic,
        angle=brief.angle,
        source_title=brief.source_title,
        source_url=brief.source_url,
        hashtags=draft.hashtags,
        critic_scores=crit.scores,
        critic_verdict=crit.verdict,
        overall_score=crit.overall_score,
        revision_count=draft.revision_count,
        issues_fixed=crit.issues if draft.revision_count > 0 else [],
        metadata={"trend_phase": trend_phase, "trend_momentum": trend_momentum},
        hook_variants=hooks,
        virality=virality,
    )


async def run_multi_agent_pipeline(
    content: list[ContentItem],
    n_posts: int = 7,
    persona: dict | None = None,
    max_parallel: int = 3,
    trend_context: str = "",
) -> list[FinalPost]:
    """
    Full pipeline: Researcher → Writer → Critic → Revision → Hooks → Scoring.
    """
    if not content:
        logger.error("No content available for generation")
        return []

    if persona is None:
        try:
            persona = load_persona()
        except FileNotFoundError:
            persona = {}

    writer_llm = get_llm()
    critic_llm = get_cheap_llm()

    # Step 1: Researcher
    logger.info("Phase 2.1: Researcher analyzing content...")
    context_window = _build_context_window(content)
    voice_summary = build_voice_rules(persona)[:300]

    if trend_context:
        context_window = f"{context_window}\n\n{trend_context}"

    briefs = await research(
        context_window=context_window,
        voice_summary=voice_summary,
        n_posts=n_posts,
        llm=critic_llm,
    )

    if not briefs:
        logger.error("Researcher produced no content briefs")
        return []

    _attach_summaries(briefs, content)

    logger.info(f"Researcher selected {len(briefs)} opportunities:")
    for b in briefs:
        logger.info(f"  • {b.topic} [{b.angle}] — {b.confidence}")

    # Steps 2-5: Writer + Critic + Revision + Hooks + Scoring
    logger.info("Phase 2.2: Writer + Critic + Hooks + Scoring pipeline...")

    final_posts: list[FinalPost] = []
    semaphore = asyncio.Semaphore(max_parallel)

    async def _bounded_process(brief: ContentBrief) -> FinalPost | None:
        async with semaphore:
            return await _process_single_post(
                brief, persona, writer_llm, critic_llm, content
            )

    tasks = [_bounded_process(brief) for brief in briefs]
    results = await asyncio.gather(*tasks)

    for post in results:
        if post and post.post_text:
            final_posts.append(post)

    # Sort by virality score (highest first)
    final_posts.sort(key=lambda p: p.virality_pct, reverse=True)

    if final_posts:
        avg_virality = sum(p.virality_pct for p in final_posts) / len(final_posts)
        logger.info(
            f"Pipeline complete: {len(final_posts)} posts, "
            f"avg virality: {avg_virality:.0f}%, "
            f"{sum(1 for p in final_posts if p.revision_count > 0)} revised"
        )

    return final_posts
