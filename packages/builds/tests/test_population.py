"""Step 19 — tests for the population-stats aggregator."""

from __future__ import annotations

from datetime import UTC, datetime

from poe1_builds.models import RemoteBuildRef
from poe1_builds.population import (
    PopulationStats,
    _percentile,
    compute_population_stats,
)

_COUNTER = 0


def _ref(
    *,
    main_skill: str | None = "Cyclone",
    life: int = 5000,
    energy_shield: int = 0,
    ehp: int = 8000,
    dps: int = 1_000_000,
    level: int = 95,
    class_name: str = "Slayer",
) -> RemoteBuildRef:
    global _COUNTER
    _COUNTER += 1
    return RemoteBuildRef.model_validate(
        {
            "source_id": f"ninja::test::{_COUNTER}",
            "account": "a",
            "character": f"c{_COUNTER}",
            "class": class_name,
            "level": level,
            "life": life,
            "energy_shield": energy_shield,
            "ehp": ehp,
            "dps": dps,
            "main_skill": main_skill,
            "league": "Mirage",
            "snapshot_version": "v1",
            "fetched_at": datetime.now(UTC),
        }
    )


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------


def test_percentile_empty_returns_zero() -> None:
    assert _percentile([], 0.5) == 0


def test_percentile_single_value() -> None:
    assert _percentile([42], 0.5) == 42
    assert _percentile([42], 0.9) == 42


def test_percentile_quartiles() -> None:
    values = list(range(1, 101))  # 1..100, already sorted
    assert _percentile(values, 0.25) == 26  # 25*1 = idx 25 → value 26
    assert _percentile(values, 0.50) == 51
    assert _percentile(values, 0.90) == 91


# ---------------------------------------------------------------------------
# compute_population_stats
# ---------------------------------------------------------------------------


def test_empty_pool_returns_empty_envelope() -> None:
    stats = compute_population_stats([])
    assert stats.total_builds == 0
    assert stats.top_skills == ()
    assert stats.life is None
    assert stats.ehp is None
    assert stats.dps is None


def test_top_skills_orders_by_count_desc() -> None:
    refs = [
        _ref(main_skill="Cyclone"),
        _ref(main_skill="Cyclone"),
        _ref(main_skill="Cyclone"),
        _ref(main_skill="Boneshatter"),
        _ref(main_skill="Boneshatter"),
        _ref(main_skill="Tornado Shot"),
    ]
    stats = compute_population_stats(refs)
    assert stats.total_builds == 6
    # Cyclone first (3), Boneshatter (2), Tornado Shot (1)
    assert [s.skill for s in stats.top_skills] == [
        "Cyclone",
        "Boneshatter",
        "Tornado Shot",
    ]
    assert stats.top_skills[0].count == 3
    assert stats.top_skills[0].pct == 50.0


def test_top_skills_skips_missing_main_skill() -> None:
    """Refs without a main_skill are excluded from the popularity table."""

    refs = [
        _ref(main_skill="Cyclone"),
        _ref(main_skill=None),
        _ref(main_skill="Cyclone"),
        _ref(main_skill=None),
    ]
    stats = compute_population_stats(refs)
    # All 4 still count in total_builds, but only 2 contribute to skills.
    assert stats.total_builds == 4
    assert len(stats.top_skills) == 1
    assert stats.top_skills[0].skill == "Cyclone"
    assert stats.top_skills[0].count == 2
    # Percent is over the with-skill subset (2/2 = 100%).
    assert stats.top_skills[0].pct == 100.0


def test_top_skills_respects_top_n_cap() -> None:
    refs = [_ref(main_skill=f"Skill{i}") for i in range(10)]
    stats = compute_population_stats(refs, top_n_skills=3)
    assert len(stats.top_skills) == 3


def test_stat_distributions_compute_quantiles() -> None:
    # Construct an explicit DPS distribution we can hand-verify.
    refs = [_ref(dps=v) for v in (100, 200, 300, 400, 500, 600, 700, 800, 900, 1000)]
    stats = compute_population_stats(refs)
    assert stats.dps is not None
    assert stats.dps.sample_size == 10
    # p25 of [100..1000] sorted at idx 2 → 300
    assert stats.dps.p25 == 300
    assert stats.dps.p50 == 600
    assert stats.dps.p75 == 800
    assert stats.dps.p90 == 1000


def test_stat_distributions_drop_zero_values() -> None:
    """Zero values shouldn't pollute the percentile calculation."""

    refs = [
        _ref(life=0),
        _ref(life=0),
        _ref(life=5000),
        _ref(life=6000),
    ]
    stats = compute_population_stats(refs)
    assert stats.life is not None
    assert stats.life.sample_size == 2  # only the two non-zero values


def test_ascendancy_passthrough() -> None:
    """The ascendancy filter label is echoed back on the response."""

    refs = [_ref()]
    stats = compute_population_stats(refs, ascendancy="Slayer")
    assert stats.ascendancy == "Slayer"
    assert isinstance(stats, PopulationStats)


def test_stat_envelope_returns_none_when_all_zero() -> None:
    refs = [_ref(life=0, energy_shield=0, ehp=0, dps=0, level=1)]
    stats = compute_population_stats(refs)
    assert stats.life is None
    assert stats.energy_shield is None
    assert stats.ehp is None
    assert stats.dps is None
    # Level 1 is still > 0 so the level distribution computes.
    assert stats.level is not None
