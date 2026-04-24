"""Build model.

A :class:`Build` is the normalised representation produced by every
:class:`BuildSource` implementation. Downstream modules (ranking, planner)
treat builds uniformly and must not branch on the originating source
beyond reading :attr:`Build.source_type`.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    Ascendancy,
    BuildSourceType,
    CharacterClass,
    ClearSpeedTier,
    ContentFocus,
    DamageProfile,
    DefenseProfile,
    ItemSlot,
    Playstyle,
)
from .item import Item
from .pricing import PriceRange


class BuildMetrics(BaseModel):
    """Numeric performance indicators for a build.

    All fields are optional because different sources expose different
    subsets (a PoB gives full detail; a poe.ninja ladder snapshot gives
    only a handful).
    """

    model_config = ConfigDict(frozen=True)

    total_dps: float | None = Field(default=None, ge=0.0)
    effective_hp: int | None = Field(default=None, ge=0)
    life: int | None = Field(default=None, ge=0)
    energy_shield: int | None = Field(default=None, ge=0)
    mana: int | None = Field(default=None, ge=0)
    chaos_res: int | None = Field(default=None, ge=-200, le=200)
    fire_res: int | None = Field(default=None, ge=-200, le=200)
    cold_res: int | None = Field(default=None, ge=-200, le=200)
    lightning_res: int | None = Field(default=None, ge=-200, le=200)
    phys_max_hit: float | None = Field(default=None, ge=0.0)
    ele_max_hit: float | None = Field(default=None, ge=0.0)
    movement_speed_pct: int | None = None
    clear_speed_tier: ClearSpeedTier | None = None


class KeyItem(BaseModel):
    """An item that defines the build — unique, or a notable rare.

    ``item`` keeps the full :class:`Item` for uniques; rares may provide
    only a rough description (``base_type`` + criteria mods).
    """

    model_config = ConfigDict(frozen=True)

    slot: ItemSlot
    item: Item
    importance: int = Field(default=1, ge=1, le=5, description="1 = nice-to-have, 5 = mandatory.")
    price: PriceRange | None = None


class Build(BaseModel):
    """Normalised representation of a PoE 1 build."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(..., min_length=1)
    source_type: BuildSourceType
    character_class: CharacterClass
    ascendancy: Ascendancy | None = None

    main_skill: str = Field(..., min_length=1)
    support_gems: list[str] = Field(default_factory=list)

    damage_profile: DamageProfile
    playstyle: Playstyle
    content_tags: list[ContentFocus] = Field(default_factory=list)
    defense_profile: DefenseProfile

    estimated_cost: PriceRange | None = None
    metrics: BuildMetrics = Field(default_factory=BuildMetrics)
    key_items: list[KeyItem] = Field(default_factory=list)

    pob_code: str | None = None
    origin_url: str | None = None
    tree_version: str | None = None
    league_slug: str | None = None
    captured_at: datetime | None = None

    @property
    def is_from_pob(self) -> bool:
        return self.source_type is BuildSourceType.POB


__all__ = ["Build", "BuildMetrics", "KeyItem"]
