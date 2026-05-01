"""Pydantic models for the reverse-progression ladder.

These are the data containers the engine produces. Concrete degraders
build them; the planner integration will consume them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..planner.stages import StageSpec

# Each rung in a ladder describes ONE intermediate item the player buys
# on the path to the endgame target. ``kind`` discriminates how the item
# should be sourced: a known unique (poe.ninja lookup), a rare crafted
# from explicit mods (Trade query), or a placeholder leveling drop.
RungKind = Literal["unique", "rare_craft", "leveling"]


class LadderStep(BaseModel):
    """One rung on the upgrade ladder.

    A rung lives inside a specific :class:`StageSpec` (which fixes its
    divine budget). The ``budget_div_max`` field is an *additional*
    soft cap the degrader can apply when the stage budget is wider than
    the rung deserves — e.g. a Tabula Rasa rung in End Mapping should
    still cost a few chaos, not the full End Mapping budget.

    Pydantic frozen so :class:`UpgradeLadder` (which holds a tuple of
    these) hashes cleanly.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    stage_key: str = Field(
        ...,
        description="StageSpec.key the rung is anchored to (early_campaign, …).",
    )
    item_name: str = Field(
        ...,
        description="Display name of the rung item (e.g. 'Tabula Rasa', "
        "'Quicksilver Flask alteration spam', '+1/+2 socketed rare body').",
    )
    kind: RungKind = Field(
        ...,
        description="Sourcing hint: unique → poe.ninja, rare_craft → Trade, "
        "leveling → no pricing (placeholder).",
    )
    budget_div_max: float | None = Field(
        default=None,
        description="Optional soft price cap in divines. None means use the "
        "stage budget cap. Set to a small number for rungs that should "
        "stay cheap even when the stage is rich (e.g. a 4L body in End "
        "Mapping).",
    )
    rationale: str = Field(
        ...,
        description="Italian copy explaining why the player should grab "
        "this rung at this stage. Surfaces directly in the plan UI.",
    )


class UpgradeLadder(BaseModel):
    """Ordered ladder cheap → endgame for one key item.

    The ``rungs`` tuple is ordered by stage progression: index 0 is the
    earliest stage, index -1 is the endgame target. The endgame target
    rung's ``item_name`` should equal the source :class:`KeyItem`
    name (so the planner can show "you currently own X, here's how
    to get there").

    Empty ladders are not valid — a degrader that can't produce any
    rung must still emit a single-rung ladder pointing at the endgame
    item itself, anchored to High Investment.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    target_name: str = Field(
        ...,
        description="The endgame item this ladder leads to. Matches "
        "KeyItem.item.name on the source build.",
    )
    rungs: tuple[LadderStep, ...] = Field(
        ...,
        description="Ordered cheap → endgame. At least 1 rung.",
        min_length=1,
    )

    def stage_keys(self) -> tuple[str, ...]:
        """Return the stage keys covered by this ladder, in order."""

        return tuple(rung.stage_key for rung in self.rungs)

    def for_stage(self, stage: StageSpec) -> LadderStep | None:
        """Return the rung anchored to *stage*, or ``None`` if none.

        At most one rung per stage is expected; if the degrader emits
        multiple rungs for the same stage, the first one wins.
        """

        for rung in self.rungs:
            if rung.stage_key == stage.key:
                return rung
        return None
