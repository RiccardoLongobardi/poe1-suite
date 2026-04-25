"""Resolve PoB-style item mods to poe.ninja variant strings.

Some uniques have many price-distinct variants on poe.ninja — same
``name``, different ``variant`` field. Pricing them accurately requires
matching the exact variant the player has equipped.

Examples (variant counts as observed on live poe.ninja):

* **Forbidden Shako** — one variant per keystone it can grant
  (~30 keystones)
* **Watcher's Eye** — one variant per (aura, stat) pair (~250 combos)
* **Forbidden Flame** / **Forbidden Flesh** — one variant per
  ascendancy notable (~100+)
* **Impossible Escape** — one variant per keystone in radius (~30)
* **Precursor's Emblem** — variants by mod combination

This module provides:

* :class:`VariantResolver` — protocol for "given an item's mods, return
  the canonical poe.ninja variant string".
* :class:`VariantRegistry` — name → resolver lookup.
* A few resolvers we can implement *purely* from PoB mod text, without
  needing a live capture of poe.ninja's variant catalogue:
  :func:`keystone_resolver`, :func:`notable_resolver`. These power
  Forbidden Shako / Impossible Escape / Forbidden Flame / Forbidden
  Flesh as a first pass.

Resolvers that need a live capture of poe.ninja's exact variant
strings (Watcher's Eye, the messy multi-axis ones) are deliberately
left unregistered until milestone 9.3 — we'll capture the catalogue,
add a tested resolver, and ship it. Until then, those uniques fall
back to the cheapest-variant heuristic in the planner.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

# ---------------------------------------------------------------------------
# Resolver protocol & registry
# ---------------------------------------------------------------------------


class VariantResolver(Protocol):
    """Map an item's mod lines to a poe.ninja variant string.

    Returns ``None`` when the resolver can't decide — typically because
    the PoB mods don't include the variant signal we expected (e.g. a
    Forbidden Shako that hasn't rolled a keystone yet, or text we don't
    recognise).
    """

    def __call__(self, mods: Iterable[str]) -> str | None: ...


@dataclass(frozen=True)
class _RegisteredResolver:
    """One row in the registry: a unique name and how to resolve it."""

    unique_name: str  # case-sensitive canonical name
    resolver: VariantResolver
    note: str  # short doc string shown in errors / debug


class VariantRegistry:
    """Name-keyed registry of variant resolvers.

    Lookups are case-insensitive on the unique's name. Names not in the
    registry simply have no resolver — callers should fall back to the
    "first variant wins" behaviour of :meth:`PricingService.quote_unique`.
    """

    def __init__(self) -> None:
        self._by_name: dict[str, _RegisteredResolver] = {}

    def register(
        self,
        unique_name: str,
        resolver: VariantResolver,
        *,
        note: str = "",
    ) -> None:
        """Add or replace the resolver for ``unique_name``."""

        key = unique_name.strip().casefold()
        self._by_name[key] = _RegisteredResolver(
            unique_name=unique_name,
            resolver=resolver,
            note=note,
        )

    def resolver_for(self, unique_name: str) -> VariantResolver | None:
        """Return the registered resolver, or ``None`` if not registered."""

        key = unique_name.strip().casefold()
        entry = self._by_name.get(key)
        return entry.resolver if entry is not None else None

    def resolve(self, unique_name: str, mods: Iterable[str]) -> str | None:
        """One-shot helper: find resolver, run it, propagate ``None``."""

        resolver = self.resolver_for(unique_name)
        if resolver is None:
            return None
        return resolver(mods)

    def __contains__(self, unique_name: str) -> bool:
        return unique_name.strip().casefold() in self._by_name


# ---------------------------------------------------------------------------
# Generic resolvers — work purely from PoB mod text
# ---------------------------------------------------------------------------


# Pattern for "Allocates X" mods. Used by Forbidden Shako (keystones
# only) and by Forbidden Flame / Flesh (ascendancy notables).
_ALLOCATES_RE = re.compile(
    r"\bAllocates\s+([A-Z][A-Za-z'\- ]+?)(?=\s*(?:if|$|\.|,|\())",
)

# Pattern for "Passives in Radius of {keystone}". Used by Impossible
# Escape — the keystone name follows "Radius of ".
_RADIUS_KEYSTONE_RE = re.compile(
    r"Passives in Radius of\s+([A-Z][A-Za-z'\- ]+?)\s+can be Allocated",
)


def _first_match(mods: Iterable[str], pattern: re.Pattern[str]) -> str | None:
    """Run *pattern* against each mod line; return the first capture group."""

    for line in mods:
        m = pattern.search(line)
        if m is not None:
            return m.group(1).strip()
    return None


def keystone_allocates_resolver(mods: Iterable[str]) -> str | None:
    """Resolve to the keystone/notable named after ``Allocates``.

    Works for Forbidden Shako (keystones), Forbidden Flame and Forbidden
    Flesh (ascendancy notables). The poe.ninja variant string for these
    items is just the bare keystone or notable name — e.g.
    ``"Avatar of Fire"``, ``"Mind Over Matter"``, ``"Magebane"``.

    .. note::
       This assumes poe.ninja's variant catalogue uses the same casing
       and spelling as the in-game keystone/notable names. We'll verify
       this empirically in milestone 9.3 with a live capture; if poe.ninja
       has stylistic differences (e.g. ``"avatar-of-fire"``), this
       resolver will need a final canonicalisation pass.
    """

    return _first_match(mods, _ALLOCATES_RE)


def keystone_radius_resolver(mods: Iterable[str]) -> str | None:
    """Resolve to the keystone named after ``Passives in Radius of``.

    Used by Impossible Escape (the only unique with this exact phrasing).
    """

    return _first_match(mods, _RADIUS_KEYSTONE_RE)


# ---------------------------------------------------------------------------
# Default registry — items we can resolve from PoB mods alone
# ---------------------------------------------------------------------------


def build_default_registry() -> VariantRegistry:
    """Return the default registry used by the planner.

    Includes the resolvers we can implement without a live poe.ninja
    catalogue capture (keystone-driven uniques). Watcher's Eye and the
    Precursor's Emblem-style multi-axis uniques are intentionally
    omitted here and added in milestone 9.3.
    """

    reg = VariantRegistry()
    reg.register(
        "Forbidden Shako",
        keystone_allocates_resolver,
        note="variant = keystone allocated by the helmet's mod",
    )
    reg.register(
        "Forbidden Flame",
        keystone_allocates_resolver,
        note="variant = ascendancy notable allocated; pairs with Forbidden Flesh",
    )
    reg.register(
        "Forbidden Flesh",
        keystone_allocates_resolver,
        note="variant = ascendancy notable allocated; pairs with Forbidden Flame",
    )
    reg.register(
        "Impossible Escape",
        keystone_radius_resolver,
        note="variant = keystone whose radius is granted",
    )
    return reg


__all__ = [
    "VariantRegistry",
    "VariantResolver",
    "build_default_registry",
    "keystone_allocates_resolver",
    "keystone_radius_resolver",
]
