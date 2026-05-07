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

        # Hydrate top-N candidates by DPS so the ranking engine actually
        # sees ``main_skill``. The protobuf list endpoint does not expose
        # the skills dictionary, so without hydration every ref carries
        # ``main_skill = None`` and the score_damage / score_playstyle
        # dimensions degenerate to neutral.
        # Cap kept low (50) because each detail fetch is one upstream
        # call; 50 x concurrency=4 ~= 12 s with a warm cache. Top by
        # ``dps`` gives a reasonable proxy for "popular endgame builds"
        # which is what the ranker should be looking at anyway.
        sorted_refs = sorted(snapshot.refs, key=lambda r: r.dps or 0, reverse=True)
        top_refs = tuple(sorted_refs[:50])
        if not top_refs:
            return ()

        try:
            full_builds = await asyncio.wait_for(
                svc.hydrate(top_refs, concurrency=4),
                timeout=timeout,
            )
        except TimeoutError:
            log.warning("source_aggregator_hydrate_timeout", refs=len(top_refs))
            return top_refs  # fall back to refs without main_skill

        # Replace each ref's ``main_skill`` field with the hydrated value
        # so the ranking engine can score on it.
        enriched: list[RemoteBuildRef] = []
        for ref, build in zip(top_refs, full_builds, strict=True):
            skill = BuildsService.main_skill_of(build)
            enriched.append(ref.model_copy(update={"main_skill": skill}))
        log.info(
            "source_aggregator_hydrated",
            hydrated=len(enriched),
            with_skill=sum(1 for r in enriched if r.main_skill),
        )
        return tuple(enriched)


__all__ = ["SourceAggregator"]
