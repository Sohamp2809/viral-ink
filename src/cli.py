"""
CLI Interface — all commands for LinkedIn Post Pilot.

Complete command list:
    pilot run              # Full pipeline (checks due autopsies first)
    pilot run -n 5 -e      # Generate 5 + email
    pilot run -n 3 -p      # Generate 3 + preview in browser
    pilot schedule         # Start daily scheduler
    pilot onboard          # Set up Persona DNA
    pilot calibrate        # Test voice match
    pilot collect          # Just collect content
    pilot select ID        # Mark post as published → queues 48h autopsy + records hook
    pilot autopsy ID       # Record actual performance
    pilot learn            # Full feedback loop (scoring + persona + memory + hooks)
    pilot analyze          # Deep pattern analysis
    pilot digest           # Weekly summary
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="pilot",
    help="LinkedIn Post Pilot — AI agent for daily LinkedIn content",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ── Run Pipeline ────────────────────────────────────────

@app.command()
def run(
    posts: int = typer.Option(None, "--posts", "-n", help="Number of posts to generate"),
    email: bool = typer.Option(False, "--email", "-e", help="Send results via email"),
    preview: bool = typer.Option(False, "--preview", "-p", help="Preview email in browser"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run the full pipeline. Checks for due autopsies first."""
    _setup_logging("DEBUG" if verbose else "INFO")

    async def _run():
        # Check for due autopsies before running pipeline
        from src.autopsy.scheduler import check_due_autopsies
        await check_due_autopsies(auto_notify=True)

        from src.main import run_pipeline
        result = await run_pipeline(n_posts=posts)

        if result and (email or preview):
            from src.delivery.email_builder import build_email_html
            subject, html = build_email_html(result, [])

            if preview:
                preview_path = Path("data/email_preview.html")
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                preview_path.write_text(html, encoding="utf-8")
                console.print(f"\n[bold]Email preview saved:[/bold] {preview_path.resolve()}")
                import webbrowser
                webbrowser.open(f"file://{preview_path.resolve()}")

            if email:
                from src.delivery.sender import send_daily_email
                await send_daily_email(result, [])

        return result

    result = asyncio.run(_run())
    if not result:
        raise typer.Exit(code=1)


# ── Schedule ────────────────────────────────────────────

