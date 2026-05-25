"""Loader for the vendored PoB unique-item catalogue (Step 58, F1).

Reads ``packages/fob/data/uniques/uniques_3_28.json`` (produced by
``scripts/extract_uniques.py`` from PoB's ``Data/Uniques/*.lua``) and
exposes:

* :class:`UniqueItem` — name + base type + slot + drop level + mod lines
  (the current-variant modifiers, value ranges kept as text).
* :func:`get_uniques` — cached full catalogue.
* :func:`uniques_for_slot` — every unique mapped to a slot string
  (``"helmet"`` / ``"body_armour"`` / ``"weapon"`` / ``"jewel"`` / …).
* :func:`unique_by_name` — exact-name lookup.

The mirror-tier optimiser uses these as candidate items to try in a build
(scored by PoB's real fitness). The mod text feeds the PoB item body the
encoder emits so PoB recognises the unique and applies its stats.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "uniques" / "uniques_3_28.json"


class UniqueItem:
    """A vendored unique item. Light wrapper (not frozen pydantic — this is
    read-only catalogue data accessed in hot optimiser loops)."""

    __slots__ = ("base_type", "drop_level", "mods", "name", "slot")

    def __init__(
        self,
        name: str,
        base_type: str,
        slot: str,
        drop_level: int,
        mods: tuple[str, ...],
    ) -> None:
        self.name = name
        self.base_type = base_type
        self.slot = slot
        self.drop_level = drop_level
        self.mods = mods

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"UniqueItem({self.name!r}, {self.base_type!r}, {self.slot!r})"


@lru_cache(maxsize=1)
def get_uniques() -> tuple[UniqueItem, ...]:
    """The full vendored unique catalogue (empty tuple if the file is absent)."""
    if not _DATA_PATH.exists():  # pragma: no cover - deployment guard
        return ()
    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return tuple(
        UniqueItem(
            name=str(u["name"]),
            base_type=str(u["base_type"]),
            slot=str(u["slot"]),
            drop_level=int(u.get("drop_level", 0)),
            mods=tuple(u.get("mods", [])),
        )
        for u in raw.get("uniques", [])
    )


@lru_cache(maxsize=1)
def _by_slot() -> dict[str, tuple[UniqueItem, ...]]:
    out: dict[str, list[UniqueItem]] = {}
    for u in get_uniques():
        out.setdefault(u.slot, []).append(u)
    return {slot: tuple(items) for slot, items in out.items()}


@lru_cache(maxsize=1)
def _by_name() -> dict[str, UniqueItem]:
    return {u.name: u for u in get_uniques()}


def uniques_for_slot(slot: str) -> tuple[UniqueItem, ...]:
    """Every unique whose slot is *slot* (``"helmet"``, ``"weapon"``, …)."""
    return _by_slot().get(slot, ())


def unique_by_name(name: str) -> UniqueItem | None:
    """Exact-name lookup, or ``None``."""
    return _by_name().get(name)


__all__ = [
    "UniqueItem",
    "get_uniques",
    "unique_by_name",
    "uniques_for_slot",
]
