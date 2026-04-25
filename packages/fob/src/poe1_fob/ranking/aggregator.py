"""SourceAggregator — fetch build candidates from all configured sources.

V1 wraps :class:`~poe1_builds.service.BuildsService` (poe.ninja ladder).
Future sources (pobb.in registry, user-submitted builds, …) slot in here
without touching the engine or router.

Design notes:
* The aggregator applies **no pre-filtering** based on the intent — it
  fetches all builds and lets :class:`~.engine.RankingEngine` do the smart
  work.  This keeps the aggregator simple and makes the scoring deterministic.
* A per-source ``timeout`` prevents one slow source from blocking the
  response.  On timeout the source contributes an empty tuple (fail-open).
"""

from __future__ import annotations

import asyncio

from poe1_builds.models import BuildFilter, RemoteBuildRef
from poe1_builds.service import BuildsService
from poe1_core.models.build_intent import BuildIntent
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient
from poe1_shared.logging import get_logger

log = get_logger(__name__)


class SourceAggregator:
    """Merge build candidates from all sources into one flat tuple."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_candidates(
        self,
        intent: BuildIntent,
        *,
        http: HttpClient,
        timeout: float = 10.0,
    ) -> tuple[RemoteBuildRef, ...]:
        """Fetch refs from all sources and return them merged.

        *intent* is accepted for future use (e.g. choosing which ascendancies
        to fan out to based on the damage profile).  Currently unused — all 19
        ascendancies are queried and the engine scores the full pool.

        Args:
            intent:  The player's structured build request (not used in V1
                     filtering, but available for future source routing).
            http:    Shared :class:`HttpClient` (cache + retry already wired).
            timeout: Per-source wall-clock timeout in seconds.  Exceeded
                     sources contribute zero refs (fail-open).
        """
        # intent is reserved for future per-source routing; suppress lint.
        _ = intent

        league = self._settings.poe_league
        svc = BuildsService(http=http, league=league)

        try:
            snapshot = await asyncio.wait_for(
                svc.fetch_refs(BuildFilter()),
                timeout=timeout,
            )
        except TimeoutError:
            log.warning(
                "source_aggregator_timeout",
                source="poe_ninja",
                league=league,
                timeout=timeout,
            )
            return ()

        log.info(
            "source_aggregator_fetched",
            source="poe_ninja",
            league=league,
            refs=len(snapshot.refs),
        )
        return snapshot.refs


__all__ = ["SourceAggregator"]
