"""Ranking Engine — filter hard constraints, score, sort, top-N.

Usage::

    engine = RankingEngine()
    ranked = engine.rank(intent, refs, top_n=10)

Pipeline:

1. **Hard-constraint filter** — drops any ref that violates a
   :class:`~poe1_core.models.enums.HardConstraint` from the intent.
   Detection is keyword-based on ``main_skill`` and life/ES ratios;
   constraints that can't be reliably detected from a ref are silently
   skipped (safe default = don't eliminate).

2. **Score** — :func:`~.scorer.score_ref` computes a
   :class:`~.models.ScoreBreakdown` for each remaining candidate using
   pool-relative DPS percentiles for budget scoring.

3. **Sort + top-N** — descending by ``total`` score; ties are broken by
   the natural iteration order (deterministic per call).
"""

from __future__ import annotations

from poe1_builds.models import RemoteBuildRef
from poe1_core.models.build_intent import BuildIntent
from poe1_core.models.enums import HardConstraint

from .models import RankedBuild
from .scorer import score_ref

# ---------------------------------------------------------------------------
# Hard-constraint detection helpers
# ---------------------------------------------------------------------------

_MELEE_KEYWORDS: frozenset[str] = frozenset(
    {
        "strike",
        "slam",
        "cyclone",
        "blade flurry",
        "flicker",
        "ground slam",
        "cleave",
        "reave",
        "consecrated path",
        "earthquake",
        "lacerate",
        "bladestorm",
    }
)
_MINION_KEYWORDS: frozenset[str] = frozenset(
    {
        "summon",
        "skeleton",
        "zombie",
        "spectre",
        "animate",
        "raging spirit",
        "golem",
        "carrion",
        "absolution",
        "reaper",
    }
)
_TOTEM_KEYWORDS: frozenset[str] = frozenset({"totem", "ballista"})
_TRAP_MINE_KEYWORDS: frozenset[str] = frozenset({"trap", "mine"})
_RF_KEYWORDS: frozenset[str] = frozenset({"righteous fire"})


def _skill_has(ref: RemoteBuildRef, keywords: frozenset[str]) -> bool:
    skill = (ref.main_skill or "").casefold()
    return any(kw in skill for kw in keywords)


def _is_ci(ref: RemoteBuildRef) -> bool:
    """True if the ref appears to be a Chaos Inoculation build."""
    return ref.life <= 1 and ref.energy_shield > 0


def _is_low_life(ref: RemoteBuildRef) -> bool:
    """True if the ref appears to be a Low-Life build (not CI)."""
    return 1 < ref.life <= 50 and ref.energy_shield > 0


def _passes_constraint(ref: RemoteBuildRef, constraint: HardConstraint) -> bool:
    """Return ``True`` if *ref* satisfies *constraint* (should be kept).

    Constraints that cannot be reliably inferred from a lightweight ref
    (:attr:`HardConstraint.NO_SELF_CAST`, :attr:`HardConstraint.HARDCORE_VIABLE`,
    :attr:`HardConstraint.SSF_VIABLE`) always return ``True`` — the caller
    may apply them at the full-build hydration stage instead.
    """
    if constraint == HardConstraint.NO_MELEE:
        return not _skill_has(ref, _MELEE_KEYWORDS)
    if constraint == HardConstraint.NO_MINION:
        return not _skill_has(ref, _MINION_KEYWORDS)
    if constraint == HardConstraint.NO_TOTEM:
        return not _skill_has(ref, _TOTEM_KEYWORDS)
    if constraint == HardConstraint.NO_TRAP_MINE:
        return not _skill_has(ref, _TRAP_MINE_KEYWORDS)
    if constraint == HardConstraint.NO_RF:
        return not _skill_has(ref, _RF_KEYWORDS)
    if constraint == HardConstraint.NO_CI:
        return not _is_ci(ref)
    if constraint == HardConstraint.NO_LOW_LIFE:
        return not _is_low_life(ref)
    # NO_SELF_CAST / HARDCORE_VIABLE / SSF_VIABLE — insufficient signal in refs
    return True


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class RankingEngine:
    """Stateless engine: filter → score → sort → top-N."""

    def filter_hard_constraints(
        self,
        refs: list[RemoteBuildRef],
        intent: BuildIntent,
    ) -> list[RemoteBuildRef]:
        """Drop refs that violate any hard constraint in *intent*."""
        if not intent.hard_constraints:
            return refs
        return [r for r in refs if all(_passes_constraint(r, c) for c in intent.hard_constraints)]

    def rank(
        self,
        intent: BuildIntent,
        refs: tuple[RemoteBuildRef, ...] | list[RemoteBuildRef],
        *,
        top_n: int = 10,
    ) -> list[RankedBuild]:
        """Filter, score, sort, and return the top *top_n* builds.

        Returns an empty list when no candidates survive the constraint filter.
        """
        candidates = self.filter_hard_constraints(list(refs), intent)
        if not candidates:
            return []

        pool_dps_sorted = tuple(sorted(r.dps for r in candidates))

        scored = [(r, score_ref(r, intent, pool_dps_sorted=pool_dps_sorted)) for r in candidates]
        scored.sort(key=lambda x: x[1].total, reverse=True)

        return [
            RankedBuild(ref=ref, score=breakdown, rank=i + 1)
            for i, (ref, breakdown) in enumerate(scored[:top_n])
        ]


__all__ = ["RankingEngine"]
