"""League metadata.

A :class:`League` pins every price, every build, and every plan to a
specific in-game economy. poe.ninja responses, trade listings, and ladder
snapshots only make sense in the context of a league.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class League(BaseModel):
    """A Path of Exile 1 league.

    ``slug`` is what poe.ninja / GGG APIs expect as a path parameter;
    keep it exactly as the official league name (case-sensitive).
    """

    model_config = ConfigDict(frozen=True)

    slug: str = Field(
        ...,
        min_length=1,
        description="Canonical league slug used by poe.ninja and GGG APIs.",
    )
    name: str = Field(..., min_length=1, description="Human-friendly display name.")
    started_at: date | None = None
    ended_at: date | None = None
    is_event: bool = False
    is_private: bool = False
    is_hardcore: bool = False
    is_ssf: bool = False

    @model_validator(mode="after")
    def _check_date_ordering(self) -> Self:
        if self.started_at and self.ended_at and self.ended_at < self.started_at:
            msg = "ended_at cannot be earlier than started_at"
            raise ValueError(msg)
        return self

    @classmethod
    def standard(cls) -> Self:
        """Return the permanent Standard league (no start/end)."""

        return cls(slug="Standard", name="Standard")


__all__ = ["League"]
