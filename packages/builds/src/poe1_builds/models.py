"""Domain models for the builds package.

Two layers coexist:

* **RemoteBuildRef / BuildsSnapshot** - lightweight, derived from the
  columnar protobuf search response. Suitable for listing hundreds of
  candidate builds without paying the ~150 KB/char detail cost.
* **FullBuild + friends** - the shape returned by
  ``GET /poe1/api/builds/{version}/character``, faithfully re-typed as
  Pydantic v2 models. The ``path_of_building_export`` field is the
  hydration handoff into :mod:`poe1_fob.pob`.

We deliberately keep ``item_data`` dicts pass-through (untyped ``dict``
with extra fields allowed): mirroring GGG's full item schema in Pydantic
buys nothing at this layer - the PoB parser already does the structural
work when ``path_of_building_export`` is round-tripped.
"""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DefenseType(StrEnum):
    """Coarse defence archetype used for filtering.

    Derived from :class:`DefensiveStats` - not an upstream dimension.
    See :func:`classify_defense` for the heuristic.
    """

    LIFE = "Life"
    LIFE_ES = "LifeES"
    ENERGY_SHIELD = "EnergyShield"
    CI = "CI"
    LOW_LIFE = "LowLife"
    HYBRID = "Hybrid"
    MOM = "MoM"


class BuildSortKey(StrEnum):
    """Sort columns we expose publicly; matches the server's ``sort_id``."""

    LEVEL = "level"
    LIFE = "life"
    ENERGY_SHIELD = "energyshield"
    EHP = "ehp"
    DPS = "dps"


class BuildStatus(IntEnum):
    """Raw status byte from the character endpoint.

    Values observed in live Mirage data; unknown statuses are passed
    through as :class:`int` - never coerced.
    """

    UNKNOWN = 0
    INACTIVE = 1
    OUTDATED = 2
    ACTIVE = 3


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class BuildFilter(BaseModel):
    """Server-side filter spec for :class:`BuildsSnapshot` ingestion.

    Every field is optional - unset means "no filter on that dimension".
    The ``class_`` field maps to poe.ninja's ``class`` query parameter,
    which is actually the **ascendancy** (ninja conflates the two).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    class_: str | None = Field(default=None, description="Ascendancy, e.g. 'Slayer'.")
    main_skill: str | None = Field(
        default=None,
        description="Main skill substring, matches poe.ninja's skills dimension.",
    )
    level_range: tuple[int, int] | None = Field(
        default=None,
        description="Inclusive (min, max) level range; clamped to [1, 100].",
    )
    defense_type: DefenseType | None = Field(
        default=None,
        description="Post-fetch filter (the API has no defense dimension).",
    )
    top_n_per_class: int | None = Field(
        default=200,
        ge=1,
        le=2000,
        description="Cap results per ascendancy. None = no cap.",
    )

    @field_validator("level_range")
    @classmethod
    def _validate_range(cls, value: tuple[int, int] | None) -> tuple[int, int] | None:
        if value is None:
            return None
        lo, hi = value
        if lo > hi:
            raise ValueError("level_range min cannot exceed max")
        if lo < 1 or hi > 100:
            raise ValueError("level_range must stay within [1, 100]")
        return value


# ---------------------------------------------------------------------------
# Lightweight reference (from columnar search response)
# ---------------------------------------------------------------------------


class RemoteBuildRef(BaseModel):
    """Lightweight handle on a poe.ninja character.

    Carries enough signal to rank/filter/present in a list; resolves to
    :class:`FullBuild` via :meth:`BuildsService.get_detail`.

    ``source_id`` is stable across snapshots of the same league:
    ``ninja::{league_url}::{account}::{character}`` - suitable as a
    cache key.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    source_id: str
    account: str
    character: str
    class_name: str = Field(alias="class")
    secondary_ascendancy: str | None = None
    level: int = Field(ge=1, le=100)
    life: int = Field(ge=0)
    energy_shield: int = Field(ge=0)
    ehp: int = Field(ge=0)
    dps: int = Field(ge=0)
    main_skill: str | None = None
    weapon_mode: str | None = None
    league: str
    snapshot_version: str
    fetched_at: datetime


# ---------------------------------------------------------------------------
# Columnar snapshot
# ---------------------------------------------------------------------------


