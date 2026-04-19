"""
Hook Learner — tracks which hook variants (A/B/C) the user picks
over time and updates hook_preferences in Persona DNA.

After enough selections (10+), the agent knows which persuasion
techniques work best for this user's audience and biases future
hook generation accordingly.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone, timedelta

import yaml
from sqlalchemy import select

from src.utils.config import CONFIG_DIR
from src.utils.db import get_session, GeneratedPost, Base
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

logger = logging.getLogger(__name__)

PERSONA_PATH = CONFIG_DIR / "persona_dna.yaml"


# ── Database Model ──────────────────────────────────────

class HookSelection(Base):
    """Records which hook variant was selected for each published post."""

    __tablename__ = "hook_selections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(Integer)
    hook_variant: Mapped[str] = mapped_column(String(10), default="A")   # A, B, C
    hook_technique: Mapped[str] = mapped_column(String(50), default="")  # contrarian, question, etc.
    selected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


# ── Recording ──────────────────────────────────────────

async def record_hook_selection(
    post_id: int,
    hook_variant: str = "A",
    hook_technique: str = "",
) -> bool:
    """
    Record which hook variant the user selected.

    Called by `pilot select` — stores the choice for later learning.

    Args:
        post_id: Database ID of the generated post
        hook_variant: "A", "B", or "C"
        hook_technique: The technique used (contrarian, question, etc.)

    Returns:
        True if recorded successfully
    """
    from src.utils.db import get_engine
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    try:
        async with session:
            selection = HookSelection(
                post_id=post_id,
                hook_variant=hook_variant.upper(),
                hook_technique=hook_technique,
                selected_at=datetime.now(timezone.utc),
            )
            session.add(selection)
            await session.commit()

        logger.info(f"Recorded hook selection: post {post_id} → variant {hook_variant} ({hook_technique})")
        return True

    except Exception as e:
        logger.error(f"Failed to record hook selection: {e}")
        return False


# ── Learning ───────────────────────────────────────────

async def compute_hook_preferences(days: int = 90) -> dict[str, float]:
    """
    Analyze hook selections and compute preference scores per technique.

    Returns a dict of technique → preference score (0-1).
    Higher = user picks this technique more often.

    Example output:
        {"contrarian": 0.35, "question": 0.25, "statistic": 0.20, ...}
    """
    from src.utils.db import get_engine
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    async with session:
        result = await session.execute(
            select(HookSelection).where(HookSelection.selected_at >= cutoff)
        )
        selections = result.scalars().all()

    if not selections:
        return {}

    # Count technique selections
    technique_counts = Counter(
        s.hook_technique for s in selections
        if s.hook_technique
    )

    total = sum(technique_counts.values())
    if total == 0:
        return {}

    # Also track variant preference (A vs B vs C)
    variant_counts = Counter(s.hook_variant for s in selections)

    preferences = {
        technique: count / total
        for technique, count in technique_counts.items()
    }

    logger.info(
        f"Hook preferences computed from {len(selections)} selections: "
        f"top technique = {technique_counts.most_common(1)[0][0] if technique_counts else 'none'}, "
        f"variant distribution = {dict(variant_counts)}"
    )

    return preferences


async def update_persona_hook_preferences(
    days: int = 90,
    min_selections: int = 10,
) -> dict | None:
    """
    Compute hook preferences and save them to persona_dna.yaml.

    The writer prompt can use these to bias hook generation toward
    techniques the user prefers.

    Args:
        days: Window of data to analyze
        min_selections: Minimum selections needed before updating

    Returns:
        Updated preferences dict, or None if not enough data
    """
    preferences = await compute_hook_preferences(days=days)

    if len(preferences) < 2:
        logger.info("Not enough hook selection data to update preferences")
        return None

    total_selections = sum(1 for _ in preferences.values())

    # We need the actual selection count, not unique techniques
    from src.utils.db import get_engine
    engine = await get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = await get_session()
    async with session:
        result = await session.execute(select(HookSelection))
        all_selections = result.scalars().all()

    if len(all_selections) < min_selections:
        logger.info(
            f"Only {len(all_selections)} hook selections "
            f"(need {min_selections}) — skipping update"
        )
        return None

    # Load and update persona
    if not PERSONA_PATH.exists():
        logger.warning("persona_dna.yaml not found")
        return None

    with open(PERSONA_PATH) as f:
        persona = yaml.safe_load(f) or {}

    # Sort by preference (highest first)
    sorted_prefs = dict(
        sorted(preferences.items(), key=lambda x: x[1], reverse=True)
    )

    persona.setdefault("learned_preferences", {})
    persona["learned_preferences"]["hook_preferences"] = {
        technique: round(score, 3)
        for technique, score in sorted_prefs.items()
    }
    persona["learned_preferences"]["hook_stats"] = {
        "total_selections": len(all_selections),
        "favorite_technique": max(preferences, key=preferences.get) if preferences else "",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }

    # Variant preference (does user prefer alternatives over originals?)
    variant_counts = Counter(s.hook_variant for s in all_selections)
    total_v = sum(variant_counts.values())
    if total_v > 0:
        persona["learned_preferences"]["variant_preference"] = {
            v: round(c / total_v, 3)
            for v, c in variant_counts.most_common()
        }

    with open(PERSONA_PATH, "w") as f:
        yaml.dump(persona, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info(
        f"Hook preferences saved to persona — "
        f"favorite: {sorted_prefs and list(sorted_prefs.keys())[0] or 'none'}"
    )

    return sorted_prefs


def get_hook_preferences() -> dict[str, float]:
    """Load saved hook preferences from persona, if they exist."""
    if not PERSONA_PATH.exists():
        return {}

    with open(PERSONA_PATH) as f:
        persona = yaml.safe_load(f) or {}

    return persona.get("learned_preferences", {}).get("hook_preferences", {})
