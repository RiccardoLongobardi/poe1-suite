"""Pydantic models for stage-by-stage skill tree allocation.

A :class:`StageTree` is the snapshot of which passive nodes the
build is supposed to have *by the end of* a given stage. Successive
stages are strictly additive — Mid Campaign should be a superset of
Early Campaign, etc. The :class:`TreeProgression` validator enforces
this so templates can't accidentally ship a non-monotone progression.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StageTree(BaseModel):
    """Passive tree allocation at the end of one stage.

    Node IDs are the canonical PoE 1 passive tree integer IDs
    (e.g. 50459 = "Path of the Warrior"). The ``notables`` field
    lists human-readable notable names for the UI / rationale; it's
    a denormalised cache of "important nodes in this set" rather
    than the source of truth.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    stage_key: str = Field(
        ...,
        description="StageSpec.key (early_campaign, mid_campaign, …).",
    )
    node_ids: tuple[int, ...] = Field(
        default=(),
        description="Sorted, deduplicated tuple of allocated node IDs.",
    )
    notables: tuple[str, ...] = Field(
        default=(),
        description=(
            "Human-readable notable / keystone names allocated by this "
            "stage (e.g. 'Avatar of Fire', 'Resolute Technique'). "
            "Cached for the UI; not the source of truth."
        ),
    )
    ascendancy_nodes: tuple[str, ...] = Field(
        default=(),
        description=(
            "Ascendancy notables allocated by this stage. Separate "
            "from the regular tree so the UI can render them in a "
            "dedicated badge row."
        ),
    )
    pob_url: str | None = Field(
        default=None,
        description=(
            "Optional pre-computed PathOfBuilding-website tree URL. "
            "Falls back to encode-on-demand via "
            ":func:`poe1_fob.tree.encode_pob_tree_url` when None."
        ),
    )

    @model_validator(mode="after")
    def _sort_and_dedupe(self) -> StageTree:
        """Enforce sorted+deduped node_ids for stable equality + diffs."""

        sorted_ids = tuple(sorted(set(self.node_ids)))
        if sorted_ids != self.node_ids:
            object.__setattr__(self, "node_ids", sorted_ids)
        return self


class TreeProgression(BaseModel):
    """Ordered tuple of :class:`StageTree`, one per stage of a build.

    Validators:

    * Stages must be monotone: each stage's ``node_ids`` is a
      superset of the previous stage's. Players don't *un*allocate
      points stage-to-stage in a Pohx-style guide.
    * ``stage_keys`` must be unique. Duplicate keys would make
      :meth:`for_stage` ambiguous.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    target_name: str = Field(
        ...,
        description=(
            "Build identity this progression maps to. Usually the "
            "BuildTemplate.name (e.g. 'rf_pohx', 'vortex_occultist')."
        ),
    )
    stages: tuple[StageTree, ...] = Field(
        ...,
        description="Stages in temporal order (earliest → latest).",
        min_length=1,
    )

    def for_stage(self, stage_key: str) -> StageTree | None:
        """Look up the tree snapshot for a stage_key, or None."""

        for stage in self.stages:
            if stage.stage_key == stage_key:
                return stage
        return None

    @model_validator(mode="after")
    def _validate_monotone_and_unique(self) -> TreeProgression:
        seen: set[str] = set()
        prev_nodes: set[int] = set()
        for stage in self.stages:
            if stage.stage_key in seen:
                raise ValueError(f"duplicate stage_key in progression: {stage.stage_key!r}")
            seen.add(stage.stage_key)
            current_nodes = set(stage.node_ids)
            if not current_nodes.issuperset(prev_nodes):
                missing = prev_nodes - current_nodes
                raise ValueError(
                    f"stage {stage.stage_key!r} dropped nodes from a previous "
                    f"stage (non-monotone): {sorted(missing)[:5]}..."
                )
            prev_nodes = current_nodes
        return self
