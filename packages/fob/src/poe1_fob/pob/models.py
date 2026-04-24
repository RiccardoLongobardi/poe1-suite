"""Structured view of a Path of Building export.

These models carry the *complete* PoB detail — passive tree, jewels,
item text, config options, pantheon, bandit — and are scoped to this
package. The cross-source abstraction used by the rest of the Oracle
pipeline is :class:`poe1_core.Build`; see :mod:`poe1_fob.pob.mapper`
for the reducer that produces one from a :class:`PobSnapshot`.

All models are frozen: parsers return immutable snapshots so callers
upstream can cache and share them without copy-on-read.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from poe1_core.models.enums import (
    Ascendancy,
    CharacterClass,
    ItemRarity,
    ItemSlot,
)


class PobGem(BaseModel):
    """A single gem inside a skill (socket) group."""

    model_config = ConfigDict(frozen=True)

    name: str  # human-readable, e.g. "Raise Spectre"
    skill_id: str  # PoE internal id, e.g. "RaiseSpectre" / "SupportEmpower"
    level: int = Field(ge=1, le=40)
    quality: int = Field(ge=0, le=30)
    enabled: bool = True
    is_support: bool


class PobSkillGroup(BaseModel):
    """A socket group: one active gem plus its supports (mechanically)."""

    model_config = ConfigDict(frozen=True)

    socket_group: int  # 1-based index inside <SkillSet>
    label: str | None = None
    enabled: bool = True
    is_main: bool = False
    gems: tuple[PobGem, ...]


class PobItem(BaseModel):
    """One item in the build: unique/rare/magic/normal + mod lines."""

    model_config = ConfigDict(frozen=True)

    pob_id: int  # <Item id="..."> — referenced by <Slot itemId="...">
    rarity: ItemRarity
    name: str | None = None  # unique name or rare title; None for magic/normal
    base_type: str
    item_level: int | None = None
    level_req: int | None = None
    sockets: str | None = None
    implicits: tuple[str, ...] = ()
    explicits: tuple[str, ...] = ()
    corrupted: bool = False
    raw_text: str  # original <Item> body for debugging & round-trip


class PobJewel(BaseModel):
    """Jewel socketed into the passive tree (vs a slot on gear)."""

    model_config = ConfigDict(frozen=True)

    slot_node_id: int
    item: PobItem


class PobPassiveTree(BaseModel):
    """Decoded passive tree spec (URL + extracted node ids)."""

    model_config = ConfigDict(frozen=True)

    spec_title: str | None = None
    tree_version: str | None = None  # e.g. "3_26"
    class_id: int
    ascendancy_id: int
    url: str
    node_ids: tuple[int, ...]
    # node_id -> effect_id (masteries picked on the tree)
    mastery_effects: dict[int, int] = Field(default_factory=dict)


class PobPantheon(BaseModel):
    """Pantheon soul picks."""

    model_config = ConfigDict(frozen=True)

    major: str | None = None  # "Solaris" / "Lunaris" / "Arakaali" / "Brine King"
    minor: str | None = None


class PobConfigOption(BaseModel):
    """One entry under <Config>: a knob the user toggled in PoB."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: str  # stored as string to handle bool/int/str uniformly


class PobSnapshot(BaseModel):
    """Full structured snapshot of a PoB export.

    This is the canonical input to :func:`snapshot_to_build`. Downstream
    modules (ranking, planner) consume the lean :class:`poe1_core.Build`
    produced by the mapper — keep PoB-specific detail out of those
    interfaces.
    """

    model_config = ConfigDict(frozen=True)

    target_version: str  # PoB's targetVersion, e.g. "3_0"
    character_class: CharacterClass
    ascendancy: Ascendancy | None
    level: int = Field(ge=1, le=100)
    main_skill_group_index: int  # 1-based index into skills
    bandit: str  # "None" / "Alira" / "Oak" / "Kraityn"
    pantheon: PobPantheon

    # All PlayerStat name->value pairs kept verbatim for the mapper.
    stats: dict[str, float] = Field(default_factory=dict)

    skills: tuple[PobSkillGroup, ...] = ()
    items_by_slot: dict[ItemSlot, PobItem] = Field(default_factory=dict)
    inventory: tuple[PobItem, ...] = ()  # unequipped but present
    flasks: tuple[PobItem, ...] = ()
    jewels: tuple[PobJewel, ...] = ()
    tree: PobPassiveTree
    notes: str = ""
    config: tuple[PobConfigOption, ...] = ()

    export_code: str  # original base64+zlib blob
    origin_url: str | None = None  # pobb.in / pastebin URL if known


__all__ = [
    "PobConfigOption",
    "PobGem",
    "PobItem",
    "PobJewel",
    "PobPantheon",
    "PobPassiveTree",
    "PobSkillGroup",
    "PobSnapshot",
]
