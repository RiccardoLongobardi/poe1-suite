"""High-level builds facade.

Downstream consumers (the /builds FastAPI router, the FOB advisor)
should import :class:`BuildsService` and never touch
:mod:`poe1_builds.sources` directly. That isolation lets us add a
second source (pobb.in ladder, player-submitted PoB registry, …)
later without rewriting the router.

V1 responsibilities:

1. **Multi-class fan-out.** poe.ninja caps search results at 100 rows
   per call; to return "top 200 per class" we drive one search per
   ascendancy and merge. Fan-out is concurrent via
   :func:`asyncio.gather` so 19 calls complete in roughly the wall
   time of one.
2. **Lazy hydration.** :meth:`fetch_refs` is cheap; callers decide
   which refs to resolve to :class:`FullBuild` via :meth:`get_detail`.
3. **Post-fetch filters.** Two filter dimensions can't be expressed on
   the server: ``main_skill`` (the skills dictionary isn't exposed,
   so we recover the main skill from the character's largest DPS
   entry) and ``defense_type`` (derived from :class:`DefensiveStats`).
   These live here, applied to hydrated :class:`FullBuild` batches.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from poe1_shared.http import HttpClient
from poe1_shared.logging import get_logger

from .models import (
    BuildFilter,
    BuildsSnapshot,
    DefenseType,
    DefensiveStats,
    FullBuild,
    RemoteBuildRef,
    SkillDps,
    SkillGroup,
)
from .sources.ninja import NinjaBuildsSource

log = get_logger(__name__)


# The 19 ascendancies poe.ninja indexes as its ``class`` dimension.
# Order matters only for determinism — we fan out concurrently, then
# merge in this order so ties resolve predictably.
DEFAULT_ASCENDANCIES: tuple[str, ...] = (
    "Slayer",
    "Gladiator",
    "Champion",
    "Juggernaut",
    "Berserker",
    "Chieftain",
    "Raider",
    "Deadeye",
    "Pathfinder",
    "Occultist",
    "Elementalist",
    "Necromancer",
    "Assassin",
    "Saboteur",
    "Trickster",
    "Inquisitor",
    "Hierophant",
    "Guardian",
    "Ascendant",
)


class BuildsService:
    """Facade over one or more build sources.

    V1 is poe.ninja-only. Extra sources slot in by extending
    :meth:`fetch_refs` with a fallback loop — the primary source's
    refs are returned first, with secondary sources filling only the
    gaps.
    """

    def __init__(
        self,
        *,
        http: HttpClient,
        league: str,
        ascendancies: tuple[str, ...] = DEFAULT_ASCENDANCIES,
    ) -> None:
        self._ninja = NinjaBuildsSource(http, league)
        self._league = league
        self._ascendancies = ascendancies

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def league(self) -> str:
        return self._league

    async def fetch_refs(self, filt: BuildFilter | None = None) -> BuildsSnapshot:
        """Return a refs-only snapshot for ``filt``.

        * If ``filt.class_`` is set → one per-class search.
        * Otherwise → fan out across :attr:`_ascendancies` concurrently
          and merge. The resulting ``total`` is the sum of server-
          reported totals (each per-class call reports its own count).
        """

        filt = filt or BuildFilter()

        if filt.class_:
            return await self._ninja.fetch_snapshot(filt)

        # Multi-class fan-out. Reuse ``filt`` but override ``class_``
        # per request so each call pins a single ascendancy and
        # the source's top_n_per_class cap applies per class.
        per_class_filters = tuple(
            filt.model_copy(update={"class_": asc}) for asc in self._ascendancies
        )
        snapshots = await asyncio.gather(
            *(self._ninja.fetch_snapshot(f) for f in per_class_filters),
            return_exceptions=False,
        )
        merged_refs: list[RemoteBuildRef] = []
        total = 0
        snapshot_version = ""
        for snap in snapshots:
            merged_refs.extend(snap.refs)
            total += snap.total
            # All fan-out shards hit the same version; pick the first
            # non-empty string defensively in case one slot missed.
            snapshot_version = snapshot_version or snap.snapshot_version

        # The caller's top_n is *per class*; the merged list respects
        # that implicitly because each shard is already capped.
        fetched_at = datetime.now(UTC)
        league_name = self._ninja.league_api_name
        log.info(
            "builds_fanout_merge",
            league=league_name,
            ascendancies=len(self._ascendancies),
            refs=len(merged_refs),
            total=total,
        )
        return BuildsSnapshot(
            league=league_name,
            snapshot_version=snapshot_version,
            fetched_at=fetched_at,
            total=total,
            refs=tuple(merged_refs),
        )

    async def get_detail(self, ref: RemoteBuildRef) -> FullBuild:
        """Hydrate a ref to its :class:`FullBuild` payload."""

        result = await self._ninja.fetch_build_detail(ref)
        assert isinstance(result, FullBuild)
        return result

    async def hydrate(
        self,
        refs: tuple[RemoteBuildRef, ...],
        *,
        concurrency: int = 4,
    ) -> tuple[FullBuild, ...]:
        """Hydrate a batch of refs concurrently, bounded.

        poe.ninja serves one character per HTTP call and tolerates
        moderate parallelism. The default (4) keeps us below the
        informal rate limit while still overlapping I/O latency.
        """

        sem = asyncio.Semaphore(concurrency)

        async def _one(ref: RemoteBuildRef) -> FullBuild:
            async with sem:
                return await self.get_detail(ref)

        return tuple(await asyncio.gather(*(_one(r) for r in refs)))

    # ------------------------------------------------------------------
    # Post-fetch filters
    # ------------------------------------------------------------------

    @staticmethod
    def classify_defense(stats: DefensiveStats) -> DefenseType:
        """Assign a :class:`DefenseType` from a character's defensive stats.

        Heuristic (tuned against live Mirage data):

        * Life == 1 and Energy Shield > 0 → **LowLife** if CI-like
          thresholds aren't met, else **CI**.
        * Energy Shield > 3 * Life → **EnergyShield**.
        * Energy Shield > Life / 2 → **LifeES** (hybrid).
        * Mana pool > 2 * Life → **MoM** (Mind over Matter).
        * Otherwise → **Life**.

        The classifier is deliberately conservative: when life is
        effectively zero (the CI or Low-Life cases) we key off
        ``life == 1`` which is the post-CI engine reading.
        """

        life = stats.life
        es = stats.energy_shield
        mana = stats.mana

        if life <= 1 and es > 0:
            # CI / Low-Life zone. Ninja doesn't expose CI directly, so
            # we treat "life at baseline + ES > 5000" as CI-ish.
            return DefenseType.CI if es >= 5000 else DefenseType.LOW_LIFE

        if es >= max(1, life) * 3:
            return DefenseType.ENERGY_SHIELD

        if es >= max(1, life) // 2:
            return DefenseType.LIFE_ES

        if mana >= max(1, life) * 2:
            return DefenseType.MOM

        return DefenseType.LIFE

    @staticmethod
    def main_skill_of(build: FullBuild) -> str | None:
        """Identify the character's main skill from its skill groups.

        We pick the gem from the skill group with the largest DPS
        entry, ignoring built-in support gems. This mirrors
        poe.ninja's own heuristic (from the columnar ``skills``
        field_id), but works entirely off the hydrated payload.
        """

        best_dps = -1
        best_name: str | None = None
        for sg in build.skills:
            top = _top_dps(sg)
            if top is None:
                continue
            if top.dps + top.dot_dps <= best_dps:
                continue
            # First non-built-in-support gem in the group is the one
            # ninja treats as "the skill".
            primary = _primary_gem(sg)
            if primary is None:
                continue
            best_dps = top.dps + top.dot_dps
            best_name = primary
        return best_name

    @classmethod
    def matches_main_skill(cls, build: FullBuild, needle: str) -> bool:
        """Case-insensitive substring match over the computed main skill."""

        if not needle:
            return True
        name = cls.main_skill_of(build)
        if name is None:
            return False
        return needle.strip().casefold() in name.casefold()

    @classmethod
    def matches_defense_type(cls, build: FullBuild, want: DefenseType) -> bool:
        """Classify the build's defence and compare to ``want``."""

        return cls.classify_defense(build.defensive_stats) is want


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _top_dps(sg: SkillGroup) -> SkillDps | None:
    """Return the SkillDps entry with the highest combined dps, or None."""

    best: SkillDps | None = None
    best_total = -1
    for d in sg.dps:
        total = d.dps + d.dot_dps
        if total > best_total:
            best = d
            best_total = total
    return best


def _primary_gem(sg: SkillGroup) -> str | None:
    """First gem in the group that isn't a built-in support."""

    for g in sg.all_gems:
        if g.is_built_in_support:
            continue
        if g.name:
            return g.name
    return None


__all__ = [
    "DEFAULT_ASCENDANCIES",
    "BuildsService",
]
