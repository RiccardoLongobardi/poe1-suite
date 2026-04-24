"""Tests for :func:`snapshot_to_build`."""

from __future__ import annotations

from pathlib import Path

import pytest

from poe1_core.models import (
    Ascendancy,
    BuildSourceType,
    CharacterClass,
    ContentFocus,
    DamageProfile,
    DefenseProfile,
    ItemRarity,
    ItemSlot,
    Playstyle,
)
from poe1_fob.pob import decode_export, parse_snapshot, snapshot_to_build
from poe1_fob.pob.mapper import (
    _classify_damage_profile,
    _classify_defense,
    _classify_playstyle,
)
from poe1_fob.pob.models import PobGem, PobSkillGroup

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REAL_POB = (FIXTURE_DIR / "pob_YNQeadFwNBmX.txt").read_text().strip()


# ---------------------------------------------------------------------------
# End-to-end on real fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_build() -> object:
    snap = parse_snapshot(
        decode_export(REAL_POB),
        export_code=REAL_POB,
        origin_url="https://pobb.in/YNQeadFwNBmX",
    )
    return snapshot_to_build(snap, source_id="pob::YNQeadFwNBmX")


def test_build_identity_from_real_fixture(real_build: object) -> None:
    # real_build is the Build returned by snapshot_to_build.
    from poe1_core.models import Build  # local import keeps module import list tight

    assert isinstance(real_build, Build)
    assert real_build.source_id == "pob::YNQeadFwNBmX"
    assert real_build.source_type is BuildSourceType.POB
    assert real_build.character_class is CharacterClass.MARAUDER
    assert real_build.ascendancy is Ascendancy.CHIEFTAIN


def test_build_main_skill_identified(real_build) -> None:  # type: ignore[no-untyped-def]
    assert real_build.main_skill == "Raise Spectre"
    # At least one support gem should come through (build uses Empower etc.).
    assert real_build.support_gems
    assert all(isinstance(s, str) and s for s in real_build.support_gems)


def test_build_classified_as_minion(real_build) -> None:  # type: ignore[no-untyped-def]
    assert real_build.playstyle is Playstyle.MINION
    # Our spectre fixture does minion elemental damage (e.g. Syndicate
    # Operative / arctic / similar) — minion_elemental or minion_chaos
    # are both plausible, but never a non-minion profile.
    assert real_build.damage_profile in (
        DamageProfile.MINION_ELEMENTAL,
        DamageProfile.MINION_CHAOS,
        DamageProfile.MINION_PHYSICAL,
    )


def test_build_defense_profile_coherent(real_build) -> None:  # type: ignore[no-untyped-def]
    # The fixture has life > ES, so defence should be LIFE or HYBRID.
    assert real_build.defense_profile in (
        DefenseProfile.LIFE,
        DefenseProfile.HYBRID,
    )
    assert real_build.metrics.life is not None
    assert real_build.metrics.life > 1000


def test_build_metrics_have_meaningful_dps(real_build) -> None:  # type: ignore[no-untyped-def]
    assert real_build.metrics.total_dps is not None
    assert real_build.metrics.total_dps > 1_000_000.0


def test_build_resists_capped_within_bounds(real_build) -> None:  # type: ignore[no-untyped-def]
    for res in (
        real_build.metrics.fire_res,
        real_build.metrics.cold_res,
        real_build.metrics.lightning_res,
        real_build.metrics.chaos_res,
    ):
        assert res is None or -200 <= res <= 200


def test_build_content_tags_include_mapping(real_build) -> None:  # type: ignore[no-untyped-def]
    # Every build is MAPPING-capable by default.
    assert ContentFocus.MAPPING in real_build.content_tags
    # With hundreds of millions of DPS, BOSSING and UBERS should be tagged too.
    assert ContentFocus.BOSSING in real_build.content_tags
    assert ContentFocus.UBERS in real_build.content_tags


def test_build_key_items_are_uniques(real_build) -> None:  # type: ignore[no-untyped-def]
    assert real_build.key_items  # non-empty for a level-100 build
    for key in real_build.key_items:
        assert key.item.rarity is ItemRarity.UNIQUE
        assert 1 <= key.importance <= 5
        assert isinstance(key.slot, ItemSlot)


def test_build_preserves_pob_provenance(real_build) -> None:  # type: ignore[no-untyped-def]
    assert real_build.pob_code == REAL_POB
    assert real_build.origin_url == "https://pobb.in/YNQeadFwNBmX"
    # Tree version comes from the <Spec> attribute — e.g. "3_28".
    assert real_build.tree_version and real_build.tree_version.startswith("3_")


# ---------------------------------------------------------------------------
# Unit coverage of classifiers (no fixture needed)
# ---------------------------------------------------------------------------


def _group_with(main: str, *, supports: tuple[str, ...] = ()) -> PobSkillGroup:
    gems = [
        PobGem(
            name=main,
            skill_id=main.replace(" ", ""),
            level=20,
            quality=0,
            enabled=True,
            is_support=False,
        ),
        *[
            PobGem(
                name=s,
                skill_id=f"Support{s.replace(' ', '')}",
                level=20,
                quality=0,
                enabled=True,
                is_support=True,
            )
            for s in supports
        ],
    ]
    return PobSkillGroup(socket_group=1, enabled=True, is_main=True, gems=tuple(gems))


@pytest.mark.parametrize(
    "skill_id, expected",
    [
        ("RaiseSpectre", Playstyle.MINION),
        ("SummonSkeletons", Playstyle.MINION),
        ("Cyclone", Playstyle.MELEE),
        ("TornadoShot", Playstyle.RANGED_ATTACK),
        ("FireballTotem", Playstyle.TOTEM),
        ("ArmageddonBrand", Playstyle.BRAND),
        ("LightningTrap", Playstyle.TRAP),
        ("ExplosiveMine", Playstyle.MINE),
        ("RighteousFire", Playstyle.DEGEN_AURA),
    ],
)
def test_classify_playstyle(skill_id: str, expected: Playstyle) -> None:
    assert _classify_playstyle(skill_id, _group_with(skill_id)) is expected


def test_classify_damage_profile_fire_hit() -> None:
    stats = {"FireDPS": 1_000_000.0, "ColdDPS": 0.0, "LightningDPS": 0.0}
    assert _classify_damage_profile("Fireball", stats) is DamageProfile.FIRE


def test_classify_damage_profile_ignite_dominates() -> None:
    stats = {"IgniteDPS": 10_000_000.0, "FireDPS": 500.0, "AverageDamage": 100.0}
    assert _classify_damage_profile("RighteousFire", stats) is DamageProfile.IGNITE


def test_classify_damage_profile_minion_chaos_pick() -> None:
    stats = {"ChaosDPS": 5_000_000.0, "FireDPS": 100_000.0}
    assert _classify_damage_profile("RaiseSpectre", stats) is DamageProfile.MINION_CHAOS


def test_classify_defense_ci_flag() -> None:
    stats = {"ChaosInoculation": 1.0, "Life": 1.0, "EnergyShield": 8000.0}
    assert _classify_defense(stats, None) is DefenseProfile.CHAOS_INOCULATION


def test_classify_defense_low_life() -> None:
    stats = {"LowLife": 1.0, "Life": 1500.0, "EnergyShield": 6000.0}
    assert _classify_defense(stats, None) is DefenseProfile.LOW_LIFE


def test_classify_defense_defaults_to_life() -> None:
    stats = {"Life": 6000.0, "EnergyShield": 100.0}
    assert _classify_defense(stats, None) is DefenseProfile.LIFE