class BuildsSnapshot(BaseModel):
    """Result of one search fetch: refs + bookkeeping.

    ``total`` is the **server-reported** count (may exceed ``len(refs)``
    when a top-N cap is applied client-side).
    """

    model_config = ConfigDict(frozen=True)

    league: str
    snapshot_version: str
    fetched_at: datetime
    total: int = Field(ge=0)
    refs: tuple[RemoteBuildRef, ...]

    def by_source_id(self, source_id: str) -> RemoteBuildRef | None:
        return next((r for r in self.refs if r.source_id == source_id), None)


# ---------------------------------------------------------------------------
# Full detail - mirrors the /character JSON endpoint
# ---------------------------------------------------------------------------


class DefensiveStats(BaseModel):
    """Defensive summary from the character endpoint.

    Field names mirror the JSON camelCase; over-cap resistances and
    penetration-visible "max hit taken" numbers are preserved.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    life: int = 0
    energy_shield: int = Field(default=0, alias="energyShield")
    mana: int = 0
    ward: int = 0
    movement_speed: int = Field(default=0, alias="movementSpeed")
    life_regen: int = Field(default=0, alias="lifeRegen")
    evasion_rating: int = Field(default=0, alias="evasionRating")
    armour: int = 0
    strength: int = 0
    dexterity: int = 0
    intelligence: int = 0
    endurance_charges: int = Field(default=0, alias="enduranceCharges")
    frenzy_charges: int = Field(default=0, alias="frenzyCharges")
    power_charges: int = Field(default=0, alias="powerCharges")
    effective_health_pool: int = Field(default=0, alias="effectiveHealthPool")
    physical_maximum_hit_taken: int = Field(default=0, alias="physicalMaximumHitTaken")
    fire_maximum_hit_taken: int = Field(default=0, alias="fireMaximumHitTaken")
    cold_maximum_hit_taken: int = Field(default=0, alias="coldMaximumHitTaken")
    lightning_maximum_hit_taken: int = Field(default=0, alias="lightningMaximumHitTaken")
    chaos_maximum_hit_taken: int = Field(default=0, alias="chaosMaximumHitTaken")
    fire_resistance: int = Field(default=0, alias="fireResistance")
    fire_resistance_over_cap: int = Field(default=0, alias="fireResistanceOverCap")
    cold_resistance: int = Field(default=0, alias="coldResistance")
    cold_resistance_over_cap: int = Field(default=0, alias="coldResistanceOverCap")
    lightning_resistance: int = Field(default=0, alias="lightningResistance")
    lightning_resistance_over_cap: int = Field(default=0, alias="lightningResistanceOverCap")
    chaos_resistance: int = Field(default=0, alias="chaosResistance")
    chaos_resistance_over_cap: int = Field(default=0, alias="chaosResistanceOverCap")
    block_chance: int = Field(default=0, alias="blockChance")
    spell_block_chance: int = Field(default=0, alias="spellBlockChance")
    spell_suppression_chance: int = Field(default=0, alias="spellSuppressionChance")
    spell_dodge_chance: int = Field(default=0, alias="spellDodgeChance")
    item_rarity: int = Field(default=0, alias="itemRarity")
    # Per-element conversion map from live Mirage data, e.g.
    # {"physical": 80, "fire": 20, "cold": 0, "lightning": 0, "chaos": 0}
    physical_taken_as: dict[str, int] = Field(default_factory=dict, alias="physicalTakenAs")
    lowest_maximum_hit_taken: int = Field(default=0, alias="lowestMaximumHitTaken")


class GemRef(BaseModel):
    """One gem slotted in a skill group.

    ``item_data`` holds the full GGG item dict pass-through; consumers
    that need structural access should parse it themselves (or route
    the ``path_of_building_export`` string through
    :mod:`poe1_fob.pob`).
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    name: str
    level: int = 0
    quality: int = 0
    is_built_in_support: bool = Field(default=False, alias="isBuiltInSupport")
    item_data: dict[str, Any] = Field(default_factory=dict, alias="itemData")


class SkillDps(BaseModel):
    """DPS summary attached to a skill group.

    ``damage_types`` / ``dot_damage_types`` are 5-slot arrays of
    integer percentages - one per damage class (fire/cold/lightning/
    physical/chaos, per live Mirage data). Kept as pass-through ints
    since the mapping isn't documented upstream.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    name: str = ""
    dps: int = 0
    dot_dps: int = Field(default=0, alias="dotDps")
    damage_types: tuple[int, ...] = Field(default=(), alias="damageTypes")
    dot_damage_types: tuple[int, ...] = Field(default=(), alias="dotDamageTypes")
    damage: tuple[int, ...] = ()


class SkillGroup(BaseModel):
    """One equipped item's socket group with gems and (optional) DPS."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    item_slot: int = Field(alias="itemSlot")
    all_gems: tuple[GemRef, ...] = Field(default=(), alias="allGems")
    dps: tuple[SkillDps, ...] = ()


