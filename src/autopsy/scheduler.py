"""
Autopsy Scheduler — manages timed autopsy triggers after post selection.

When the user runs `pilot select`, this module:
1. Records the selection timestamp
2. Schedules a reminder/trigger 48h later
3. On trigger: either auto-scrape metrics (if cookies configured)
   or send a reminder notification to record metrics manually

Also handles the weekly digest schedule.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.utils.config import DATA_DIR

logger = logging.getLogger(__name__)

PENDING_FILE = DATA_DIR / "pending_autopsies.json"


# ── Pending Autopsy Queue ──────────────────────────────

def _load_pending() -> list[dict]:
    """Load pending autopsy queue from disk."""
    if not PENDING_FILE.exists():
        return []
    try:
        with open(PENDING_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_pending(pending: list[dict]) -> None:
    """Save pending autopsy queue to disk."""
    PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PENDING_FILE, "w") as f:
        json.dump(pending, f, indent=2, default=str)


def queue_autopsy(
    post_id: int,
    topic: str = "",
    delay_hours: int = 48,
) -> datetime:
    """
    Queue a post for autopsy after the specified delay.

    Called automatically by `pilot select`.

    Args:
        post_id: Database ID of the selected post
        topic: Post topic (for display in reminders)
        delay_hours: Hours to wait before triggering (default 48)

    Returns:
        The scheduled trigger time
    """
    trigger_at = datetime.now(timezone.utc) + timedelta(hours=delay_hours)

    pending = _load_pending()

    # Avoid duplicates
    existing_ids = {p["post_id"] for p in pending}
    if post_id in existing_ids:
        logger.info(f"Post {post_id} already queued for autopsy")
        # Return existing trigger time
        for p in pending:
            if p["post_id"] == post_id:
                return datetime.fromisoformat(p["trigger_at"])
        return trigger_at

    pending.append({
        "post_id": post_id,
        "topic": topic,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "trigger_at": trigger_at.isoformat(),
        "delay_hours": delay_hours,
        "status": "pending",
    })

    _save_pending(pending)

    logger.info(
        f"Autopsy queued: post {post_id} ({topic}) — "
        f"triggers at {trigger_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )

    return trigger_at


def get_due_autopsies() -> list[dict]:
    """
    Get all pending autopsies that are past their trigger time.

    Returns:
        List of due autopsy entries
    """
    pending = _load_pending()
    now = datetime.now(timezone.utc)

    due = []
    for entry in pending:
        if entry.get("status") != "pending":
            continue
        trigger = datetime.fromisoformat(entry["trigger_at"])
        if trigger.tzinfo is None:
            trigger = trigger.replace(tzinfo=timezone.utc)
        if now >= trigger:
            due.append(entry)

    return due


def mark_autopsy_done(post_id: int) -> None:
    """Mark a queued autopsy as completed."""
    pending = _load_pending()
    for entry in pending:
        if entry["post_id"] == post_id:
            entry["status"] = "completed"
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_pending(pending)


def get_pending_count() -> int:
    """Get count of pending (not yet due) autopsies."""
    pending = _load_pending()
    now = datetime.now(timezone.utc)
    count = 0
    for entry in pending:
        if entry.get("status") != "pending":
            continue
        trigger = datetime.fromisoformat(entry["trigger_at"])
        if trigger.tzinfo is None:
            trigger = trigger.replace(tzinfo=timezone.utc)
        if now < trigger:
            count += 1
    return count


def cleanup_old_entries(days: int = 30) -> int:
    """Remove completed autopsy entries older than N days."""
    pending = _load_pending()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    original_count = len(pending)
    pending = [
        e for e in pending
        if e.get("status") == "pending"
        or (
            e.get("completed_at")
            and datetime.fromisoformat(e["completed_at"]).replace(tzinfo=timezone.utc) > cutoff
        )
    ]
    removed = original_count - len(pending)

    if removed:
        _save_pending(pending)
        logger.info(f"Cleaned up {removed} old autopsy entries")

    return removed


# ── Check and Remind ───────────────────────────────────

async def check_due_autopsies(auto_notify: bool = True) -> list[dict]:
    """
    Check for autopsies that are due and notify/remind the user.

    This is called:
    - At the start of every `pilot run` pipeline
    - By the daily scheduler

    Args:
        auto_notify: Whether to print reminders to console

    Returns:
        List of due autopsy entries
    """
    due = get_due_autopsies()

    if not due:
        return []

    if auto_notify:
        from rich.console import Console
        console = Console()

        console.print(f"\n[bold yellow]📋 {len(due)} autopsy reminder(s)[/bold yellow]")
        for entry in due:
            hours_ago = (
                datetime.now(timezone.utc) -
                datetime.fromisoformat(entry["trigger_at"]).replace(tzinfo=timezone.utc)
            ).total_seconds() / 3600

            console.print(
                f"  Post {entry['post_id']}: [bold]{entry.get('topic', 'Unknown')}[/bold] "
                f"— published {entry['delay_hours']}h+ ago"
            )
            console.print(
                f"  [dim]Run: pilot autopsy {entry['post_id']} "
                f"-r <reactions> -c <comments> -s <shares>[/dim]"
            )
            console.print()

    return due


async def send_autopsy_reminder_email(due_entries: list[dict]) -> bool:
    """
    Send an email reminder for due autopsies.

    Called by the daily scheduler when autopsies are overdue.
    """
    if not due_entries:
        return False

    from src.utils.config import get_settings
    settings = get_settings()
    email_to = settings.email_to

    if not email_to:
        return False

    # Build simple reminder email
    items_html = "\n".join(
        f"<li><strong>Post {e['post_id']}</strong>: {e.get('topic', 'Unknown')} "
        f"— published {e['delay_hours']}h ago<br>"
        f"<code>pilot autopsy {e['post_id']} -r &lt;reactions&gt; -c &lt;comments&gt;</code></li>"
        for e in due_entries
    )

    html = f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:20px;">
<h2>📋 Autopsy Reminders</h2>
<p>{len(due_entries)} post(s) are ready for performance review:</p>
<ul>{items_html}</ul>
<p>Check your LinkedIn analytics and record the numbers to help the agent learn.</p>
</body></html>"""

    try:
        from src.delivery.sender import send_email
        return await send_email(
            to=email_to,
            subject=f"📋 {len(due_entries)} LinkedIn post(s) ready for autopsy",
            html_body=html,
        )
    except Exception as e:
        logger.warning(f"Failed to send autopsy reminder email: {e}")
        return False