@app.command()
def schedule(
    hour: int = typer.Option(5, "--hour", help="Hour to run (24h format)"),
    minute: int = typer.Option(0, "--minute", help="Minute to run"),
    tz: str = typer.Option("UTC", "--tz", help="Timezone"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Start the daily scheduler. Runs pipeline + checks autopsies automatically."""
    _setup_logging("DEBUG" if verbose else "INFO")

    console.print(f"\n[bold]Starting daily scheduler[/bold]")
    console.print(f"  Pipeline: {hour:02d}:{minute:02d} {tz}")
    console.print(f"  Autopsy reminders: checked at each run")
    console.print(f"  Press Ctrl+C to stop\n")

    from src.delivery.scheduler import start_scheduler
    start_scheduler(hour=hour, minute=minute, timezone_str=tz)


# ── Collect Only ────────────────────────────────────────

@app.command()
def collect(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """Just collect and rank content (no generation)."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from src.main import collect_content, rank_content

    async def _collect():
        items = await collect_content()
        ranked = rank_content(items)
        console.print(f"\n[bold]Top 10 items:[/bold]\n")
        for i, item in enumerate(ranked[:10], 1):
            age = f"{item.age_hours:.0f}h ago" if item.age_hours < 48 else f"{item.age_hours/24:.0f}d ago"
            console.print(f"  {i:2}. [{item.source_name}] {item.title}")
            console.print(f"      {age} · score: {item.weight:.1f}\n")

    asyncio.run(_collect())


# ── Onboard ─────────────────────────────────────────────

@app.command()
def onboard(
    file: Path = typer.Option(None, "--file", "-f", help="Text file with posts separated by ---"),
):
    """Set up your Persona DNA by analyzing your LinkedIn posts."""
    _setup_logging("INFO")

    posts: list[str] = []

    if file and file.exists():
        raw = file.read_text()
        posts = [p.strip() for p in raw.split("---") if p.strip() and len(p.strip()) > 50]
        console.print(f"Loaded {len(posts)} posts from {file}")
    else:
        console.print("\n[bold]Persona DNA Onboarding[/bold]\n")
        console.print("Paste posts one at a time. Press Enter twice after each, type 'done' to finish.\n")
        while True:
            console.print(f"[dim]Post {len(posts) + 1} (or 'done'):[/dim]")
            lines = []
            while True:
                line = input()
                if line.strip().lower() == "done":
                    break
                lines.append(line)
                if len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
                    break
            text = "\n".join(lines).strip()
            if not text or text.lower() == "done":
                break
            if len(text) > 50:
                posts.append(text)
                console.print(f"  [green]✓ Post {len(posts)} added ({len(text)} chars)[/green]\n")
            if len(posts) >= 20:
                break

    if len(posts) < 2:
        console.print("[red]Need at least 2 posts.[/red]")
        raise typer.Exit(code=1)

    from src.persona.profile_builder import build_profile
    from src.utils.llm import get_llm

    config = asyncio.run(build_profile(posts, get_llm()))
    console.print("[bold green]Persona DNA created![/bold green]")
    tone = config.get("tone", {})
    console.print(f"  Formality:     {tone.get('formality', 0.5):.1f}/1.0")
    console.print(f"  Assertiveness: {tone.get('assertiveness', 0.5):.1f}/1.0")
    console.print(f"  Vulnerability: {tone.get('vulnerability', 0.5):.1f}/1.0")
    console.print(f"  Humor:         {tone.get('humor_frequency', 0.3):.1f}/1.0")
    console.print(f"\nRun [bold]pilot calibrate[/bold] to test the voice match.\n")


# ── Calibrate ───────────────────────────────────────────

@app.command()
def calibrate(verbose: bool = typer.Option(False, "--verbose", "-v")):
    """Test if generated posts match your voice."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from src.persona.calibrator import run_calibration
    from src.utils.config import load_persona
    from src.utils.llm import get_llm

    try:
        persona = load_persona()
    except FileNotFoundError:
        console.print("[red]No persona_dna.yaml. Run `pilot onboard` first.[/red]")
        raise typer.Exit(code=1)

    result = asyncio.run(run_calibration(persona, get_llm()))
    for i, (post, score) in enumerate(zip(result.generated_posts, result.voice_match_scores), 1):
        color = "green" if score >= 0.7 else "yellow" if score >= 0.5 else "red"
        console.print(f"[bold]Test Post {i}[/bold] — Voice match: [{color}]{score:.0%}[/{color}]")
        console.print(f"[dim]{post[:200]}...[/dim]\n")
    status = "PASSED" if result.passed else "NEEDS WORK"
    color = "green" if result.passed else "red"
    console.print(f"[bold {color}]{status}[/bold {color}] — Average: {result.avg_score:.0%}\n")


# ── Select Post (wired to autopsy scheduler + hook learner) ──

@app.command()
def select(
    post_id: int = typer.Argument(help="Database ID of the post to mark as selected"),
    hook: str = typer.Option("A", "--hook", help="Which hook variant was used (A/B/C)"),
    hook_technique: str = typer.Option("", "--technique", "-t", help="Hook technique (contrarian, question, etc.)"),
    delay: int = typer.Option(48, "--delay", help="Hours before autopsy reminder (default 48)"),
):
    """Mark a post as published. Queues 48h autopsy reminder + records hook choice."""
    _setup_logging("INFO")

    async def _select():
        # 1. Mark as selected in database
        from src.delivery.tracker import mark_post_selected
        success = await mark_post_selected(post_id, hook)
        if not success:
            console.print(f"[red]Post {post_id} not found[/red]")
            return False

        # 2. Get post topic for the reminder
        from src.utils.db import get_session, GeneratedPost
        from sqlalchemy import select as sql_select
        session = await get_session()
        async with session:
            result = await session.execute(
                sql_select(GeneratedPost).where(GeneratedPost.id == post_id)
            )
            post = result.scalar_one_or_none()
        topic = post.topic if post else "Unknown"

        # 3. Record hook selection for learning
        from src.autopsy.hook_learner import record_hook_selection
        await record_hook_selection(
            post_id=post_id,
            hook_variant=hook,
            hook_technique=hook_technique,
        )

        # 4. Queue autopsy reminder (48h timer)
        from src.autopsy.scheduler import queue_autopsy
        trigger_at = queue_autopsy(
            post_id=post_id,
            topic=topic,
            delay_hours=delay,
        )

        console.print(f"[green]✓ Post {post_id} marked as selected[/green]")
        console.print(f"  Hook: {hook.upper()} ({hook_technique or 'unspecified'})")
        console.print(f"  Autopsy reminder: {trigger_at.strftime('%Y-%m-%d %H:%M UTC')}")
        console.print(f"\n[dim]After {delay}h, run: pilot autopsy {post_id} -r <reactions> -c <comments>[/dim]")
        return True

    success = asyncio.run(_select())
    if not success:
        raise typer.Exit(code=1)


# ── Autopsy ─────────────────────────────────────────────

@app.command()
def autopsy(
    post_id: int = typer.Argument(help="Database ID of the published post"),
    reactions: int = typer.Option(0, "--reactions", "-r", help="LinkedIn reaction count"),
    comments: int = typer.Option(0, "--comments", "-c", help="Comment count"),
    shares: int = typer.Option(0, "--shares", "-s", help="Share/repost count"),
    impressions: int = typer.Option(0, "--impressions", "-i", help="Impression count"),
):
    """Record a post's actual performance and analyze what worked."""
    _setup_logging("INFO")

    async def _autopsy():
        from src.autopsy.report_builder import create_autopsy
        result = await create_autopsy(
            post_id=post_id,
            reactions=reactions,
            comments=comments,
            shares=shares,
            impressions=impressions,
        )

        if not result:
            console.print(f"[red]Post {post_id} not found[/red]")
            return None

        # Mark autopsy as done in the scheduler queue
        from src.autopsy.scheduler import mark_autopsy_done
        mark_autopsy_done(post_id)

        return result

    result = asyncio.run(_autopsy())
    if not result:
        raise typer.Exit(code=1)

    error_color = "green" if abs(result.prediction_error) < 15 else "yellow" if abs(result.prediction_error) < 25 else "red"

    console.print(f"\n[bold]Post Autopsy — {result.topic}[/bold]\n")
    console.print(f"  Predicted:  {result.predicted_score:.0f}%")
    console.print(f"  Actual:     {result.actual_score:.0f}%")
    console.print(f"  Error:      [{error_color}]{result.prediction_error:+.0f}[/{error_color}]")
    console.print(f"  Reactions:  {result.reactions}  Comments: {result.comments}  Shares: {result.shares}")
    console.print()
    console.print(f"  [green]✓ What worked:[/green]  {result.what_worked}")
    console.print(f"  [red]✗ What didn't:[/red]  {result.what_didnt}")
    console.print(f"  [cyan]→ Lesson:[/cyan]       {result.lesson}")
    console.print()
    console.print(f"[dim]Run `pilot learn` to feed this into the scoring model and persona.[/dim]\n")


# ── Learn (Full Feedback Loop) ──────────────────────────

@app.command()
def learn(
    days: int = typer.Option(30, "--days", "-d", help="Days of data to learn from"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run the FULL feedback loop: scoring + persona + memory + hooks."""
    _setup_logging("DEBUG" if verbose else "INFO")

    async def _learn():
        console.print("\n[bold]Running feedback loop[/bold]\n")
        steps_done = 0

        # Step 1: Recalibrate scoring weights
        console.print("[bold]Step 1:[/bold] Recalibrating scoring weights...")
        from src.autopsy.calibrator import recalibrate
        new_weights = await recalibrate()
        if new_weights:
            console.print(f"  [green]✓ Weights updated[/green]")
            for signal, weight in new_weights.items():
                console.print(f"    {signal}: {weight:.0%}")
            steps_done += 1
        else:
            console.print(f"  [yellow]Not enough data yet[/yellow]")

        # Step 2: Update persona DNA
        console.print("[bold]Step 2:[/bold] Updating Persona DNA...")
        from src.autopsy.persona_updater import update_persona_from_autopsies
        updated_persona = await update_persona_from_autopsies(days=days)
        if updated_persona:
            prefs = updated_persona.get("learned_preferences", {})
            strong = prefs.get("strong_angles", [])
            weak = prefs.get("weak_angles", [])
            console.print(f"  [green]✓ Persona updated[/green]")
            if strong:
                console.print(f"    Strong angles: {', '.join(strong)}")
            if weak:
                console.print(f"    Weak angles: {', '.join(weak)}")
            steps_done += 1
        else:
            console.print(f"  [yellow]Not enough data yet[/yellow]")

        # Step 3: Update content memory
        console.print("[bold]Step 3:[/bold] Updating content memory...")
        from src.autopsy.memory_updater import update_memory_from_autopsies
        nodes_updated = await update_memory_from_autopsies(days=days)
        if nodes_updated > 0:
            console.print(f"  [green]✓ {nodes_updated} memory nodes updated[/green]")
            steps_done += 1
        else:
            console.print(f"  [yellow]No memory updates needed[/yellow]")

        # Step 4: Update hook preferences
        console.print("[bold]Step 4:[/bold] Learning hook preferences...")
        from src.autopsy.hook_learner import update_persona_hook_preferences
        hook_prefs = await update_persona_hook_preferences(days=days)
        if hook_prefs:
            console.print(f"  [green]✓ Hook preferences updated[/green]")
            for technique, score in list(hook_prefs.items())[:3]:
                console.print(f"    {technique}: {score:.0%}")
            steps_done += 1
        else:
            console.print(f"  [yellow]Not enough hook selection data yet[/yellow]")

        # Step 5: Clean up old autopsy queue entries
        from src.autopsy.scheduler import cleanup_old_entries
        cleaned = cleanup_old_entries(days=30)
        if cleaned:
            console.print(f"  [dim]Cleaned {cleaned} old queue entries[/dim]")

        if steps_done > 0:
            console.print(f"\n[bold green]Feedback loop complete — {steps_done}/4 systems updated[/bold green]\n")
        else:
            console.print(f"\n[yellow]No updates made. Need more data:[/yellow]")
            console.print(f"  1. Publish posts and run `pilot select <id>`")
            console.print(f"  2. After 48h, run `pilot autopsy <id> -r <reactions> -c <comments>`")
            console.print(f"  3. Repeat for 5+ posts, then run `pilot learn` again\n")

    asyncio.run(_learn())


# ── Analyze ─────────────────────────────────────────────

@app.command()
def analyze(
    days: int = typer.Option(30, "--days", "-d", help="Days of data to analyze"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Deep pattern analysis across all autopsy data."""
    _setup_logging("DEBUG" if verbose else "INFO")

    from src.autopsy.analyzer import analyze_performance

    async def _analyze():
        from src.utils.llm import get_cheap_llm
        llm = get_cheap_llm()
        return await analyze_performance(days=days, llm=llm)

    report = asyncio.run(_analyze())

    console.print(f"\n[bold]Performance Analysis — Last {days} days[/bold]\n")
    console.print(f"  Posts analyzed:       {report.total_posts}")
    console.print(f"  Avg predicted:       {report.avg_predicted:.0f}%")
    console.print(f"  Avg actual:          {report.avg_actual:.0f}%")
    console.print(f"  Prediction accuracy: {report.accuracy:.0f}%")
    if report.best_angle:
        console.print(f"  Best angle:          [green]{report.best_angle}[/green]")
    if report.worst_angle:
        console.print(f"  Worst angle:         [red]{report.worst_angle}[/red]")

    if report.patterns:
        console.print(f"\n[bold]Detected Patterns[/bold]\n")
        for p in report.patterns:
            confidence_bar = "●" * int(p.confidence * 5) + "○" * (5 - int(p.confidence * 5))
            console.print(Panel(
                f"[dim]{p.evidence}[/dim]\n\n→ {p.recommendation}",
                title=f"{p.description} [{confidence_bar}]",
                border_style="cyan",
                width=70,
            ))

    if report.recommendations:
        console.print(f"\n[bold]Top Recommendations[/bold]")
        for r in report.recommendations:
            if r:
                console.print(f"  → {r}")
    console.print()


# ── Weekly Digest ───────────────────────────────────────

@app.command()
def digest(
    days: int = typer.Option(7, "--days", "-d", help="Days to summarize"),
    recalibrate_flag: bool = typer.Option(False, "--recalibrate", help="Also recalibrate scoring"),
):
    """Show weekly performance summary."""
    _setup_logging("INFO")

    from src.autopsy.digest_builder import build_weekly_digest, format_digest_text
    digest_data = asyncio.run(build_weekly_digest(days))
    console.print(format_digest_text(digest_data))

    if recalibrate_flag:
        from src.autopsy.calibrator import recalibrate as do_recalibrate
        result = asyncio.run(do_recalibrate())
        if result:
            console.print(f"\n[green]Scoring weights recalibrated:[/green]")
            for signal, weight in result.items():
                console.print(f"  {signal}: {weight:.0%}")
        else:
            console.print("\n[yellow]Not enough data to recalibrate.[/yellow]")


if __name__ == "__main__":
    app()
