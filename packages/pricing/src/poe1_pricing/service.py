"""High-level pricing facade.

Downstream consumers (FOB, future Faustus) should import
:class:`PricingService` and never talk to :mod:`poe1_pricing.sources`
directly. That way when we add a second source later (GGG Trade API
for rare-only items, watchthis.trade, …) the caller code doesn't
change.

The service keeps a per-category in-memory cache of the *last*
:class:`PriceSnapshot` fetched. On-disk HTTP caching is handled one
layer down by :class:`poe1_shared.http.HttpClient`; this in-memory
cache exists purely so a single call to :meth:`quote_by_name` can turn
into a single round-trip per category even when invoked repeatedly in
the same request.
"""

from __future__ import annotations

from poe1_shared.http import HttpClient
from poe1_shared.logging import get_logger

from .models import ItemCategory, PriceQuote, PriceSnapshot
from .sources.ninja import NinjaSource

log = get_logger(__name__)


# Order matters: we probe currency first because it's the smallest
# payload and, by naming convention, currency items (Divine, Exalt,
# Mirror…) don't collide with unique names. After currency, we try the
# unique item categories. Skill gems & commoditised items are last —
# they're large payloads and rarely the intended lookup target.
_DEFAULT_SEARCH_ORDER: tuple[ItemCategory, ...] = (
    ItemCategory.CURRENCY,
    ItemCategory.FRAGMENT,
    ItemCategory.UNIQUE_WEAPON,
    ItemCategory.UNIQUE_ARMOUR,
    ItemCategory.UNIQUE_ACCESSORY,
    ItemCategory.UNIQUE_FLASK,
    ItemCategory.UNIQUE_JEWEL,
    ItemCategory.CLUSTER_JEWEL,
    ItemCategory.SCARAB,
    ItemCategory.ESSENCE,
    ItemCategory.FOSSIL,
    ItemCategory.DIVINATION_CARD,
    ItemCategory.MAP,
    ItemCategory.SKILL_GEM,
)


class PricingService:
    """Facade over one or more pricing sources.

    V1 is poe.ninja-only. Additional sources are added by extending
    :meth:`quote_by_name` to probe them in fallback order (the primary
    source's nulls trigger a secondary lookup).
    """

    def __init__(
        self,
        *,
        http: HttpClient,
        league: str,
        search_order: tuple[ItemCategory, ...] = _DEFAULT_SEARCH_ORDER,
    ) -> None:
        self._ninja = NinjaSource(http, league)
        self._league = league
        self._search_order = search_order
        self._snapshots: dict[ItemCategory, PriceSnapshot] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def league(self) -> str:
        return self._league

    async def snapshot(self, category: ItemCategory) -> PriceSnapshot:
        """Return (and in-memory cache) a category snapshot."""

        cached = self._snapshots.get(category)
        if cached is not None:
            return cached
        snapshot = await self._ninja.fetch_snapshot(category)
        self._snapshots[category] = snapshot
        return snapshot

    async def quote_by_name(
        self,
        name: str,
        *,
        category: ItemCategory | None = None,
    ) -> PriceQuote | None:
        """Look up a single item by name.

        If ``category`` is given, only that snapshot is probed (one
        request). Otherwise we walk :attr:`_search_order`, returning the
        first hit.

        Match is case-insensitive; exact name equality. poe.ninja often
        has multiple unique variants under the same ``name`` (different
        ``variant`` strings) — we return the first match of the category,
        which is poe.ninja's most-listed variant.
        """

        if category is not None:
            snapshot = await self.snapshot(category)
            return snapshot.by_name_ci(name)

        for cat in self._search_order:
            snapshot = await self.snapshot(cat)
            hit = snapshot.by_name_ci(name)
            if hit is not None:
                log.debug("pricing_hit", name=name, category=cat.value)
                return hit
        return None

    async def quote_currency(self, name: str) -> PriceQuote | None:
        """Look up a currency item (Divine, Exalt, Mirror, ...)."""

        return await self.quote_by_name(name, category=ItemCategory.CURRENCY)

    async def quote_unique(self, name: str) -> PriceQuote | None:
        """Look up a unique item by name across all unique categories.

        Returns the first hit across weapon/armour/accessory/flask/jewel
        — covers the overwhelming majority of build-relevant uniques.
        """

        for cat in (
            ItemCategory.UNIQUE_WEAPON,
            ItemCategory.UNIQUE_ARMOUR,
            ItemCategory.UNIQUE_ACCESSORY,
            ItemCategory.UNIQUE_FLASK,
            ItemCategory.UNIQUE_JEWEL,
        ):
            snapshot = await self.snapshot(cat)
            hit = snapshot.by_name_ci(name)
            if hit is not None:
                return hit
        return None

    def invalidate(self, *, category: ItemCategory | None = None) -> None:
        """Drop the in-memory snapshot cache.

        Use between tests or whenever a fresh pull is required; the
        next :meth:`snapshot` call will go back through the HTTP layer.
        """

        if category is None:
            self._snapshots.clear()
        else:
            self._snapshots.pop(category, None)


__all__ = ["PricingService"]
