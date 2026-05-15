"""Step 19 — population stats over the poe.ninja ladder.

Aggregator that turns a tuple of :class:`RemoteBuildRef` into a
compact summary the Finder UI can render above the recommend
results:

* ``top_skills`` — top-N main-skill counts + percentages per
  ascendancy, lets the user see "most Slayers play Cyclone right now".
* ``stat_distributions`` — p25 / p50 / p75 / p90 quantiles for life,
  ES, EHP, DPS, level. Lets the user see "what does an endgame
  Necromancer actually look like stat-wise" before committing to
  the ranking pool.

Pure functions, no HTTP. The data they aggregate is the same
``RemoteBuildRef`` tuple :class:`BuildsService.fetch_refs` already
returns — caller wires the source.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from .models import RemoteBuildRef

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SkillPopularity(BaseModel):
    """One row of the top-skills table."""

    model_config = ConfigDict(frozen=True)

    skill: str = Field(..., description="Main skill name as poe.ninja reports it.")
    count: int = Field(..., ge=0, description="Builds running this skill in the sample.")
    pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Share of the sample (with-skill subset) as a percentage.",
    )


class StatDistribution(BaseModel):
    """Quantile snapshot for one stat (life / ehp / dps / level)."""

    model_config = ConfigDict(frozen=True)

    sample_size: int = Field(..., ge=0, description="Refs with a non-zero value.")
    p25: int = Field(..., ge=0)
    p50: int = Field(..., ge=0)
    p75: int = Field(..., ge=0)
    p90: int = Field(..., ge=0)


class PopulationStats(BaseModel):
    """Aggregated stats over a sampled subset of poe.ninja refs."""

    model_config = ConfigDict(frozen=True)

    ascendancy: str | None = Field(
        default=None,
        description="Ascendancy the sample was filtered to. None = whole league.",
    )
    total_builds: int = Field(..., ge=0, description="Refs in the aggregation pool.")
    top_skills: tuple[SkillPopularity, ...] = Field(
        default=(),
        description="Top-N most-played main skills, descending by count.",
    )
    life: StatDistribution | None = Field(
        default=None, description="Life percentile distribution. None when no data."
    )
    energy_shield: StatDistribution | None = Field(
        default=None, description="Energy shield percentile distribution."
    )
    ehp: StatDistribution | None = Field(default=None, description="EHP percentile distribution.")
    dps: StatDistribution | None = Field(
        default=None, description="Combined DPS percentile distribution."
    )
    level: StatDistribution | None = Field(
        default=None, description="Character level percentile distribution."
    )


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def _percentile(values: list[int], pct: float) -> int:
    """Return the *pct* percentile (0..1) of an already-sorted list.

    Uses nearest-rank (no interpolation) — players' rounded stats
    don't benefit from interpolation accuracy, and integer outputs
    are easier to read in the UI.
    """

    if not values:
        return 0
    n = len(values)
    # nearest-rank: ceil(pct * n) - 1, clamped.
    idx = min(n - 1, max(0, int(pct * n)))
    return int(values[idx])


def _distribution(raw_values: Iterable[int]) -> StatDistribution | None:
    """Compute p25/p50/p75/p90 over a stat. Drops zeros (no signal)."""

    values = sorted(v for v in raw_values if v > 0)
    if not values:
        return None
    return StatDistribution(
        sample_size=len(values),
        p25=_percentile(values, 0.25),
        p50=_percentile(values, 0.50),
        p75=_percentile(values, 0.75),
        p90=_percentile(values, 0.90),
    )


def compute_population_stats(
    refs: tuple[RemoteBuildRef, ...] | list[RemoteBuildRef],
    *,
    ascendancy: str | None = None,
    top_n_skills: int = 10,
) -> PopulationStats:
    """Aggregate population stats over *refs*.

    Returns an empty-but-valid envelope when *refs* is empty so the UI
    can render "no data" rather than failing.
    """

    refs_list = list(refs)
    total = len(refs_list)

    # Top skills — drop entries where main_skill is unknown (poe.ninja
    # sometimes omits it for builds without a "main" socket group).
    with_skill = [r for r in refs_list if r.main_skill]
    skill_counts = Counter(r.main_skill for r in with_skill if r.main_skill)
    total_with_skill = sum(skill_counts.values())
    top: list[SkillPopularity] = []
    for skill, count in skill_counts.most_common(top_n_skills):
        pct = round((count / total_with_skill) * 100, 1) if total_with_skill else 0.0
        top.append(SkillPopularity(skill=skill, count=count, pct=pct))

    return PopulationStats(
        ascendancy=ascendancy,
        total_builds=total,
        top_skills=tuple(top),
        life=_distribution(r.life for r in refs_list),
        energy_shield=_distribution(r.energy_shield for r in refs_list),
        ehp=_distribution(r.ehp for r in refs_list),
        dps=_distribution(r.dps for r in refs_list),
        level=_distribution(r.level for r in refs_list),
    )


__all__ = [
    "PopulationStats",
    "SkillPopularity",
    "StatDistribution",
    "compute_population_stats",
]
