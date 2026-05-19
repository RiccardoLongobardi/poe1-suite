"""Domain models for Theorycrafter — the build-from-scratch tool.

Step 38 ships only the **Build Generator** (Pillar 1). The user describes
the build they want in natural language; the generator extracts an
intent, ranks the poe.ninja ladder, picks the best-fit real build, and
reformats it as a clean :class:`TheoryBuildSkeleton`.

The skeleton is *anchored on a real ladder build* — it never invents
items or gem links. ``source_*`` fields expose which ladder character it
was derived from so the user can verify it.

No camelCase aliases: like :class:`PobSnapshot`, these models serialize
with their snake_case field names and the frontend consumes them as-is.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkeletonUnique(BaseModel):
    """One unique item in the generated skeleton, with its budget tier."""

    model_config = ConfigDict(frozen=True)

    name: str
    slot: str
    tier: str = Field(
        description=(
            "Budget tier from the gear classifier: "
            "mageblood / high / mid / cheap / leveling / cluster / mirror."
        ),
    )


class TheoryBuildSkeleton(BaseModel):
    """A complete build skeleton generated from a natural-language query.

    Every mechanical field (class, ascendancy, skill, links, uniques,
    keystones) comes verbatim from the best-fit ladder build — the
    generator only *selects and reformats*, it does not synthesise.
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(description="The original natural-language request.")
    character_class: str
    ascendancy: str | None = None
    main_skill: str
    support_gems: tuple[str, ...] = ()
    level: int = Field(ge=1, le=100)
    key_uniques: tuple[SkeletonUnique, ...] = ()
    keystones: tuple[str, ...] = ()
    passive_count: int = Field(default=0, ge=0)
    content_focus: tuple[str, ...] = ()
    template_name: str
    rationale: str = Field(description="Italian prose explaining the build identity.")
    source_account: str
    source_character: str
    source_url: str


__all__ = ["SkeletonUnique", "TheoryBuildSkeleton"]
