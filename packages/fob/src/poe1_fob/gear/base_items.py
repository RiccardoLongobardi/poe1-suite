"""Loader for the vendored repoe-fork base-item catalogue.

Reads ``packages/fob/data/items/base_items.json`` (extracted from
``repoe-fork/repoe-fork.github.io`` via :mod:`scripts.extract_base_items`)
and exposes:

* :class:`BaseItem` — pruned per-base record (name + item_class + tags).
* :func:`get_base_catalogue` — cached accessor for the full catalogue.
* :func:`base_for_name` — case-sensitive name lookup ("Stygian Vise" → BaseItem).
* :func:`bases_for_slot` — return every base mapped to a given ``ItemSlot``,
  used by the substitution picker in :mod:`poe1_fob.gear.dynamic`.

Slot mapping rules (``BaseItem.item_class`` → :class:`ItemSlot`):

* ``Body Armour`` → ``BODY_ARMOUR``
* ``Helmet`` / ``Gloves`` / ``Boots`` → respective slot
* ``Belt`` → ``BELT``; ``Amulet`` → ``AMULET``; ``Ring`` → ``RING``
* ``Shield`` → ``WEAPON_OFFHAND``; ``Quiver`` → ``QUIVER``
* Every weapon class (One/Two Hand Sword/Axe/Mace/Bow/Wand/Dagger/Sceptre/Staff/Claw)
  → ``WEAPON_MAIN``
* Every flask class → ``FLASK``
* ``Jewel`` / ``AbyssJewel`` / cultural jewel families → ``JEWEL``
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from poe1_core.models.enums import ItemSlot

_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "items" / "base_items.json"


@dataclass(frozen=True, slots=True)
class BaseItem:
    """Pruned base-item record."""

    metadata_path: str  # e.g. "Metadata/Items/Belts/BeltAbyss"
    name: str  # "Stygian Vise"
    item_class: str  # "Belt", "Body Armour", ...
    drop_level: int | None
    tags: tuple[str, ...]
    slot: ItemSlot


# Map repoe-fork ``item_class`` → our ItemSlot enum.
_CLASS_TO_SLOT: dict[str, ItemSlot] = {
    "Body Armour": ItemSlot.BODY_ARMOUR,
    "Helmet": ItemSlot.HELMET,
    "Gloves": ItemSlot.GLOVES,
    "Boots": ItemSlot.BOOTS,
    "Belt": ItemSlot.BELT,
    "Amulet": ItemSlot.AMULET,
    "Ring": ItemSlot.RING,
    "Shield": ItemSlot.WEAPON_OFFHAND,
    "Quiver": ItemSlot.QUIVER,
    # Weapons → main hand
    "One Hand Sword": ItemSlot.WEAPON_MAIN,
    "Two Hand Sword": ItemSlot.WEAPON_MAIN,
    "Thrusting One Hand Sword": ItemSlot.WEAPON_MAIN,
    "One Hand Axe": ItemSlot.WEAPON_MAIN,
    "Two Hand Axe": ItemSlot.WEAPON_MAIN,
    "One Hand Mace": ItemSlot.WEAPON_MAIN,
    "Two Hand Mace": ItemSlot.WEAPON_MAIN,
    "Sceptre": ItemSlot.WEAPON_MAIN,
    "Staff": ItemSlot.WEAPON_MAIN,
    "Warstaff": ItemSlot.WEAPON_MAIN,
    "Bow": ItemSlot.WEAPON_MAIN,
    "Wand": ItemSlot.WEAPON_MAIN,
    "Claw": ItemSlot.WEAPON_MAIN,
    "Dagger": ItemSlot.WEAPON_MAIN,
    "Rune Dagger": ItemSlot.WEAPON_MAIN,
    # Flasks
    "LifeFlask": ItemSlot.FLASK,
    "ManaFlask": ItemSlot.FLASK,
    "HybridFlask": ItemSlot.FLASK,
    "UtilityFlask": ItemSlot.FLASK,
    # Jewels — all cultural variants and abyss go to the JEWEL slot.
    "Jewel": ItemSlot.JEWEL,
    "AbyssJewel": ItemSlot.JEWEL,
    "HighlanderJewel": ItemSlot.JEWEL,
    "KaruiJewel": ItemSlot.JEWEL,
    "EternalJewel": ItemSlot.JEWEL,
    "MarakethJewel": ItemSlot.JEWEL,
    "TemplarJewel": ItemSlot.JEWEL,
    "VaalJewel": ItemSlot.JEWEL,
}


def _build_catalogue(raw: Mapping[str, Mapping[str, object]]) -> tuple[BaseItem, ...]:
    out: list[BaseItem] = []
    for path, entry in raw.items():
        name = entry.get("name")
        cls = entry.get("item_class")
        if not isinstance(name, str) or not isinstance(cls, str):
            continue
        slot = _CLASS_TO_SLOT.get(cls)
        if slot is None:
            continue
        drop_level_raw = entry.get("drop_level")
        drop_level = drop_level_raw if isinstance(drop_level_raw, int) else None
        tags_raw = entry.get("tags") or ()
        tags = (
            tuple(t for t in tags_raw if isinstance(t, str)) if isinstance(tags_raw, list) else ()
        )
        out.append(
            BaseItem(
                metadata_path=path,
                name=name,
                item_class=cls,
                drop_level=drop_level,
                tags=tags,
                slot=slot,
            )
        )
    return tuple(out)


@lru_cache(maxsize=1)
def get_base_catalogue() -> tuple[BaseItem, ...]:
    """Return all released gear bases. ~1030 entries."""

    if not _DATA_PATH.exists():
        raise FileNotFoundError(
            f"Base items JSON not found at {_DATA_PATH}. "
            "Run `uv run python scripts/extract_base_items.py` to fetch it."
        )
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return _build_catalogue(raw)


@lru_cache(maxsize=1)
def _bases_by_name() -> dict[str, BaseItem]:
    return {b.name: b for b in get_base_catalogue()}


@lru_cache(maxsize=1)
def _bases_by_slot() -> dict[ItemSlot, tuple[BaseItem, ...]]:
    by_slot: dict[ItemSlot, list[BaseItem]] = {}
    for base in get_base_catalogue():
        by_slot.setdefault(base.slot, []).append(base)
    return {slot: tuple(items) for slot, items in by_slot.items()}


def base_for_name(name: str) -> BaseItem | None:
    """Look up a base by canonical PoE name. ``None`` when unknown."""

    return _bases_by_name().get(name)


def bases_for_slot(slot: ItemSlot) -> tuple[BaseItem, ...]:
    """Return every base that lives in *slot*. Empty tuple if none mapped."""

    return _bases_by_slot().get(slot, ())


__all__ = [
    "BaseItem",
    "base_for_name",
    "bases_for_slot",
    "get_base_catalogue",
]
