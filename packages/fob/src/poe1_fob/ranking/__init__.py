"""Ranking Engine — public API.

Typical call sequence::

    agg    = SourceAggregator(settings)
    refs   = await agg.fetch_candidates(intent, http=http)
    engine = RankingEngine()
    ranked = engine.rank(intent, refs, top_n=10)
"""

from __future__ import annotations

from .aggregator import SourceAggregator
from .engine import RankingEngine
from .models import RankedBuild, RecommendRequest, RecommendResponse, ScoreBreakdown

__all__ = [
    "RankedBuild",
    "RankingEngine",
    "RecommendRequest",
    "RecommendResponse",
    "ScoreBreakdown",
    "SourceAggregator",
]
