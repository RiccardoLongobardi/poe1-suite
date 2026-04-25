"""Pricing lookup for PoE 1 items & currency.

Public surface:

* :class:`poe1_pricing.models.PriceQuote` — single-item price point.
* :class:`poe1_pricing.models.PriceSnapshot` — full category listing.
* :class:`poe1_pricing.sources.ninja.NinjaSource` — poe.ninja adapter.
* :class:`poe1_pricing.service.PricingService` — high-level facade.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .models import (
    ItemCategory,
    NinjaIndex,
    NinjaLeagueRef,
    NinjaSnapshotVersion,
    PriceQuote,
    PriceSnapshot,
)
from .service import PricingService
from .sources.ninja import NinjaSource, NinjaSourceError
from .variants import (
    VariantRegistry,
    VariantResolver,
    build_default_registry,
    keystone_allocates_resolver,
    keystone_radius_resolver,
)

__all__ = [
    "ItemCategory",
    "NinjaIndex",
    "NinjaLeagueRef",
    "NinjaSnapshotVersion",
    "NinjaSource",
    "NinjaSourceError",
    "PriceQuote",
    "PriceSnapshot",
    "PricingService",
    "VariantRegistry",
    "VariantResolver",
    "__version__",
    "build_default_registry",
    "keystone_allocates_resolver",
    "keystone_radius_resolver",
]
