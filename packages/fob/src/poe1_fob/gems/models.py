"""Pydantic models for stage-by-stage gem socket allocation.

A :class:`StageGemLinks` is the snapshot of which gems the build
should have socketed by the end of a stage, grouped by socket-link
group (6L body, 4L helmet, 4L weapon, etc).

Unlike the tree progression, gem progression is NOT strictly monotone:
a support gem can be replaced (Burning Damage 20/20 → Awakened Burning
Damage 5) so each stage spec stands on its own.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from poe1_core.models.enums import ItemSlot

# Alternate-quality variants shipped with PoE 3.x. Maps directly to
# poe.ninja's ``alternateQuality`` field on a gem listing. ``None`` =
# the standard (superior) variant.
AltQuality = Literal["divergent", "phantasmal", "anomalous"]


class GemSpec(BaseModel):
    """One gem in a socket group.

    The ``name`` is the canonical PoE in-game gem name, including the
    "Support" suffix for support gems and the "Awakened "/"Vaal "
    prefixes when relevant. e.g.:

    * "Righteous Fire"
    * "Burning Damage Support"
    * "Awakened Burning Damage Support"
    * "Vaal Molten Shell"

    Level + quality are the **target** values for this stage. Defaults
    are the canonical-leveled values (20/20). Awakened gems max at 5.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    name: str = Field(..., min_length=1, description="Canonical gem name.")
    level: int = Field(default=20, ge=1, le=40, description="Target gem level.")
    quality: int = Field(default=20, ge=0, le=23, description="Target quality %.")
    alt_quality: AltQuality | None = Field(
        default=None,
        description=(
            "Alternate-quality variant (Divergent/Phantasmal/Anomalous). None = standard."
        ),
    )
    is_support: bool = Field(
        default=False,
        description=(
            "True when this is a support gem (used by the UI to render "
            "supports differently from active skills)."
        ),
    )
    notes: str = Field(
        default="",
        description=(
            "Optional per-gem rationale or alternative. Italian copy. "
            "E.g. 'corrupted 21/20 endgame', 'swap to Concentrated Effect on bossing'."
        ),
    )


class GemLink(BaseModel):
    """One socket group: slot + ordered gems.

    The ``sockets`` count must equal ``len(gems)``. The first gem is
    treated as the active skill (drives the link's identity in the UI);
    the rest are supports or auxiliary actives (e.g. CWDT setup chains).

    ``color_pattern`` is a 6-char string of R/G/B/W (white) for builds
    that need explicit socket colors (e.g. 4 red + 2 blue for fire body).
    None = the build doesn't care about colors at this stage.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    slot: ItemSlot = Field(..., description="Equipment slot the socket group is in.")
    sockets: int = Field(..., ge=1, le=6, description="Number of linked sockets.")
    color_pattern: str | None = Field(
        default=None,
        description="Optional R/G/B/W colors required (1 char per socket).",
    )
    gems: tuple[GemSpec, ...] = Field(..., min_length=1, description="Gems in socket order.")
    notes: str = Field(
        default="",
        description="Per-link rationale (e.g. 'CWDT setup', 'mobility chain').",
    )
    imbued_support: str | None = Field(
        default=None,
        description=(
            "3.28 imbued-gem support: a corrupted skill gem grants this support "
            "at level 1 with no socket cost. Value is the support base name "
            "without ' Support' (e.g. 'Increased Critical Damage'). PoB encodes "
            "it as the <Skill imbuedSupport=...> attribute."
        ),
    )

    @model_validator(mode="after")
    def _validate_socket_count(self) -> GemLink:
        if len(self.gems) != self.sockets:
            raise ValueError(f"sockets={self.sockets} but gems has {len(self.gems)} entries")
        if self.color_pattern is not None and len(self.color_pattern) != self.sockets:
            raise ValueError(
                f"color_pattern length {len(self.color_pattern)} != sockets {self.sockets}"
            )
        return self


class StageGemLinks(BaseModel):
    """All gem links for one stage."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    stage_key: str = Field(..., description="StageSpec.key.")
    links: tuple[GemLink, ...] = Field(
        ..., min_length=1, description="Ordered link groups (main 6L first)."
    )
    notes: str = Field(
        default="",
        description="Stage-level note about gem progression as a whole.",
    )

    def link_for_slot(self, slot: ItemSlot) -> GemLink | None:
        """First link assigned to ``slot``, or None."""

        for link in self.links:
            if link.slot == slot:
                return link
        return None


class GemProgression(BaseModel):
    """Ordered tuple of :class:`StageGemLinks` per template."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    target_name: str = Field(..., description="BuildTemplate.name.")
    stages: tuple[StageGemLinks, ...] = Field(
        ..., min_length=1, description="Stages in temporal order."
    )

    def for_stage(self, stage_key: str) -> StageGemLinks | None:
        for stage in self.stages:
            if stage.stage_key == stage_key:
                return stage
        return None

    @model_validator(mode="after")
    def _validate_unique(self) -> GemProgression:
        seen: set[str] = set()
        for stage in self.stages:
            if stage.stage_key in seen:
                raise ValueError(f"duplicate stage_key in gem progression: {stage.stage_key!r}")
            seen.add(stage.stage_key)
        return self
