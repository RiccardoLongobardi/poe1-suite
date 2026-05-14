"""Step 18 — tests for dynamic gem progression derivation."""

from __future__ import annotations

from pathlib import Path

import pytest

from poe1_core.models.enums import ItemSlot
from poe1_fob.gems.dynamic import (
    _is_awakened,
    _is_trigger,
    _is_vaal,
    _map_slot,
    _project_gem,
    _project_level_quality,
    _strip_awakened,
    _strip_vaal,
    derive_gem_progression,
)
from poe1_fob.pob import decode_export, parse_snapshot
from poe1_fob.pob.models import PobGem

# ---------------------------------------------------------------------------
# _project_level_quality
# ---------------------------------------------------------------------------


def test_project_lvl21q20_user_in_early_campaign() -> None:
    """A 21/20 endgame gem projects to ~lvl 9 / quality 0 at Early Campaign."""

    level, quality = _project_level_quality(user_level=21, user_quality=20, stage_index=0)
    assert level == 9  # max(1, 21-12)
    assert quality == 0


def test_project_lvl21q20_at_high_investment_stays_user_actual() -> None:
    """Stage 6 must echo the user's actual lvl/quality verbatim."""

    level, quality = _project_level_quality(user_level=21, user_quality=20, stage_index=5)
    assert level == 21
    assert quality == 20


def test_project_low_level_gem_at_early_stage_clamps_to_one() -> None:
    """A user-level-1 gem can't downscale below 1."""

    level, quality = _project_level_quality(user_level=1, user_quality=0, stage_index=0)
    assert level == 1
    assert quality == 0


def test_project_floor_step_progression_monotone() -> None:
    """For a lvl 21 / Q 20 gem, levels across stages 0-5 are non-decreasing."""

    levels = [_project_level_quality(21, 20, i)[0] for i in range(6)]
    assert levels == sorted(levels)


# ---------------------------------------------------------------------------
# Awakened / Vaal helpers
# ---------------------------------------------------------------------------


def test_is_awakened_recognises_awakened_prefix() -> None:
    assert _is_awakened("Awakened Burning Damage Support")
    assert not _is_awakened("Burning Damage Support")
    assert not _is_awakened("Empower Support")


def test_strip_awakened_returns_base_gem_name() -> None:
    assert _strip_awakened("Awakened Burning Damage Support") == "Burning Damage Support"
    assert _strip_awakened("Awakened Empower Support") == "Empower Support"


def test_is_vaal_and_strip() -> None:
    assert _is_vaal("Vaal Righteous Fire")
    assert _strip_vaal("Vaal Righteous Fire") == "Righteous Fire"
    assert _strip_vaal("Righteous Fire") == "Righteous Fire"


def test_is_trigger_cwdt_match() -> None:
    assert _is_trigger("Cast When Damage Taken Support")
    assert _is_trigger("Cast On Critical Strike Support")
    assert not _is_trigger("Empower Support")


# ---------------------------------------------------------------------------
# Slot mapping
# ---------------------------------------------------------------------------


def test_map_slot_body_armour() -> None:
    assert _map_slot("Body Armour") == ItemSlot.BODY_ARMOUR


def test_map_slot_falls_back_to_body_armour_for_unknown() -> None:
    assert _map_slot(None) == ItemSlot.BODY_ARMOUR
    assert _map_slot("Weird Slot Name") == ItemSlot.BODY_ARMOUR


def test_map_slot_handles_weapon_swap() -> None:
    """PoB's "Weapon 2 Swap" → WEAPON_OFFHAND (we ignore the swap dimension)."""

    assert _map_slot("Weapon 2 Swap") == ItemSlot.WEAPON_OFFHAND
    assert _map_slot("Weapon 1 Swap") == ItemSlot.WEAPON_MAIN


# ---------------------------------------------------------------------------
# Per-gem projection
# ---------------------------------------------------------------------------


def _gem(name: str, *, level: int = 21, quality: int = 20, is_support: bool = False) -> PobGem:
    return PobGem(
        name=name,
        skill_id=name.replace(" ", ""),
        level=level,
        quality=quality,
        enabled=True,
        is_support=is_support,
    )


def test_project_active_gem_stages() -> None:
    rf = _gem("Righteous Fire", level=21, quality=20)
    # Stage 0 (Early Campaign): low level
    early = _project_gem(rf, 0)
    assert early is not None and early.name == "Righteous Fire"
    assert early.level == 9 and early.quality == 0
    # Stage 5 (High Investment): user's actual
    end = _project_gem(rf, 5)
    assert end is not None and end.level == 21 and end.quality == 20


