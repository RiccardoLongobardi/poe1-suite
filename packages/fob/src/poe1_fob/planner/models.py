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


# ---------------------------------------------------------------------------
# Trade search — POST /fob/trade-search
# ---------------------------------------------------------------------------


class TradeSearchModFilter(BaseModel):
    """One mod filter the user has toggled on in the search dialog.

    The frontend extracts mod text from the analyzed PoB / plan item,
    runs it through the same pattern table the pricing layer uses, and
    submits one of these per mod the user wants to require. ``min`` is
    typically the rolled value scaled by the strictness slider (default
    80 % — same as poe.ninja's character trade search default).
    """

    model_config = ConfigDict(frozen=True)

    stat_id: str = Field(
        ...,
        min_length=1,
        description="GGG stat id (e.g. 'explicit.stat_3299347043' for +# to maximum Life).",
    )
    min: float | None = Field(
        default=None,
        description="Lower bound for the stat value; None = open lower bound.",
    )
    max: float | None = Field(
        default=None,
        description="Upper bound for the stat value; None = open upper bound.",
    )


class TradeSearchRequest(BaseModel):
    """Input for ``POST /fob/trade-search``.

    Builds a GGG Trade query from a focused selection of mods plus
    optional name / base type / link constraints, runs the search, and
    returns the share URL the frontend can open in a new tab. The
    endpoint never parses listings — that's the pricing layer's job.

    All fields are optional except that the request must specify *at
    least* a name, type, or one mod filter; an empty query would match
    every rare in the league and is rejected at validation.
    """

    model_config = ConfigDict(frozen=True)

    item_name: str | None = Field(
        default=None,
        description="Unique name to constrain the search to (e.g. 'Mageblood').",
    )
    item_type: str | None = Field(
        default=None,
        description="Base type to constrain the search to (e.g. 'Vaal Regalia').",
    )
    mods: tuple[TradeSearchModFilter, ...] = Field(
        default=(),
        description="Stat filters AND-combined; each one becomes one row in the search.",
    )
    online_only: bool = Field(
        default=True,
        description="When True (default), only include sellers currently online.",
    )
    min_links: int | None = Field(
        default=None,
        ge=1,
        le=6,
        description="Required minimum socket-link count (5 or 6 are the common values).",
    )


class TradeSearchResponse(BaseModel):
    """Response from ``POST /fob/trade-search``.

    The frontend opens :attr:`url` in a new tab; ``search_id`` is also
    surfaced in case the caller wants to construct alternative URLs
    (e.g. the official trade tools beyond the standard search page).
    """

    model_config = ConfigDict(frozen=True)

    league: str = Field(..., description="League the search ran against.")
    search_id: str = Field(..., description="GGG-issued search id (~10 minute lifetime).")
    url: str = Field(
        ...,
        description="Browser URL pointing at the pre-filled search on pathofexile.com.",
    )
    total_listings: int = Field(
        ...,
        ge=0,
        description="Server-reported total matches at search time.",
    )


# ---------------------------------------------------------------------------
# Trade-search dialog preview — POST /fob/extract-trade-mods
# ---------------------------------------------------------------------------


class TradeModExtractRequest(BaseModel):
    """Input for ``POST /fob/extract-trade-mods``.

    The frontend sends the verbatim mod text lines from a CoreItem (or
    from any other PoB-derived item) and gets back the typed dialog
    rows ready to render: stat_id, label, rolled value. Mod lines
    that don't match any pattern are silently dropped.
    """

    model_config = ConfigDict(frozen=True)

    mods: tuple[str, ...] = Field(
        default=(),
        description="Mod text lines to extract trade filters from.",
    )


class ExtractedTradeMod(BaseModel):
    """One row in the Trade-search dialog's mod list.

    Mirrors :class:`poe1_fob.pob.rares.ExtractedMod` but lives in the
    HTTP layer so the wire format is decoupled from the internal
    extraction dataclass.
    """

    model_config = ConfigDict(frozen=True)

    line: str = Field(..., description="Original mod line that matched.")
    stat_id: str = Field(..., description="GGG stat id keyed by the matching pattern.")
    value: float = Field(..., description="Numeric value rolled on the item.")
    label: str = Field(..., description="Human-readable label (e.g. '+# to maximum Life').")


class TradeModExtractResponse(BaseModel):
    """Output for ``POST /fob/extract-trade-mods``."""

    model_config = ConfigDict(frozen=True)

    mods: tuple[ExtractedTradeMod, ...] = Field(default=())


__all__ = [
    "ExtractedTradeMod",
    "PlanRequest",
    "PlanResponse",
    "TradeModExtractRequest",
    "TradeModExtractResponse",
    "TradeSearchModFilter",
    "TradeSearchRequest",
    "TradeSearchResponse",
]
