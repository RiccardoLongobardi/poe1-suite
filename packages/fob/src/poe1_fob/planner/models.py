"""HTTP-shaped request/response models for the planner endpoint.

These wrap the cross-source :class:`poe1_core.Build` and
:class:`poe1_core.BuildPlan` so ``POST /fob/plan`` has a single
narrowly-typed payload to validate. Keep them in this file (not in
:mod:`poe1_core.models`) — :mod:`poe1_core` should stay free of
HTTP/OpenAPI concerns.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from poe1_core.models import Build, BuildPlan
from poe1_core.models.enums import TargetGoal


class PlanRequest(BaseModel):
    """Input for ``POST /fob/plan``.

    Accepts the same shape as ``/fob/analyze-pob`` so the UX is one
    paste-and-go: raw PoB export code, ``https://pobb.in/<id>``, or
    ``https://pastebin.com/<id>``. The endpoint runs the analyze
    pipeline first and feeds the resulting :class:`Build` to the
    planner.
    """

    model_config = ConfigDict(frozen=True)

    input: str = Field(
        ...,
        min_length=1,
        description=(
            "Raw PoB export code, or a pobb.in / pastebin share URL pointing "
            "at one. The server follows the URL to fetch the raw code."
        ),
    )
    target_goal: TargetGoal = Field(
        default=TargetGoal.MAPPING_AND_BOSS,
        description=(
            "Final goal of the plan. Currently informative — stage "
            "content tags reflect this in a future revision."
        ),
    )


class PlanResponse(BaseModel):
    """Response from ``POST /fob/plan``.

    Includes the analyzed :class:`Build` alongside the resulting
    :class:`BuildPlan` so the UI can render both summary and plan
    without a second round-trip.
    """

    model_config = ConfigDict(frozen=True)

    build: Build
    plan: BuildPlan


__all__ = ["PlanRequest", "PlanResponse"]
