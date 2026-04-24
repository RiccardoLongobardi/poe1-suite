"""BuildIntent — the normalised representation of a player's request.

This is the output of the Intent Engine (rule-based + LLM hybrid) and the
input of the Ranking Engine. Every natural-language query the user types
lands here; everything downstream speaks only in these terms.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import (
    BudgetTier,
    ComplexityLevel,
    ContentFocus,
    DamageProfile,
    DefenseProfile,
    HardConstraint,
    ParserOrigin,
    Playstyle,
)


class ContentFocusWeight(BaseModel):
    """Weighted focus on a specific content type.

    Weights are interpretable as probabilities: a player saying "mapping
    mostly but also some bossing" would be modelled as
    ``[(mapping, 0.7), (bossing, 0.3)]``.
    """

    model_config = ConfigDict(frozen=True)

    focus: ContentFocus
    weight: float = Field(..., ge=0.0, le=1.0)


class BudgetRange(BaseModel):
    """Player-declared or inferred budget, in divines.

    Both numeric range and tier are carried: numeric is used by the pricing
    layer, tier is used by the ranking layer for coarse matching.
    """

    model_config = ConfigDict(frozen=True)

    tier: BudgetTier | None = None
    min_divines: float | None = Field(default=None, ge=0.0)
    max_divines: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _check_ordering(self) -> Self:
        if (
            self.min_divines is not None
            and self.max_divines is not None
            and self.min_divines > self.max_divines
        ):
            msg = "min_divines must be <= max_divines"
            raise ValueError(msg)
        return self


class BuildIntent(BaseModel):
    """Structured representation of a player's build request."""

    model_config = ConfigDict(frozen=True)

    # --- Damage ---
    damage_profile: DamageProfile | None = None
    alternative_damage_profiles: list[DamageProfile] = Field(default_factory=list)

    # --- Playstyle ---
    playstyle: Playstyle | None = None
    alternative_playstyles: list[Playstyle] = Field(default_factory=list)

    # --- Content & budget ---
    content_focus: list[ContentFocusWeight] = Field(default_factory=list)
    budget: BudgetRange | None = None

    # --- Complexity & defense ---
    complexity_cap: ComplexityLevel | None = None
    defense_profile: DefenseProfile | None = None

    # --- Constraints ---
    hard_constraints: set[HardConstraint] = Field(default_factory=set)

    # --- Provenance ---
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_input: str = Field(..., min_length=1)
    parser_origin: ParserOrigin

    @model_validator(mode="after")
    def _check_content_focus_weights(self) -> Self:
        if not self.content_focus:
            return self
        total = sum(cfw.weight for cfw in self.content_focus)
        # Tolerate minor rounding; enforce that weights are sensibly scaled.
        if total > 1.0 + 1e-6:
            msg = f"sum of content_focus weights must be <= 1.0 (got {total:.3f})"
            raise ValueError(msg)
        return self


__all__ = ["BudgetRange", "BuildIntent", "ContentFocusWeight"]
