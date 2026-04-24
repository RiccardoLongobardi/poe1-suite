"""Item and item-mod models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .enums import ItemRarity, ItemSlot, ModType


class ItemMod(BaseModel):
    """A single line of text on an item.

    ``text`` is kept verbatim (as exported by PoB / trade API) so we
    never lose information. Structured parsing of modifiers lives in a
    separate module because it is inherently imprecise and should not
    contaminate this model.
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(..., min_length=1)
    mod_type: ModType = ModType.EXPLICIT
    tier: int | None = Field(default=None, ge=1)


class Item(BaseModel):
    """A single PoE 1 item, rare or unique.

    The ``name`` field is the unique name for uniques (e.g. "Mageblood"),
    or the crafted name for rares (typically empty in PoB exports).
    For rares the :class:`Item` is identified by ``base_type`` + ``mods``.
    """

    model_config = ConfigDict(frozen=True)

    name: str = ""
    base_type: str = Field(..., min_length=1)
    rarity: ItemRarity
    slot: ItemSlot | None = None
    item_level: int | None = Field(default=None, ge=1, le=100)
    mods: list[ItemMod] = Field(default_factory=list)
    sockets: str | None = None
    links: int | None = Field(default=None, ge=1, le=6)
    corrupted: bool = False
    influence: list[str] = Field(default_factory=list)


__all__ = ["Item", "ItemMod"]
