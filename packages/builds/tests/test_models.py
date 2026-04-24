"""Tests for poe1_builds.models.

Exercises every domain model against **real poe.ninja fixtures** so
schema drift surfaces as a test failure. No synthetic payloads.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from pydantic import ValidationError

from poe1_builds import (
    BuildFilter,
    BuildSortKey,
    BuildsSnapshot,
    BuildStatus,
    DefenseType,
    DefensiveStats,
    FullBuild,
    GemRef,
    ItemEntry,
    KeystonePassive,
    RemoteBuildRef,
    SkillGroup,
)

FIXTURES = Path(__file__).parent / "fixtures"
CHARACTER_FIXTURE = FIXTURES / "character_brainwar_brain.json"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


def test_defense_type_values() -> None:
    assert DefenseType.LIFE.value == "Life"
    assert DefenseType.LIFE_ES.value == "LifeES"
    assert DefenseType.CI.value == "CI"
    assert DefenseType.LOW_LIFE.value == "LowLife"
    assert DefenseType.MOM.value == "MoM"


def test_build_sort_key_values() -> None:
    assert BuildSortKey.LEVEL.value == "level"
    assert BuildSortKey.EHP.value == "ehp"


def test_build_status_values() -> None:
    assert int(BuildStatus.ACTIVE) == 3
    assert int(BuildStatus.OUTDATED) == 2
    assert int(BuildStatus.INACTIVE) == 1
    assert int(BuildStatus.UNKNOWN) == 0


# ---------------------------------------------------------------------------
# BuildFilter
# ---------------------------------------------------------------------------


def test_build_filter_defaults_are_useful() -> None:
    f = BuildFilter()
    assert f.class_ is None
    assert f.main_skill is None
    assert f.level_range is None
    assert f.defense_type is None
    assert f.top_n_per_class == 200


def test_build_filter_is_frozen() -> None:
    f = BuildFilter(class_="Slayer")
    with pytest.raises(ValidationError):
        f.class_ = "Champion"


def test_build_filter_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        BuildFilter.model_validate({"unknown_field": "oops"})


@pytest.mark.parametrize(
    "level_range",
    [
        (90, 85),  # inverted
        (0, 80),  # below 1
        (80, 101),  # above 100
    ],
)
def test_build_filter_rejects_bad_level_range(level_range: tuple[int, int]) -> None:
    with pytest.raises(ValidationError):
        BuildFilter(level_range=level_range)


def test_build_filter_accepts_valid_level_range() -> None:
    f = BuildFilter(level_range=(80, 100))
    assert f.level_range == (80, 100)


def test_build_filter_top_n_bounds() -> None:
    BuildFilter(top_n_per_class=1)
    BuildFilter(top_n_per_class=2000)
    with pytest.raises(ValidationError):
        BuildFilter(top_n_per_class=0)
    with pytest.raises(ValidationError):
        BuildFilter(top_n_per_class=2001)


# ---------------------------------------------------------------------------
# RemoteBuildRef
# ---------------------------------------------------------------------------


def _sample_ref(**overrides: object) -> RemoteBuildRef:
    base: dict[str, object] = {
        "source_id": "ninja::Mirage::Brainwar-1546::Brain",
        "account": "Brainwar-1546",
        "character": "Brain",
        "class": "Chieftain",
        "level": 100,
        "life": 5000,
        "energy_shield": 0,
        "ehp": 180_000,
        "dps": 1_200_000,
        "main_skill": "Righteous Fire",
        "league": "Mirage",
        "snapshot_version": "0606-20260424-28035",
        "fetched_at": datetime(2026, 4, 24, tzinfo=UTC),
    }
    base.update(overrides)
    return RemoteBuildRef.model_validate(base)


def test_remote_build_ref_accepts_class_alias() -> None:
    ref = _sample_ref()
    assert ref.class_name == "Chieftain"
    dumped = ref.model_dump(by_alias=True)
    assert dumped["class"] == "Chieftain"
    assert "class_name" not in dumped


def test_remote_build_ref_level_clamp() -> None:
    with pytest.raises(ValidationError):
        _sample_ref(level=0)
    with pytest.raises(ValidationError):
        _sample_ref(level=101)


def test_remote_build_ref_negative_stats_rejected() -> None:
    with pytest.raises(ValidationError):
        _sample_ref(life=-1)
    with pytest.raises(ValidationError):
        _sample_ref(dps=-1)


def test_remote_build_ref_is_frozen() -> None:
    ref = _sample_ref()
    with pytest.raises(ValidationError):
        ref.level = 99


# ---------------------------------------------------------------------------
# BuildsSnapshot
# ---------------------------------------------------------------------------


def test_builds_snapshot_by_source_id() -> None:
    a = _sample_ref(source_id="a", character="A")
    b = _sample_ref(source_id="b", character="B")
    snap = BuildsSnapshot(
        league="Mirage",
        snapshot_version="0606-20260424-28035",
        fetched_at=datetime(2026, 4, 24, tzinfo=UTC),
        total=2,
        refs=(a, b),
    )
    assert snap.by_source_id("a") is a
    assert snap.by_source_id("b") is b
    assert snap.by_source_id("missing") is None


def test_builds_snapshot_total_non_negative() -> None:
    with pytest.raises(ValidationError):
        BuildsSnapshot(
            league="Mirage",
            snapshot_version="v",
            fetched_at=datetime(2026, 4, 24, tzinfo=UTC),
            total=-1,
            refs=(),
        )


# ---------------------------------------------------------------------------
# FullBuild from real fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def character_payload() -> dict[str, object]:
    raw = cast(
        "dict[str, object]",
        json.loads(CHARACTER_FIXTURE.read_text(encoding="utf-8")),
    )
    # Inject the bookkeeping fields we attach in the adapter.
    raw["source_id"] = "ninja::Mirage::Brainwar-1546::Brain"
    raw["snapshot_version"] = "0606-20260424-28035"
    raw["fetched_at"] = "2026-04-24T00:00:00Z"
    raw["league"] = "Mirage"
    return raw


def test_full_build_parses_real_character(character_payload: dict[str, object]) -> None:
    build = FullBuild.model_validate(character_payload)
    assert build.account == "Brainwar-1546"
    assert build.name == "Brain\u318d"
    assert build.class_name == "Chieftain"
    assert build.base_class == "Marauder"
    assert build.ascendancy_class_name == "Chieftain"
    assert build.level == 100
    assert build.league == "Mirage"
    assert build.snapshot_version == "0606-20260424-28035"
    assert build.path_of_building_export.strip()
    assert len(build.path_of_building_export) > 1000
    assert len(build.skills) == 8
    assert len(build.items) == 12
    assert len(build.key_stones) == 1


def test_full_build_defensive_stats_all_35_fields(
    character_payload: dict[str, object],
) -> None:
    build = FullBuild.model_validate(character_payload)
    stats = build.defensive_stats
    assert stats.life > 0
    assert stats.effective_health_pool > 0
    assert stats.fire_resistance >= 75
    assert stats.cold_resistance >= 75
    assert stats.lightning_resistance >= 75
    dumped = stats.model_dump(by_alias=True)
    for json_key in [
        "life",
        "energyShield",
        "mana",
        "ward",
        "movementSpeed",
        "lifeRegen",
        "evasionRating",
        "armour",
        "strength",
        "dexterity",
        "intelligence",
        "enduranceCharges",
        "frenzyCharges",
        "powerCharges",
        "effectiveHealthPool",
        "physicalMaximumHitTaken",
        "fireMaximumHitTaken",
        "coldMaximumHitTaken",
        "lightningMaximumHitTaken",
        "chaosMaximumHitTaken",
        "fireResistance",
        "fireResistanceOverCap",
        "coldResistance",
        "coldResistanceOverCap",
        "lightningResistance",
        "lightningResistanceOverCap",
        "chaosResistance",
        "chaosResistanceOverCap",
        "blockChance",
        "spellBlockChance",
        "spellSuppressionChance",
        "spellDodgeChance",
        "itemRarity",
        "physicalTakenAs",
        "lowestMaximumHitTaken",
    ]:
        assert json_key in dumped, f"DefensiveStats missing alias {json_key}"


def test_full_build_skills_parse_as_skill_groups(
    character_payload: dict[str, object],
) -> None:
    build = FullBuild.model_validate(character_payload)
    assert all(isinstance(s, SkillGroup) for s in build.skills)
    for sg in build.skills:
        assert sg.item_slot >= 0
        assert all(isinstance(g, GemRef) for g in sg.all_gems)


def test_full_build_items_parse_as_item_entries(
    character_payload: dict[str, object],
) -> None:
    build = FullBuild.model_validate(character_payload)
    assert all(isinstance(i, ItemEntry) for i in build.items)
    assert all(len(i.item_data) > 0 for i in build.items)


def test_full_build_keystones_parse(character_payload: dict[str, object]) -> None:
    build = FullBuild.model_validate(character_payload)
    assert all(isinstance(k, KeystonePassive) for k in build.key_stones)
    assert all(k.name for k in build.key_stones)


def test_full_build_is_frozen(character_payload: dict[str, object]) -> None:
    build = FullBuild.model_validate(character_payload)
    with pytest.raises(ValidationError):
        build.level = 99


def test_full_build_roundtrip_via_aliases(character_payload: dict[str, object]) -> None:
    build = FullBuild.model_validate(character_payload)
    dumped = build.model_dump(by_alias=True, mode="json")
    rebuilt = FullBuild.model_validate(dumped)
    assert rebuilt.account == build.account
    assert rebuilt.level == build.level
    assert rebuilt.class_name == build.class_name
    assert rebuilt.path_of_building_export == build.path_of_building_export
    assert len(rebuilt.skills) == len(build.skills)
    assert len(rebuilt.items) == len(build.items)


def test_full_build_extra_allowed(character_payload: dict[str, object]) -> None:
    """Unknown fields from upstream should not break parsing."""
    payload = dict(character_payload)
    payload["brandNewFieldFromNinja"] = {"foo": 1}
    build = FullBuild.model_validate(payload)
    assert build.account == "Brainwar-1546"


# ---------------------------------------------------------------------------
# DefensiveStats directly (isolated)
# ---------------------------------------------------------------------------


def test_defensive_stats_all_defaults_zero() -> None:
    s = DefensiveStats()
    assert s.life == 0
    assert s.energy_shield == 0
    assert s.chaos_resistance_over_cap == 0


def test_defensive_stats_accepts_alias_and_python_names() -> None:
    s_alias = DefensiveStats.model_validate({"energyShield": 1234})
    s_py = DefensiveStats.model_validate({"energy_shield": 1234})
    assert s_alias.energy_shield == 1234
    assert s_py.energy_shield == 1234
