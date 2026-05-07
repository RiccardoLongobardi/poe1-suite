"""Pydantic models for stage-by-stage gear allocation.

A :class:`StageGearSet` says "by the end of this stage you should be
wearing X in this slot, Y in that slot, …". Slots can be deliberately
empty (skipped) when the build doesn't use them — e.g. a 2H weapon
build skips ``weapon_offhand``, a no-flask-build skips ``flask`` slots.

Unlike the tree progression, gear sets are NOT strictly monotone:
an item is replaced when you upgrade (Tabula Rasa → Loreweave →
Mageblood-tier rare body), so a stage ships its own complete spec
per slot rather than diffing from the previous.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from poe1_core.models.enums import ItemSlot

# How an item should be sourced. Drives the UI affordance:
# * unique → ninja price lookup + "Apri su Trade"
# * rare_craft → display the mod requirements + "craft" suggestion
# * leveling → no specific item; copy line only ("any 4L base")
# * skip → empty slot intentionally (e.g. offhand for 2H builds)
GearKind = Literal["unique", "rare_craft", "leveling", "skip"]


class StageGearSlot(BaseModel):
    """One slot's spec at the end of a stage."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    slot: ItemSlot = Field(..., description="Equipment slot the spec targets.")
    item_name: str = Field(
        ...,
        min_length=1,
        description=(
            "Display name. For unique: exact PoE name ('Mageblood'). "
            "For rare_craft: short identifier ('+1 socketed gems body 6L'). "
            "For leveling: free-form ('any 3L bow with attack speed'). "
            "For skip: '(none)'."
        ),
    )
    kind: GearKind = Field(..., description="Sourcing hint for the UI.")
    notes: str = Field(
        default="",
        description=(
            "Rationale + mod requirements. Italian copy. For rare_craft "
            "this is where the player sees what tiers / stats to chase."
        ),
    )
    budget_div_max: float | None = Field(
        default=None,
        description=(
            "Optional soft price cap in divines. None = use stage budget. "
            "Useful for items that should stay cheap even when the stage "
            "is rich (e.g. Tabula Rasa during Early Mapping)."
        ),
    )


class StageGearSet(BaseModel):
    """The complete gear specification for one stage.

    Slots not present in :attr:`slots` are implicitly "leveling" — the
    player wears whatever drops. The hand-curated registry should
    surface every slot the build cares about.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    stage_key: str = Field(
        ...,
        description="StageSpec.key (early_campaign, mid_campaign, …).",
    )
    slots: tuple[StageGearSlot, ...] = Field(
        ...,
        description="Per-slot spec for this stage.",
        min_length=1,
    )
    overall_notes: str = Field(
        default="",
        description=(
            "Free-form note about the stage as a whole — e.g. 'do not "
            "use RF before Springleaf shield'. Surfaces in a banner "
            "above the gear grid in the UI."
        ),
    )

    def slot(self, target: ItemSlot) -> StageGearSlot | None:
        """Look up the spec for a specific equipment slot."""

        for s in self.slots:
            if s.slot == target:
                return s
        return None


class GearProgression(BaseModel):
    """Ordered tuple of :class:`StageGearSet`, one per stage.

    Validators:

    * Stage_keys are unique within the progression (so :meth:`for_stage`
      is unambiguous).
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    target_name: str = Field(
        ...,
        description=("BuildTemplate.name this progression maps to (e.g. 'rf_pohx')."),
    )
    stages: tuple[StageGearSet, ...] = Field(
        ...,
        description="Stages in temporal order.",
        min_length=1,
    )

    def for_stage(self, stage_key: str) -> StageGearSet | None:
        for stage in self.stages:
            if stage.stage_key == stage_key:
                return stage
        return None

    @model_validator(mode="after")
    def _validate_unique(self) -> GearProgression:
        seen: set[str] = set()
        for stage in self.stages:
            if stage.stage_key in seen:
                raise ValueError(f"duplicate stage_key in gear progression: {stage.stage_key!r}")
            seen.add(stage.stage_key)
        return self
