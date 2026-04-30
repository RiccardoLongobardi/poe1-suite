"""Build progression plan.

A :class:`BuildPlan` is the Planner's output: an ordered list of stages
(league-start → mid → end-game), each with its own budget, core items,
and upgrade rationale. The planner works identically whether the starting
:class:`~poe1_core.models.build.Build` came from a source or from a
user-supplied PoB.
"""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .enums import ContentFocus, ItemRarity, ItemSlot, TargetGoal
from .pricing import PriceRange


class CoreItem(BaseModel):
    """An item the player should acquire at a given stage.

    ``buy_priority`` is a 1..N ordering within the stage (1 = buy first).

    ``base_type`` and ``mods`` are populated when the planner has access
    to the item's PoB-side detail (always for items mapped from a Build's
    KeyItems). They power the "Cerca su Trade" dialog: ``mods`` carries
    the verbatim mod text lines so the frontend can extract stat filters
    on demand. Both default to None / empty so test fixtures don't have
    to supply them, and so older serialised plans deserialise cleanly.
    """

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., min_length=1)
    slot: ItemSlot
    rarity: ItemRarity
    price_estimate: PriceRange | None = None
    buy_priority: int = Field(..., ge=1)
    notes: str | None = None
    base_type: str | None = None
    mods: tuple[str, ...] = ()


class PlanStage(BaseModel):
    """One step in the progression plan."""

    model_config = ConfigDict(frozen=True)

    label: str = Field(..., min_length=1)
    budget_range: PriceRange
    expected_content: list[ContentFocus] = Field(default_factory=list)
    core_items: list[CoreItem] = Field(default_factory=list)
    tree_changes: list[str] = Field(default_factory=list)
    gem_changes: list[str] = Field(default_factory=list)
    upgrade_rationale: str = ""
    next_step_trigger: str | None = None


class BuildPlan(BaseModel):
    """Complete progression plan for a specific build and target goal."""

    model_config = ConfigDict(frozen=True)

    build_source_id: str = Field(..., min_length=1)
    target_goal: TargetGoal
    stages: list[PlanStage] = Field(..., min_length=1)
    total_estimated_cost: PriceRange

    @model_validator(mode="after")
    def _check_stages_order(self) -> Self:
        # Stages should be in non-decreasing budget order (by midpoint).
        midpoints = [stage.budget_range.midpoint for stage in self.stages]
        if midpoints != sorted(midpoints):
            msg = "stages must be ordered by non-decreasing budget midpoint"
            raise ValueError(msg)
        return self


__all__ = ["BuildPlan", "CoreItem", "PlanStage"]
