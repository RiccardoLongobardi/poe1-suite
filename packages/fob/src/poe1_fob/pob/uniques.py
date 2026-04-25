"""Map a PoB unique item to a poe.ninja variant string.

Many uniques are price-distinct per variant on poe.ninja
(Forbidden Shako per keystone, Watcher's Eye per aura+stat pair, etc.).
The :class:`poe1_pricing.VariantRegistry` carries the resolvers; this
module is the thin glue between :class:`PobItem` and that registry.

The resolver inputs are the item's mod lines (implicit + explicit).
For uniques those are clean — PoB doesn't sprinkle metadata on
unique-mod sections — so we feed them straight through.
"""

from __future__ import annotations

from poe1_pricing import VariantRegistry

from .models import PobItem


def unique_variant(item: PobItem, registry: VariantRegistry) -> str | None:
    """Resolve *item* to a poe.ninja variant string, or ``None``.

    Returns ``None`` when:

    * The item has no name (would never happen for a true unique, but
      defensive).
    * No resolver is registered for that unique's name.
    * The resolver runs but the mods don't carry the variant signal we
      look for (e.g. an unrolled Forbidden Shako).

    Callers should treat ``None`` as "fall back to the cheapest variant
    on poe.ninja" — that's the safest pricing assumption when we can't
    pin the exact variant down.
    """

    if not item.name:
        return None
    mods = (*item.implicits, *item.explicits)
    return registry.resolve(item.name, mods)


__all__ = ["unique_variant"]
