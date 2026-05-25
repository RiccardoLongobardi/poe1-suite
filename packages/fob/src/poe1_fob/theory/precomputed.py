"""Precomputed, PoB-exact-optimised builds (Step 56).

The Theorycrafter generator produces a viable build live (on Render, with
no PoB runtime). For the popular archetypes we go further *offline*:
``scripts/precompute_builds.py`` runs the local PoB-exact optimiser
(``scripts/optimize_build.py``) over a curated matrix, captures the
optimised tree + supports + gear + **real** PoB stats, and writes them to
``packages/fob/data/theory/precomputed_3_28.json``.

This module is the live-serving half: given a :class:`TheoryIntent`, return
the matching precomputed :class:`BuildSkeleton` (real DPS/EHP, ``optimised
= True``) if one exists, else ``None`` so the caller falls back to live
generation. The vendored JSON is the only thing Render serves — PoB never
runs in production.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from poe1_shared.logging import get_logger

from .models import BuildSkeleton, TheoryIntent

log = get_logger(__name__)

_DATA_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "theory" / "precomputed_3_28.json"
)


def _intent_key(intent: TheoryIntent) -> tuple[str, ...]:
    """A hashable key identifying an archetype (the full structured intent)."""
    return (
        intent.character_class,
        intent.ascendancy,
        intent.primary_skill,
        intent.damage_type,
        intent.defence_archetype,
        intent.budget,
        intent.focus,
    )


@lru_cache(maxsize=1)
def _load() -> dict[tuple[str, ...], BuildSkeleton]:
    """Parse the vendored optima into an intent-keyed map (cached)."""
    if not _DATA_PATH.exists():
        return {}
    try:
        raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - corrupt vendor file
        log.warning("precomputed_load_failed", error=str(exc))
        return {}
    out: dict[tuple[str, ...], BuildSkeleton] = {}
    for entry in raw.get("builds", []):
        try:
            skeleton = BuildSkeleton.model_validate(entry)
        except Exception as exc:  # pragma: no cover - skip a malformed entry
            log.warning("precomputed_entry_invalid", error=str(exc))
            continue
        out[_intent_key(skeleton.intent)] = skeleton
    return out


def lookup(intent: TheoryIntent) -> BuildSkeleton | None:
    """Return the precomputed optimised build for *intent*, or ``None``.

    An exact match on all seven structured fields is required — a
    precomputed optimum is only valid for the exact archetype it was
    optimised for.
    """
    return _load().get(_intent_key(intent))


def available_count() -> int:
    """How many precomputed archetypes are vendored (for diagnostics)."""
    return len(_load())


__all__ = ["available_count", "lookup"]
