"""Tests for :class:`poe1_builds.BuildsService`.

Covers the facade's two concerns: multi-source fan-out (driven by the
MockTransport) and post-fetch filters (classify_defense,
main_skill_of). The service is trimmed in ``conftest.py`` to the five
ascendancies we have per-class protobuf fixtures for, so fan-out is
deterministic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from poe1_builds import (
    BuildFilter,
    BuildsService,
    DefenseType,
    DefensiveStats,
    FullBuild,
    RemoteBuildRef,
)
from poe1_builds.service import DEFAULT_ASCENDANCIES

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# DEFAULT_ASCENDANCIES sanity
# ---------------------------------------------------------------------------


def test_default_ascendancies_has_19_canonical() -> None:
    # 3 per class * 6 base classes + Ascendant on Scion = 19.
    assert len(DEFAULT_ASCENDANCIES) == 19
    # A sampling of canonical names (spelling matches poe.ninja's).
    for name in ("Slayer", "Deadeye", "Necromancer", "Hierophant", "Ascendant"):
        assert name in DEFAULT_ASCENDANCIES


# ---------------------------------------------------------------------------
# classify_defense — one case per branch
# ---------------------------------------------------------------------------


def _stats(*, life: int = 0, es: int = 0, mana: int = 0) -> DefensiveStats:
    """Build a DefensiveStats via model_validate — fields have camelCase aliases."""

    return DefensiveStats.model_validate(
        {"life": life, "energyShield": es, "mana": mana}
    )


def test_classify_defense_life() -> None:
    stats = _stats(life=5000, es=100, mana=500)
    assert BuildsService.classify_defense(stats) is DefenseType.LIFE


def test_classify_defense_ci() -> None:
    # life == 1 (CI-engine reading) and es >= 5000 → CI.
    stats = _stats(life=1, es=8000, mana=500)
    assert BuildsService.classify_defense(stats) is DefenseType.CI


def test_classify_defense_low_life() -> None:
    # life == 1 but ES below CI threshold → LowLife.
    stats = _stats(life=1, es=2000, mana=200)
    assert BuildsService.classify_defense(stats) is DefenseType.LOW_LIFE


def test_classify_defense_energy_shield() -> None:
    # es >= life * 3 → EnergyShield (but life > 1 so not CI).
    stats = _stats(life=1000, es=4000, mana=500)
    assert BuildsService.classify_defense(stats) is DefenseType.ENERGY_SHIELD


def test_classify_defense_life_es_hybrid() -> None:
    # es >= life / 2 but less than life * 3 → LifeES.
    stats = _stats(life=4000, es=2500, mana=500)
    assert BuildsService.classify_defense(stats) is DefenseType.LIFE_ES


def test_classify_defense_mom() -> None:
    # mana >= life * 2 (and es low) → MoM.
    stats = _stats(life=2000, es=100, mana=5000)
    assert BuildsService.classify_defense(stats) is DefenseType.MOM


# ---------------------------------------------------------------------------
# main_skill_of / matches_main_skill against the Brain fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def brain_build() -> FullBuild:
    raw = cast(
        "dict[str, object]",
        json.loads((FIXTURES / "character_brainwar_brain.json").read_text(encoding="utf-8")),
    )
    raw["source_id"] = "ninja::mirage::Brainwar-1546::Brain\u318d"
    raw["snapshot_version"] = "0606-20260424-28035"
    raw["fetched_at"] = "2026-04-24T00:00:00Z"
    raw["league"] = "Mirage"
    return FullBuild.model_validate(raw)


def test_main_skill_of_brain(brain_build: FullBuild) -> None:
    name = BuildsService.main_skill_of(brain_build)
    assert name is not None
    # Brain is a Fire Trap Chieftain — the primary-gem heuristic
    # should surface "Fire Trap" regardless of support gems bunched
    # into the same group.
    assert "Fire Trap" in name


def test_matches_main_skill_substring(brain_build: FullBuild) -> None:
    assert BuildsService.matches_main_skill(brain_build, "Fire")
    assert BuildsService.matches_main_skill(brain_build, "fire")
    assert BuildsService.matches_main_skill(brain_build, "TRAP")
    assert BuildsService.matches_main_skill(brain_build, "")  # empty → always matches


def test_matches_main_skill_negative(brain_build: FullBuild) -> None:
    assert not BuildsService.matches_main_skill(brain_build, "Righteous Fire")
    assert not BuildsService.matches_main_skill(brain_build, "Tornado Shot")


def test_matches_defense_type_brain_is_life(brain_build: FullBuild) -> None:
    # Brainwar has life=5433, es=109, mana=787 — pure Life build.
    assert BuildsService.matches_defense_type(brain_build, DefenseType.LIFE)
    assert not BuildsService.matches_defense_type(brain_build, DefenseType.CI)
    assert not BuildsService.matches_defense_type(brain_build, DefenseType.ENERGY_SHIELD)


# ---------------------------------------------------------------------------
# fetch_refs — single-class fast path
# ---------------------------------------------------------------------------


async def test_fetch_refs_single_class(builds_service: BuildsService) -> None:
    snap = await builds_service.fetch_refs(BuildFilter(class_="Slayer"))
    assert snap.league == "Mirage"
    assert len(snap.refs) == 100
    assert all(r.class_name == "Slayer" for r in snap.refs)


# ---------------------------------------------------------------------------
# fetch_refs — multi-class fan-out
# ---------------------------------------------------------------------------


async def test_fetch_refs_multi_class_fanout(builds_service: BuildsService) -> None:
    # conftest shrinks ascendancies to 5 → expect 500 refs in total.
    snap = await builds_service.fetch_refs()
    assert snap.league == "Mirage"
    assert snap.snapshot_version  # propagated from underlying snapshots
    assert len(snap.refs) == 5 * 100
    # Every ref should pin exactly one of the five per-class fixtures.
    classes = {r.class_name for r in snap.refs}
    assert classes == {"Slayer", "Deadeye", "Chieftain", "Necromancer", "Hierophant"}


async def test_fetch_refs_multi_class_none_filter_equivalent(
    builds_service: BuildsService,
) -> None:
    # Explicit None vs. default should give the same result.
    snap_none = await builds_service.fetch_refs(None)
    snap_default = await builds_service.fetch_refs()
    assert len(snap_none.refs) == len(snap_default.refs)


async def test_fetch_refs_respects_per_class_top_n(
    builds_service: BuildsService,
) -> None:
    snap = await builds_service.fetch_refs(BuildFilter(top_n_per_class=20))
    # 20 refs per class * 5 classes = 100 total.
    assert len(snap.refs) == 5 * 20


# ---------------------------------------------------------------------------
# get_detail / hydrate
# ---------------------------------------------------------------------------


async def test_get_detail_single(builds_service: BuildsService) -> None:
    # Build a ref that matches the character fixture served by the
    # MockTransport.
    ref = RemoteBuildRef.model_validate(
        {
            "source_id": "ninja::mirage::Brainwar-1546::Brain\u318d",
            "account": "Brainwar-1546",
            "character": "Brain\u318d",
            "class": "Chieftain",
            "level": 100,
            "life": 5433,
            "energy_shield": 109,
            "ehp": 180_000,
            "dps": 1_200_000,
            "main_skill": None,
            "league": "Mirage",
            "snapshot_version": "0606-20260424-28035",
            "fetched_at": datetime(2026, 4, 24, tzinfo=UTC),
        }
    )
    build = await builds_service.get_detail(ref)
    assert isinstance(build, FullBuild)
    assert build.account == "Brainwar-1546"
    assert build.name == "Brain\u318d"


async def test_hydrate_bounded_concurrency(builds_service: BuildsService) -> None:
    # Hydrate the same ref three times to verify the concurrency=2
    # bounded path doesn't deadlock and yields a list of FullBuilds.
    ref = RemoteBuildRef.model_validate(
        {
            "source_id": "ninja::mirage::Brainwar-1546::Brain\u318d",
            "account": "Brainwar-1546",
            "character": "Brain\u318d",
            "class": "Chieftain",
            "level": 100,
            "life": 5433,
            "energy_shield": 109,
            "ehp": 180_000,
            "dps": 1_200_000,
            "main_skill": None,
            "league": "Mirage",
            "snapshot_version": "0606-20260424-28035",
            "fetched_at": datetime(2026, 4, 24, tzinfo=UTC),
        }
    )
    builds = await builds_service.hydrate((ref, ref, ref), concurrency=2)
    assert len(builds) == 3
    assert all(isinstance(b, FullBuild) for b in builds)
    assert all(b.account == "Brainwar-1546" for b in builds)


# ---------------------------------------------------------------------------
# Service property getters
# ---------------------------------------------------------------------------


def test_builds_service_league_property(builds_service: BuildsService) -> None:
    assert builds_service.league == "Mirage"