class ItemEntry(BaseModel):
    """Equipped/inventory item; ``item_data`` is pass-through."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    item_slot: int = Field(alias="itemSlot")
    item_data: dict[str, Any] = Field(default_factory=dict, alias="itemData")


class KeystonePassive(BaseModel):
    """Keystone allocated on the passive tree."""

    model_config = ConfigDict(frozen=True, extra="allow")

    name: str
    icon: str = ""
    stats: tuple[str, ...] = ()


class MasteryChoice(BaseModel):
    """One mastery effect pick."""

    model_config = ConfigDict(frozen=True, extra="allow")

    name: str
    group: str


class ItemProvidedGemGroup(BaseModel):
    """Gems granted by items (e.g. Voideye, Curse on Hit helm)."""

    model_config = ConfigDict(frozen=True, extra="allow")

    slot: int
    gems: tuple[GemRef, ...] = ()


class FullBuild(BaseModel):
    """Full character payload as returned by poe.ninja.

    Mirrors the JSON keys 1:1 via camelCase aliases. Fields we don't
    yet use structurally (``cluster_jewels``, ``hashes_ex``, ``economy``)
    are kept as loose ``dict`` / ``list`` so round-tripping is lossless.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    # Identity
    account: str
    name: str
    league: str
    source_id: str
    snapshot_version: str
    fetched_at: datetime

    # Class & ascendancy
    level: int = Field(ge=1, le=100)
    class_name: str = Field(alias="class")
    base_class: str = Field(alias="baseClass")
    ascendancy_class_id: str | None = Field(default=None, alias="ascendancyClassId")
    ascendancy_class_name: str | None = Field(default=None, alias="ascendancyClassName")
    secondary_ascendancy_class_id: str | None = Field(
        default=None, alias="secondaryAscendancyClassId"
    )
    secondary_ascendancy_class_name: str | None = Field(
        default=None, alias="secondaryAscendancyClassName"
    )

    # Build export (the hydration handoff)
    path_of_building_export: str = Field(default="", alias="pathOfBuildingExport")

    # Stats
    defensive_stats: DefensiveStats = Field(default_factory=DefensiveStats, alias="defensiveStats")

    # Gear & skills
    skills: tuple[SkillGroup, ...] = ()
    items: tuple[ItemEntry, ...] = ()
    flasks: tuple[ItemEntry, ...] = ()
    jewels: tuple[ItemEntry, ...] = ()
    key_stones: tuple[KeystonePassive, ...] = Field(default=(), alias="keyStones")
    masteries: tuple[MasteryChoice, ...] = ()
    item_provided_gems: tuple[ItemProvidedGemGroup, ...] = Field(
        default=(), alias="itemProvidedGems"
    )

    # Tree state
    passive_selection: tuple[int, ...] = Field(default=(), alias="passiveSelection")
    passive_tree_name: str = Field(default="", alias="passiveTreeName")
    atlas_tree_name: str = Field(default="", alias="atlasTreeName")
    cluster_jewels: dict[str, Any] = Field(default_factory=dict, alias="clusterJewels")
    hashes_ex: list[Any] = Field(default_factory=list, alias="hashesEx")

    # Endgame choices
    bandit_choice: str | None = Field(default=None, alias="banditChoice")
    pantheon_major: str | None = Field(default=None, alias="pantheonMajor")
    pantheon_minor: str | None = Field(default=None, alias="pantheonMinor")
    use_second_weapon_set: bool = Field(default=False, alias="useSecondWeaponSet")

    # Freshness
    last_seen_utc: datetime | None = Field(default=None, alias="lastSeenUtc")
    updated_utc: datetime | None = Field(default=None, alias="updatedUtc")
    last_checked_utc: datetime | None = Field(default=None, alias="lastCheckedUtc")
    status: int = 0
    economy: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "BuildFilter",
    "BuildSortKey",
    "BuildStatus",
    "BuildsSnapshot",
    "DefenseType",
    "DefensiveStats",
    "FullBuild",
    "GemRef",
    "ItemEntry",
    "ItemProvidedGemGroup",
    "KeystonePassive",
    "MasteryChoice",
    "RemoteBuildRef",
    "SkillDps",
    "SkillGroup",
]
