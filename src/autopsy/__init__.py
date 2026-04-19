"""
Post Autopsy — the self-improving feedback loop.

Complete flow:
  pilot select 42 --hook B --technique contrarian
    → Records hook selection (hook_learner)
    → Queues 48h autopsy reminder (scheduler)

  pilot autopsy 42 -r 500 -c 30
    → Creates autopsy report (report_builder)
    → Marks queue entry as done (scheduler)

  pilot learn
    → Recalibrates scoring weights (calibrator)
    → Updates persona DNA with angle/hook preferences (persona_updater)
    → Updates content memory with topic performance (memory_updater)
    → Learns hook preferences from selections (hook_learner)

  pilot analyze
    → Deep pattern detection across all data (analyzer)

  pilot digest
    → Weekly performance summary (digest_builder)
"""

from src.autopsy.report_builder import create_autopsy, PostAutopsy, compute_engagement_score
from src.autopsy.calibrator import recalibrate, load_weights
from src.autopsy.analyzer import analyze_performance, AnalysisReport
from src.autopsy.persona_updater import update_persona_from_autopsies
from src.autopsy.memory_updater import update_memory_from_autopsies
from src.autopsy.hook_learner import (
    record_hook_selection,
    compute_hook_preferences,
    update_persona_hook_preferences,
)
from src.autopsy.scheduler import (
    queue_autopsy,
    check_due_autopsies,
    get_due_autopsies,
    mark_autopsy_done,
)
from src.autopsy.digest_builder import build_weekly_digest, format_digest_text
