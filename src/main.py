"""
Pipeline Orchestrator — Phase 4.

    collect → rank → trend radar → multi-agent generate → hooks → score → display

Now shows A/B hook variants and virality percentage for each post.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from rich.console import Console
from rich.panel import Panel

from src.collectors.base import ContentItem
from src.collectors.rss_collector import RSSCollector
from src.collectors.news_collector import NewsCollector
from src.collectors.trend_radar import (
    compute_trends,
    format_trend_radar,
    apply_trend_weights,
    TrendScore,
)
from src.collectors.trend_radar.snapshots import cleanup_old_snapshots
from src.generator.orchestrator import run_multi_agent_pipeline, FinalPost
from src.utils.config import get_settings, load_sources
from src.utils.db import get_session, Article, GeneratedPost as DBPost

logger = logging.getLogger(__name__)
console = Console()


# ── Step 1: Collect ─────────────────────────────────────

async def collect_content() -> list[ContentItem]:
    collectors = [RSSCollector(), NewsCollector()]
    all_items: list[ContentItem] = []

    with console.status("[bold teal]Collecting content from all sources..."):
        tasks = [c.safe_collect() for c in collectors]
        results = await asyncio.gather(*tasks)
        for items in results:
            all_items.extend(items)

    console.print(f"  Collected [bold]{len(all_items)}[/bold] items from {len(collectors)} sources")
    return all_items


# ── Step 2: Rank & Filter ──────────────────────────────

def rank_content(items: list[ContentItem], max_items: int = 20) -> list[ContentItem]:
    for item in items:
        hours = item.age_hours
        if hours < 6:
            recency = 25
        elif hours < 12:
            recency = 22
        elif hours < 24:
            recency = 18
        elif hours < 48:
            recency = 12
        else:
            recency = 5

        weight_score = min(item.weight * 10, 15)
        richness = min(len(item.display_text) / 100, 10)
        item.weight = recency + weight_score + richness

    # Hard filter: drop articles that don't mention any target topic
    target_topics = load_sources().get("target_topics", [])
    if target_topics:
        filtered = []
        for item in items:
            text = f"{item.title} {item.summary[:300]}".lower()
            if any(topic.lower() in text for topic in target_topics):
                filtered.append(item)
        items = filtered if filtered else items

    items.sort(key=lambda x: x.weight, reverse=True)
    top = items[:max_items]
    console.print(f"  Ranked content: top {len(top)} of {len(items)} items selected")
    return top


# ── Step 3: Trend Radar ────────────────────────────────

async def run_trend_radar(items: list[ContentItem]) -> list[TrendScore]:
    trends = await compute_trends(items)

    if trends:
        emerging = [t for t in trends if t.phase == "EMERGING"]
        peaking = [t for t in trends if t.phase == "PEAKING"]

        console.print(f"  Tracked [bold]{len(trends)}[/bold] topics")
        if emerging:
            console.print(f"  [bold red]🔴 {len(emerging)} EMERGING[/bold red]:", end=" ")
            console.print(", ".join(t.topic for t in emerging[:5]))
        if peaking:
            console.print(f"  [bold yellow]🟡 {len(peaking)} PEAKING[/bold yellow]:", end=" ")
            console.print(", ".join(t.topic for t in peaking[:5]))

        apply_trend_weights(items, trends)
        items.sort(key=lambda x: x.weight, reverse=True)
    else:
        console.print("  [dim]No trend data yet — trends appear after multiple runs[/dim]")

    return trends


# ── Step 4: Generate ────────────────────────────────────

async def generate(
    content: list[ContentItem],
    trends: list[TrendScore],
    n_posts: int = 7,
) -> list[FinalPost]:
    trend_context = format_trend_radar(trends)

    with console.status("[bold coral]Running multi-agent pipeline..."):
        posts = await run_multi_agent_pipeline(
            content, n_posts=n_posts, trend_context=trend_context,
        )
    return posts


# ── Step 5: Display ─────────────────────────────────────

def display_posts(posts: list[FinalPost], trends: list[TrendScore]) -> None:
    if not posts:
        console.print("[red]No posts were generated.[/red]")
        return

    # Trend radar summary
    if trends:
        emerging = [t for t in trends if t.phase == "EMERGING"]
        peaking = [t for t in trends if t.phase == "PEAKING"]
        if emerging or peaking:
            console.print("\n[bold]Trend Radar[/bold]")
            for t in (emerging + peaking)[:6]:
                console.print(f"  {t.display}")
            console.print()

    # Summary stats
    avg_virality = sum(p.virality_pct for p in posts) / len(posts)
    revised = sum(1 for p in posts if p.revision_count > 0)

    console.print(f"[bold green]Generated {len(posts)} LinkedIn posts[/bold green]")
    console.print(
        f"  Avg virality: [bold]{avg_virality:.0f}%[/bold] · "
        f"{revised} revised\n"
    )

    for i, post in enumerate(posts, 1):
        # Virality bar
        v = post.virality
        if v:
            vbar = v.bar
            tier_color = v.tier_color
            vpct = v.overall_pct
        else:
            vbar = "░" * 20
            tier_color = "white"
            vpct = 0

        verdict = {"PUBLISH": "✅", "REVISE": "🔄", "REJECT": "❌"}.get(post.critic_verdict, "❓")

        # Strip duplicate hashtags from text
        text = post.post_text
        for tag in post.hashtags:
            text = text.replace(tag, "").strip()
        while text.endswith("\n"):
            text = text.rstrip()

        tags = " ".join(post.hashtags)

        # Hook variants section
        hooks_section = ""
        if post.hook_variants and len(post.hook_variants) > 1:
            hooks_lines = ["\n[bold]Hook variants:[/bold]"]
            for hv in post.hook_variants:
                tech = hv.technique
                hooks_lines.append(f"  [{hv.label}] ({tech}): {hv.text}")
            hooks_section = "\n".join(hooks_lines)

        # Virality breakdown
        virality_section = ""
        if v:
            virality_section = f"\n[dim]Virality: {v.display}[/dim]"
            if v.reasoning:
                virality_section += f"\n[dim]{v.reasoning}[/dim]"

        # Critic scores
        if post.critic_scores:
            scores_parts = [
                f"{k.replace('_', ' ').title()}: {val}"
                for k, val in post.critic_scores.items()
            ]
            scores_line = " · ".join(scores_parts)
        else:
            scores_line = "N/A"

        revision_note = f" · Revised {post.revision_count}x" if post.revision_count else ""
        trend_badge = ""
        if post.metadata.get("trend_phase"):
            phase = post.metadata["trend_phase"]
            emoji = {"EMERGING": "🔴", "PEAKING": "🟡"}.get(phase, "")
            if emoji:
                trend_badge = f" · {emoji} {phase}"

        content_text = (
            f"{text}\n\n"
            f"{tags}"
            f"{hooks_section}"
            f"{virality_section}\n\n"
            f"[dim]Critic: {scores_line}[/dim]\n"
            f"[dim]{post.char_count} chars · Source: {post.source_title}{revision_note}{trend_badge}[/dim]"
        )

        panel = Panel(
            content_text,
            title=(
                f"[bold]Post {i}[/bold] · {post.topic} · [{post.angle}] "
                f"{verdict} [{tier_color}][{vbar}] {vpct}%[/{tier_color}]"
            ),
            border_style="cyan",
            width=90,
            padding=(1, 2),
        )
        console.print(panel)
        console.print()


# ── Step 6: Save to DB ─────────────────────────────────

async def save_posts(posts: list[FinalPost]) -> None:
    session = await get_session()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with session:
        for post in posts:
            db_post = DBPost(
                pipeline_date=today,
                topic=post.topic,
                angle=post.angle,
                post_text=post.post_text,
                source_title=post.source_title,
                source_url=post.source_url,
                hashtags=" ".join(post.hashtags),
                virality_score=post.virality_pct,
                score_breakdown=post.virality.breakdown if post.virality else {},
                voice_match_score=post.critic_scores.get("voice_match", 0),
            )
            session.add(db_post)
        await session.commit()

    logger.info(f"Saved {len(posts)} posts to database")


async def save_articles(items: list[ContentItem]) -> None:
    session = await get_session()
    async with session:
        for item in items[:50]:
            article = Article(
                source_name=item.source_name,
                source_url=item.metadata.get("feed_url", ""),
                title=item.title,
                summary=item.summary[:2000],
                url=item.url,
                category=item.category,
                published_at=item.published_at,
                weight=item.weight,
            )
            session.add(article)
        await session.commit()


# ── Full Pipeline ───────────────────────────────────────

async def run_pipeline(n_posts: int | None = None) -> list[FinalPost]:
    """
    Full daily pipeline:
    1. Collect → 2. Rank → 3. Trend Radar → 4. Multi-Agent + Hooks + Score
    5. Display → 6. Save
    """
    settings = get_settings()
    if n_posts is None:
        n_posts = settings.posts_per_run

    console.print("\n[bold]LinkedIn Post Pilot[/bold] — Starting daily pipeline\n")
    start = datetime.now()

    console.print("[bold]Step 1:[/bold] Collecting content...")
    content = await collect_content()
    if not content:
        console.print("[red]No content collected.[/red]")
        return []

    console.print("[bold]Step 2:[/bold] Ranking content...")
    ranked = rank_content(content)

    console.print("[bold]Step 3:[/bold] Running trend radar...")
    trends = await run_trend_radar(ranked)

    console.print(f"[bold]Step 4:[/bold] Multi-agent + hooks + scoring ({n_posts} posts)...")
    console.print("  [dim]Researcher → Writer → Critic → Revision → Hooks → Score[/dim]")
    posts = await generate(ranked, trends, n_posts=n_posts)

    display_posts(posts, trends)

    console.print("[bold]Step 6:[/bold] Saving to database...")
    await save_articles(ranked)
    await save_posts(posts)

    await cleanup_old_snapshots(keep_hours=72)

    elapsed = (datetime.now() - start).total_seconds()
    console.print(
        f"\n[bold green]Pipeline complete[/bold green] in {elapsed:.1f}s — "
        f"{len(posts)} posts generated\n"
    )

    return posts
