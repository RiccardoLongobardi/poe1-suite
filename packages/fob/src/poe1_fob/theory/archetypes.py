"""Archetype catalogue for the Theorycrafter Build Generator.

Loads the vendored, hand-curated ``data/gems/archetypes_3_28.json`` —
~18 real PoE 3.28 build archetypes. This is the *only* place class /
ascendancy / skill / support-gem knowledge enters Theorycrafter: it is
a small, stable, reviewable data file, not a data warehouse.

`resolve_archetype` scores every archetype against a parsed
:class:`BuildIntent` and picks the best fit. Ties break on a static
``popularity`` rank (lower = more popular) — no live ladder call, so
generation stays synchronous, offline and deterministic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from poe1_core.models.build_intent import BuildIntent

_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "gems" / "archetypes_3_28.json"


@dataclass(frozen=True, slots=True)
class Archetype:
    """One curated build archetype."""

    skill_id: str
    skill_name: str
    tags: tuple[str, ...]
    gem_type: str
    canonical_supports: tuple[str, ...]
    class_name: str
    ascendancy: str
    keystones: tuple[str, ...]
    defence: str
    damage_type: str
    content: str
    popularity: int
    rationale_it: str
    rationale_en: str


@lru_cache(maxsize=1)
def get_archetypes() -> tuple[Archetype, ...]:
    """Load and cache the archetype catalogue."""
    if not _DATA_PATH.exists():  # pragma: no cover - deployment guard
        raise FileNotFoundError(
            f"Archetype catalogue not found at {_DATA_PATH}.",
        )
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    out: list[Archetype] = []
    for e in raw:
        out.append(
            Archetype(
                skill_id=str(e["skill_id"]),
                skill_name=str(e["skill_name"]),
                tags=tuple(e.get("tags", [])),
                gem_type=str(e.get("gem_type", "active")),
                canonical_supports=tuple(e.get("canonical_supports", [])),
                class_name=str(e["class_name"]),
                ascendancy=str(e["ascendancy"]),
                keystones=tuple(e.get("keystones", [])),
                defence=str(e.get("defence", "life")),
                damage_type=str(e.get("damage_type", "physical")),
                content=str(e.get("content", "mapping")),
                popularity=int(e.get("popularity", 999)),
                rationale_it=str(e["rationale_it"]),
                rationale_en=str(e["rationale_en"]),
            ),
        )
    return tuple(out)


def _score(arch: Archetype, intent: BuildIntent) -> int:
    """Score how well *arch* matches *intent*. Higher = better."""
    score = 0

    hint = (intent.main_skill_hint or "").strip().lower()
    if hint and (hint in arch.skill_name.lower() or hint in arch.skill_id):
        score += 10

    cls = (intent.class_filter or "").strip().lower()
    if cls and cls in (arch.class_name.lower(), arch.ascendancy.lower()):
        score += 5

    if intent.damage_profile is not None:
        # DamageProfile values: "fire", "cold_dot", "bleed", ... — match
        # the archetype damage type / tags loosely.
        dp = intent.damage_profile.value.lower()
        if arch.damage_type in dp or dp.split("_")[0] in arch.tags:
            score += 3

    focuses = {cf.focus.value for cf in intent.content_focus}
    if arch.content in focuses or (arch.content == "allcontent" and focuses):
        score += 2

    return score


def resolve_archetype(intent: BuildIntent) -> Archetype:
    """Pick the best-fit archetype for *intent*.

    Always returns an archetype — when nothing scores, the most popular
    one is the deliberate fallback (never crashes on a vague query).
    """
    archs = get_archetypes()
    best = max(
        archs,
        key=lambda a: (_score(a, intent), -a.popularity),
    )
    return best


__all__ = ["Archetype", "get_archetypes", "resolve_archetype"]
