"""Price values and ranges.

Prices are represented as a band (``min``..``max``), never as a single
spot value. This is deliberate: for crafted rares we only know an order
of magnitude, and even for uniques poe.ninja reports a daily distribution
rather than a single listing price. Downstream code should treat prices
probabilistically.
"""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import Confidence, Currency, PriceSource


class PriceValue(BaseModel):
    """A single price point in a given currency."""

    model_config = ConfigDict(frozen=True)

    amount: float = Field(..., ge=0.0)
    currency: Currency

    def as_divines(self, chaos_per_divine: float) -> float:
        """Convert this price to divines, given today's chaos/divine rate."""

        if self.currency is Currency.DIVINE:
            return self.amount
        if chaos_per_divine <= 0:
            msg = "chaos_per_divine must be > 0"
            raise ValueError(msg)
        return self.amount / chaos_per_divine


class PriceRange(BaseModel):
    """An observed or estimated price band.

    Invariants:
      - ``min.currency == max.currency``
      - ``min.amount <= max.amount``
    """

    model_config = ConfigDict(frozen=True)

    min: PriceValue
    max: PriceValue
    source: PriceSource
    observed_at: datetime | None = None
    sample_size: int | None = Field(default=None, ge=0)
    confidence: Confidence = Confidence.MEDIUM
    notes: str | None = None

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.min.currency is not self.max.currency:
            msg = "min and max must use the same currency"
            raise ValueError(msg)
        if self.min.amount > self.max.amount:
            msg = "min.amount must be <= max.amount"
            raise ValueError(msg)
        return self

    @property
    def currency(self) -> Currency:
        return self.min.currency

    @property
    def midpoint(self) -> float:
        return (self.min.amount + self.max.amount) / 2.0

    @classmethod
    def point(
        cls,
        amount: float,
        currency: Currency = Currency.DIVINE,
        *,
        source: PriceSource = PriceSource.UNKNOWN,
        confidence: Confidence = Confidence.MEDIUM,
    ) -> Self:
        """Construct a degenerate range ``[amount, amount]``."""

        value = PriceValue(amount=amount, currency=currency)
        return cls(min=value, max=value, source=source, confidence=confidence)


__all__ = ["PriceRange", "PriceValue"]
