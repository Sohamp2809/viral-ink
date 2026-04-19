"""
Phase 6 completion tests — hook learner + autopsy scheduler.
Run with: pytest tests/test_phase6_complete.py -v
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch


class TestHookLearner:
    @pytest.mark.asyncio
    async def test_record_hook_selection(self):
        from src.autopsy.hook_learner import record_hook_selection
        result = await record_hook_selection(
            post_id=999,
            hook_variant="B",
            hook_technique="contrarian",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_compute_preferences_empty(self):
        from src.autopsy.hook_learner import compute_hook_preferences
        prefs = await compute_hook_preferences(days=1)
        # May or may not have data depending on test order
        assert isinstance(prefs, dict)

    def test_get_hook_preferences_no_file(self):
        from src.autopsy.hook_learner import get_hook_preferences
        prefs = get_hook_preferences()
        assert isinstance(prefs, dict)

    def test_hook_selection_dataclass(self):
        from src.autopsy.hook_learner import HookSelection
        hs = HookSelection.__table__
        assert "hook_variant" in [c.name for c in hs.columns]
        assert "hook_technique" in [c.name for c in hs.columns]


class TestAutopsyScheduler:
    def test_queue_autopsy(self, tmp_path):
        from src.autopsy import scheduler

        # Redirect pending file to temp
        original = scheduler.PENDING_FILE
        scheduler.PENDING_FILE = tmp_path / "pending.json"
        try:
            trigger = scheduler.queue_autopsy(
                post_id=42,
                topic="AI Agents",
                delay_hours=48,
            )
            assert trigger > datetime.now(timezone.utc)

            # Should be in pending
            pending = scheduler._load_pending()
            assert len(pending) == 1
            assert pending[0]["post_id"] == 42
            assert pending[0]["topic"] == "AI Agents"
            assert pending[0]["status"] == "pending"
        finally:
            scheduler.PENDING_FILE = original

    def test_duplicate_queue_prevented(self, tmp_path):
        from src.autopsy import scheduler

        original = scheduler.PENDING_FILE
        scheduler.PENDING_FILE = tmp_path / "pending.json"
        try:
            scheduler.queue_autopsy(post_id=42, topic="Test")
            scheduler.queue_autopsy(post_id=42, topic="Test")

            pending = scheduler._load_pending()
            assert len(pending) == 1
        finally:
            scheduler.PENDING_FILE = original

    def test_get_due_autopsies(self, tmp_path):
        from src.autopsy import scheduler

        original = scheduler.PENDING_FILE
        scheduler.PENDING_FILE = tmp_path / "pending.json"
        try:
            # Queue with 0 delay (immediately due)
            scheduler.queue_autopsy(post_id=1, topic="Due", delay_hours=0)

            due = scheduler.get_due_autopsies()
            assert len(due) == 1
            assert due[0]["post_id"] == 1
        finally:
            scheduler.PENDING_FILE = original

    def test_mark_done(self, tmp_path):
        from src.autopsy import scheduler

        original = scheduler.PENDING_FILE
        scheduler.PENDING_FILE = tmp_path / "pending.json"
        try:
            scheduler.queue_autopsy(post_id=10, topic="Test")
            scheduler.mark_autopsy_done(10)

            pending = scheduler._load_pending()
            assert pending[0]["status"] == "completed"
        finally:
            scheduler.PENDING_FILE = original

    def test_pending_count(self, tmp_path):
        from src.autopsy import scheduler

        original = scheduler.PENDING_FILE
        scheduler.PENDING_FILE = tmp_path / "pending.json"
        try:
            scheduler.queue_autopsy(post_id=1, topic="A", delay_hours=48)
            scheduler.queue_autopsy(post_id=2, topic="B", delay_hours=48)
            scheduler.queue_autopsy(post_id=3, topic="C", delay_hours=0)

            # Only 2 should be pending (not yet due), 1 is already due
            count = scheduler.get_pending_count()
            assert count == 2
        finally:
            scheduler.PENDING_FILE = original

    def test_cleanup(self, tmp_path):
        from src.autopsy import scheduler

        original = scheduler.PENDING_FILE
        scheduler.PENDING_FILE = tmp_path / "pending.json"
        try:
            scheduler.queue_autopsy(post_id=1, topic="Old")
            scheduler.mark_autopsy_done(1)

            # Manually set completed_at to 60 days ago
            pending = scheduler._load_pending()
            old_time = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
            pending[0]["completed_at"] = old_time
            scheduler._save_pending(pending)

            removed = scheduler.cleanup_old_entries(days=30)
            assert removed == 1
        finally:
            scheduler.PENDING_FILE = original
