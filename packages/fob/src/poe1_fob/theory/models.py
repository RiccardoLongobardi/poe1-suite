"""Pydantic models for the Theorycrafter Build Generator v2 (Step 40).

v2 is form-driven (no free-text query). A :class:`TheoryIntent` is the
structured input the user fills out via cascading selects; the
generator produces a :class:`BuildSkeleton` deterministically from
vendored 3.28 data (passive tree + gem tags + item bases).

The skeleton carries a complete, importable PoB code so the user can
paste it straight into Path of Building.

No camelCase aliases: like :class:`PobSnapshot`, these serialize with
their snake_case field names (the pydantic-mypy plugin rejects by-name
construction when aliases are set).

Note: we deliberately use a Theorycrafter-local :class:`TheoryIntent`
rather than extending :class:`poe1_core.models.build_intent.BuildIntent`
— the latter is the *Finder* intent (free text → ladder query) and
shares no semantics with the structured Theorycrafter input.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .viability import ViabilityReport

BudgetTier = Literal["starter", "mid", "endgame"]
DefenceArchetype = Literal["life", "es", "ward", "hybrid_life_es"]
ContentFocus = Literal["mapping", "bossing", "allcontent"]
DamageType = Literal["fire", "cold", "lightning", "chaos", "physical", "spell", "attack"]


class TheoryIntent(BaseModel):
    """Structured input to the Build Generator — one field per form select."""

    model_config = ConfigDict(frozen=True)

    character_class: str
    ascendancy: str
    primary_skill: str
    damage_type: DamageType
    defence_archetype: DefenceArchetype
    budget: BudgetTier
    focus: ContentFocus


class GemLink(BaseModel):
    """One active skill + its support gems (up to 5 supports = a 6L).

    ``extra_actives`` lets a single socket group host *several* active gems
    (Step 67) — used for a multi-aura group: ``skill`` + ``extra_actives``
    are all emitted as active gems in the same PoB socket group, with
    ``supports`` (e.g. ``Enlighten``) linked to all of them so PoB applies
    the support's reservation-efficiency to every aura in the group.
    """

    model_config = ConfigDict(frozen=True)

    skill: str
    supports: tuple[str, ...] = ()
    extra_actives: tuple[str, ...] = ()
    slot: str = ""
    label: str = ""
    # Optional level/quality override for the *active* skill gem (Step 74:
    # a corrupted 21/23 main skill is standard on a min-maxed build). None =
    # use the default (level 20, quality 20).
    skill_level: int | None = None
    skill_quality: int | None = None
    # Imbued support (3.28 corrupted-gem mechanic, QA #4): a corrupted skill
    # gem can carry an *additional* built-in support at level 1 that costs no
    # socket — effectively a 7th support on the main 6L. The value is the
    # support's base name WITHOUT " Support" (PoB appends it), e.g. "Increased
    # Critical Damage". None = no imbued support.
    imbued_support: str | None = None


class TreeNodeRef(BaseModel):
    """One passive-tree node referenced by the skeleton — real ids only."""

    model_config = ConfigDict(frozen=True)

    node_id: int
    name: str
    type: Literal["keystone", "notable", "ascendancy", "start", "travel", "mastery"]
    stats: tuple[str, ...] = ()
    # For ``type == "mastery"``: the chosen mastery-effect id (PoB needs
    # the (node, effect) pair to allocate it). None for every other type.
    effect_id: int | None = None


class GearSlot(BaseModel):
    """Recommended base + priority stats for one equipment slot."""

    model_config = ConfigDict(frozen=True)

    slot: str
    base_name: str
    stat_priorities: tuple[str, ...] = ()
    budget_tier: BudgetTier


class StatEstimate(BaseModel):
    """Stats for a generated build.

    For an on-the-fly generated build these are rough estimates derived
    from tree + gear weights and ``estimated`` is True. For a
    PoB-optimised precomputed build (Step 56) ``estimated`` is False and
    ``full_dps`` / ``total_ehp`` carry PoB's real calc output.
    """

    model_config = ConfigDict(frozen=True)

    life_estimate: int = Field(default=0, ge=0)
    es_estimate: int = Field(default=0, ge=0)
    dps_index: int = Field(default=0, ge=0)
    resistance_warning: str | None = None
    estimated: bool = True
    # PoB-exact numbers — populated only for precomputed/optimised builds
    # (Step 56). 0 on a freshly-generated estimate.
    full_dps: float = Field(default=0.0, ge=0)
    total_ehp: int = Field(default=0, ge=0)


class BuildSkeleton(BaseModel):
    """A complete from-scratch build skeleton."""

    model_config = ConfigDict(frozen=True)

    intent: TheoryIntent
    links: tuple[GemLink, ...] = ()
    tree_nodes: tuple[TreeNodeRef, ...] = ()
    gear_slots: tuple[GearSlot, ...] = ()
    stats: StatEstimate
    rationale_it: str
    rationale_en: str
    pob_code: str = Field(description="Base64+zlib PoB import code.")
    viability: ViabilityReport = Field(default_factory=ViabilityReport)
    # Step 56: True when this skeleton is a precomputed, PoB-exact-optimised
    # build served from the vendored optima rather than generated live.
    optimised: bool = False


class SkillEntry(BaseModel):
    """One active skill exposed by ``GET /fob/theory/skills``."""

    model_config = ConfigDict(frozen=True)

    name: str
    tags: tuple[str, ...] = ()
    damage_types: tuple[str, ...] = ()


class SkillsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    skills: tuple[SkillEntry, ...] = ()


__all__ = [
    "BudgetTier",
    "BuildSkeleton",
    "ContentFocus",
    "DamageType",
    "DefenceArchetype",
    "GearSlot",
    "GemLink",
    "SkillEntry",
    "SkillsResponse",
    "StatEstimate",
    "TheoryIntent",
    "TreeNodeRef",
]
