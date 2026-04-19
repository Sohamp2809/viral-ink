"""Virality Scoring Engine — predicts each post's viral potential (0-100%)."""

from src.scorer.engine import score_post, ViralityScore

__all__ = ["score_post", "ViralityScore"]