def test_project_awakened_substitutes_base_name_early_stages() -> None:
    awk = _gem("Awakened Burning Damage Support", level=5, quality=20, is_support=True)
    stage0 = _project_gem(awk, 0)
    assert stage0 is not None
    # Stages 1-3 use the base gem name.
    assert stage0.name == "Burning Damage Support"
    assert stage0.is_support is True


def test_project_awakened_emerges_at_stage_4() -> None:
    awk = _gem("Awakened Burning Damage Support", level=5, quality=20, is_support=True)
    stage4 = _project_gem(awk, 3)  # 0-indexed: stage 4 = idx 3
    assert stage4 is not None
    assert stage4.name == "Awakened Burning Damage Support"
    assert stage4.level == 1  # Awakened starts at lvl 1


def test_project_awakened_high_investment_echoes_user() -> None:
    awk = _gem("Awakened Burning Damage Support", level=5, quality=20, is_support=True)
    stage6 = _project_gem(awk, 5)
    assert stage6 is not None
    assert stage6.name == "Awakened Burning Damage Support"
    assert stage6.level == 5
    assert stage6.quality == 20


def test_project_vaal_strips_in_early_stages() -> None:
    vrf = _gem("Vaal Righteous Fire", level=21, quality=20)
    stage0 = _project_gem(vrf, 0)
    assert stage0 is not None
    # Stages 0-1 use the base gem.
    assert stage0.name == "Righteous Fire"
    stage3 = _project_gem(vrf, 2)  # End Campaign — Vaal becomes available
    assert stage3 is not None
    assert stage3.name == "Vaal Righteous Fire"


def test_project_trigger_gem_keeps_level_across_stages() -> None:
    cwdt = _gem("Cast When Damage Taken Support", level=1, quality=20, is_support=True)
    for stage_idx in range(6):
        proj = _project_gem(cwdt, stage_idx)
        assert proj is not None
        # CWDT mechanical threshold breaks if level changes — keep it
        # locked to whatever the user picked.
        assert proj.level == 1


# ---------------------------------------------------------------------------
# End-to-end: derive_gem_progression on real fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_snapshot() -> object:
    code = (Path(__file__).parent / "fixtures" / "pob_YNQeadFwNBmX.txt").read_text().strip()
    return parse_snapshot(decode_export(code), export_code=code)


def test_derive_gem_progression_on_real_fixture(fixture_snapshot: object) -> None:
    """Spectre Necro fixture should produce 6 stages of non-empty links."""

    prog = derive_gem_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    assert len(prog.stages) == 6
    for stage in prog.stages:
        assert len(stage.links) > 0
        # Every link must have at least one gem.
        for link in stage.links:
            assert len(link.gems) > 0


def test_derive_gem_progression_stage_keys_canonical(fixture_snapshot: object) -> None:
    prog = derive_gem_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    keys = [s.stage_key for s in prog.stages]
    assert keys == [
        "early_campaign",
        "mid_campaign",
        "end_campaign",
        "early_mapping",
        "end_mapping",
        "high_investment",
    ]


def test_derive_gem_progression_high_investment_echoes_user(fixture_snapshot: object) -> None:
    """The high_investment stage matches the user's actual gem levels."""

    snap = fixture_snapshot
    prog = derive_gem_progression(snap)  # type: ignore[arg-type]
    assert prog is not None
    end_stage = prog.stages[-1]
    assert end_stage.stage_key == "high_investment"
    # Collect (name, level, quality) tuples from end stage.
    end_gems = {(g.name, g.level, g.quality) for link in end_stage.links for g in link.gems}
    # Compare with user's enabled gems from the snapshot (max 6 per group
    # to match our encoder clamp).
    user_gems = set()
    for group in snap.skills:  # type: ignore[attr-defined]
        if not group.enabled:
            continue
        for ug in group.gems[:6]:
            if ug.enabled:
                user_gems.add((ug.name, ug.level, ug.quality))
    assert end_gems == user_gems


def test_derive_gem_progression_empty_snapshot_returns_none(
    fixture_snapshot: object,
) -> None:
    """A snapshot with empty skills → None (no progression to derive).

    Uses model_copy on a real snapshot to dodge the long required-field
    list when constructing one from scratch.
    """

    empty = fixture_snapshot.model_copy(update={"skills": ()})  # type: ignore[attr-defined]
    assert derive_gem_progression(empty) is None
