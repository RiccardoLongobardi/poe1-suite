"""Domain models for the Ranking Engine.

* ``ScoreBreakdown`` — per-dimension scores plus weighted total.
* ``RankedBuild``    — a :class:`RemoteBuildRef` paired with its breakdown and rank.
* ``RecommendRequest``  — input to ``POST /fob/recommend``.
* ``RecommendResponse`` — output of ``POST /fob/recommend``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from poe1_builds.models import RemoteBuildRef
from poe1_core.models.build_intent import BuildIntent


class ScoreBreakdown(BaseModel):
    """Per-dimension scores and the final weighted total.

    Every value is in ``[0.0, 1.0]``:

    * ``0.0`` — clear mismatch (or hard constraint would have removed the build,
      but a soft version of the same dimension was used).
    * ``0.5`` — no signal (the intent or the ref carries no information on this
      dimension).
    * ``1.0`` — perfect match.
    """

    model_config = ConfigDict(frozen=True)

    damage: float = Field(ge=0.0, le=1.0)
    playstyle: float = Field(ge=0.0, le=1.0)
    budget: float = Field(ge=0.0, le=1.0)
    content: float = Field(ge=0.0, le=1.0)
    defense: float = Field(ge=0.0, le=1.0)
    complexity: float = Field(ge=0.0, le=1.0)
    total: float = Field(ge=0.0, le=1.0)


class RankedBuild(BaseModel):
    """A build reference paired with its score and final rank position."""

    model_config = ConfigDict(frozen=True)

    ref: RemoteBuildRef
    score: ScoreBreakdown
    rank: int = Field(ge=1)


class RecommendRequest(BaseModel):
    """Input for ``POST /fob/recommend``.

    The caller is expected to have already extracted a :class:`BuildIntent`
    (via ``POST /fob/extract-intent`` or any other means). The ranking layer
    is intentionally decoupled from intent extraction so both steps can be
    called independently.
    """

    model_config = ConfigDict(frozen=True)

    intent: BuildIntent
    top_n: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of ranked builds to return.",
    )


class RecommendResponse(BaseModel):
    """Response from ``POST /fob/recommend``."""

    model_config = ConfigDict(frozen=True)

    ranked: tuple[RankedBuild, ...]
    total_candidates: int = Field(
        ge=0,
        description=("Total refs fetched from all sources before hard-constraint filtering."),
    )
    intent: BuildIntent


__all__ = ["RankedBuild", "RecommendRequest", "RecommendResponse", "ScoreBreakdown"]
