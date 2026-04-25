"""Price-lookup helpers for the planner.

Wraps :class:`poe1_pricing.PricingService` calls so the rest of the
planner doesn't have to know about the chaos/divine conversion or the
poe.ninja-specific shapes. Two responsibilities live here:

* Resolve the current chaos-per-divine rate (with a heuristic fallback
  so a pricing outage doesn't fail the whole plan request).
* Turn a single poe.ninja :class:`PriceQuote` into a divine- or
  chaos-denominated :class:`PriceRange` with a ±15 % spread band and
  a sample-count-driven confidence.

The planner stays purely sync after this module returns; the only async
touchpoints in the planner pipeline are these two functions.
"""

from __future__ import annotations

from typing import Protocol

from poe1_core.models import (
    Confidence,
    Currency,
    PriceRange,
    PriceSource,
    PriceValue,
)
from poe1_pricing import PriceQuote

# Heuristic fallback when poe.ninja's currency overview can't be reached
# or when ``Divine Orb`` is missing. Mirage league baseline (~April 2026).
_DEFAULT_CHAOS_PER_DIVINE: float = 200.0

# ±15 % spread around the mid-point we observe. poe.ninja already
# averages across listings, so the band represents day-over-day noise
# more than market depth.
_PRICE_SPREAD: float = 0.15

# Items below this divine value are reported in chaos to preserve UX:
# saying "0.05 div" hides that an item is a 10-chaos pickup.
_DIVINE_THRESHOLD: float = 1.0


class PricingPort(Protocol):
    """Subset of :class:`poe1_pricing.PricingService` the planner needs.

    Defined as a Protocol so unit tests can stand up a tiny fake without
    instantiating an HttpClient. The real ``PricingService`` satisfies
    this interface structurally.

    ``quote_unique_variant`` lets callers pin a specific poe.ninja
    variant string (Forbidden Shako keystone, Watcher's Eye combo, etc.).
    Passing ``variant=None`` is equivalent to :meth:`quote_unique`.
    """

    async def quote_currency(self, name: str) -> PriceQuote | None: ...

    async def quote_unique(self, name: str) -> PriceQuote | None: ...

    async def quote_unique_variant(
        self,
        name: str,
        variant: str | None,
    ) -> PriceQuote | None: ...


async def chaos_to_divine_rate(pricing: PricingPort) -> float:
    """Return the current ``chaos per 1 divine`` rate.

    Falls back to :data:`_DEFAULT_CHAOS_PER_DIVINE` if the lookup fails
    or returns a non-positive value — better to ship a slightly stale
    rate than fail a whole plan request.
    """

    quote = await pricing.quote_currency("Divine Orb")
    if quote is None or quote.chaos_value <= 0.0:
        return _DEFAULT_CHAOS_PER_DIVINE
    return float(quote.chaos_value)


def _confidence_from_quote(*, low_confidence: bool, sample_count: int | None) -> Confidence:
    if low_confidence:
        return Confidence.LOW
    n = sample_count or 0
    if n >= 50:
        return Confidence.HIGH
    if n >= 10:
        return Confidence.MEDIUM
    return Confidence.LOW


def quote_to_range(quote: PriceQuote, *, chaos_per_divine: float) -> PriceRange:
    """Convert a poe.ninja quote into a :class:`PriceRange`.

    Sub-divine items stay in chaos for readability; ≥ 1 div items are
    re-expressed in divines. The ±:data:`_PRICE_SPREAD` band gives
    downstream UI a sensible "from X to Y" copy.
    """

    chaos = float(quote.chaos_value)
    rate = chaos_per_divine if chaos_per_divine > 0 else _DEFAULT_CHAOS_PER_DIVINE
    div_amount = chaos / rate
    confidence = _confidence_from_quote(
        low_confidence=quote.low_confidence,
        sample_count=quote.sample_count,
    )

    if div_amount < _DIVINE_THRESHOLD:
        low = PriceValue(
            amount=round(chaos * (1.0 - _PRICE_SPREAD), 2),
            currency=Currency.CHAOS,
        )
        high = PriceValue(
            amount=round(chaos * (1.0 + _PRICE_SPREAD), 2),
            currency=Currency.CHAOS,
        )
    else:
        low = PriceValue(
            amount=round(div_amount * (1.0 - _PRICE_SPREAD), 2),
            currency=Currency.DIVINE,
        )
        high = PriceValue(
            amount=round(div_amount * (1.0 + _PRICE_SPREAD), 2),
            currency=Currency.DIVINE,
        )

    return PriceRange(
        min=low,
        max=high,
        source=PriceSource.POE_NINJA,
        observed_at=quote.fetched_at,
        sample_size=quote.sample_count,
        confidence=confidence,
    )


async def quote_unique_range(
    pricing: PricingPort,
    name: str,
    *,
    chaos_per_divine: float,
    variant: str | None = None,
) -> PriceRange | None:
    """Look up a unique by ``(name, variant)``; return ``None`` when missing.

    When *variant* is supplied we ask poe.ninja for that exact variant
    string. If poe.ninja doesn't list that variant we fall back to the
    cheapest variant of the same name — better an approximate price
    than no price at all. Pass ``variant=None`` to skip variant
    matching entirely (current behaviour for items without resolvers).
    """

    quote: PriceQuote | None
    if variant is not None:
        quote = await pricing.quote_unique_variant(name, variant)
        if quote is None:
            quote = await pricing.quote_unique(name)
    else:
        quote = await pricing.quote_unique(name)
    if quote is None:
        return None
    return quote_to_range(quote, chaos_per_divine=chaos_per_divine)


def price_range_to_divines(price: PriceRange | None, chaos_per_divine: float) -> float | None:
    """Express a :class:`PriceRange` mid-point in divines.

    Returns ``None`` when *price* is ``None``. Used by the stage bucketing
    logic to decide which stage an item belongs to.
    """

    if price is None:
        return None
    rate = chaos_per_divine if chaos_per_divine > 0 else _DEFAULT_CHAOS_PER_DIVINE
    if price.currency is Currency.DIVINE:
        return float(price.midpoint)
    return float(price.midpoint) / rate


__all__ = [
    "PricingPort",
    "chaos_to_divine_rate",
    "price_range_to_divines",
    "quote_to_range",
    "quote_unique_range",
]
