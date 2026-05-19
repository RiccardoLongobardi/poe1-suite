"""Unit tests for the Theorycrafter Build Generator (Step 38).

Pure-function + model coverage. The end-to-end test of the
``/fob/theory/generate`` endpoint (real protobuf ladder fixtures + real
character JSON) lives in ``apps/server/tests/test_fob_router.py``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from poe1_fob.theory import SkeletonUnique, TheoryBuildSkeleton, TheoryError
from poe1_fob.theory.generator import _compose_rationale, _fmt, _ninja_url


def test_skeleton_unique_frozen() -> None:
    u = SkeletonUnique(name="Mageblood", slot="Belt", tier="mageblood")
    with pytest.raises(ValidationError):
        u.name = "Headhunter"


def test_build_skeleton_shape() -> None:
    sk = TheoryBuildSkeleton(
        query="build tanky con RF",
        character_class="Marauder",
        ascendancy="Chieftain",
        main_skill="Righteous Fire",
        support_gems=("Elemental Focus", "Burning Damage"),
        level=95,
        key_uniques=(SkeletonUnique(name="Springleaf", slot="Shield", tier="leveling"),),
        keystones=("Avatar of Fire",),
        passive_count=120,
        content_focus=("mapping",),
        template_name="RF Pohx",
        rationale="prova",
        source_account="Acc-1",
        source_character="Char",
        source_url="https://poe.ninja/builds/mirage/character/Acc-1/Char",
    )
    assert sk.character_class == "Marauder"
    assert sk.main_skill == "Righteous Fire"
    assert len(sk.key_uniques) == 1
    with pytest.raises(ValidationError):
        sk.level = 100


def test_build_skeleton_rejects_out_of_range_level() -> None:
    with pytest.raises(ValidationError):
        TheoryBuildSkeleton(
            query="x",
            character_class="Witch",
            main_skill="Spark",
            level=200,
            template_name="Spark Inq",
            rationale="r",
            source_account="a",
            source_character="c",
            source_url="u",
        )


def test_fmt_groups_thousands_italian_style() -> None:
    assert _fmt(1234567) == "1.234.567"
    assert _fmt(500) == "500"


def test_ninja_url_slugifies_multiword_league() -> None:
    assert (
        _ninja_url("Settlers of Kalguur", "Acc-1", "Hero")
        == "https://poe.ninja/builds/settlers-of-kalguur/character/Acc-1/Hero"
    )


def test_compose_rationale_picks_energy_shield_when_dominant() -> None:
    text = _compose_rationale(
        template_name="Vortex Occultist",
        character="Chillz",
        ascendancy="Occultist",
        level=96,
        life=2000,
        energy_shield=9000,
        dps=1_500_000,
        content=("bossing",),
    )
    assert "9.000 energy shield" in text
    assert "1.500.000 DPS" in text
    assert "bossing" in text
    # Honesty clause — the skeleton is never invented.
    assert "non sono inventati" in text


def test_compose_rationale_defaults_content_to_all() -> None:
    text = _compose_rationale(
        template_name="T",
        character="C",
        ascendancy=None,
        level=90,
        life=6000,
        energy_shield=0,
        dps=100,
        content=(),
    )
    assert "tutti i contenuti" in text
    assert "6.000 vita" in text


def test_theory_error_is_runtime_error() -> None:
    assert issubclass(TheoryError, RuntimeError)
