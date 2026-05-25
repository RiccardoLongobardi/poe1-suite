"""Tests for the vendored unique-item catalogue (Step 58, F1)."""

from __future__ import annotations

from poe1_fob.gear.uniques import (
    get_uniques,
    unique_by_name,
    unique_pob_body,
    uniques_for_slot,
)


def test_catalogue_non_empty_and_well_distributed() -> None:
    uniques = get_uniques()
    assert len(uniques) >= 800
    slots = {u.slot for u in uniques}
    # Every major gear slot is represented.
    for slot in ("helmet", "body_armour", "gloves", "boots", "belt", "amulet", "ring", "weapon"):
        assert slot in slots, f"no uniques for slot {slot}"


def test_known_build_defining_uniques_parse() -> None:
    """The chase uniques that close the ladder gap must parse with their
    build-defining mods intact."""
    rime = unique_by_name("Rime Gaze")
    assert rime is not None
    assert rime.slot == "helmet"
    assert any("Cold Damage over Time Multiplier" in m for m in rime.mods)

    mageblood = unique_by_name("Mageblood")
    assert mageblood is not None and mageblood.slot == "belt"

    kaoms = unique_by_name("Kaom's Heart")
    assert kaoms is not None and kaoms.slot == "body_armour"
    assert any("maximum Life" in m for m in kaoms.mods)


def test_uniques_for_slot_matches_catalogue() -> None:
    helmets = uniques_for_slot("helmet")
    assert helmets
    assert all(u.slot == "helmet" for u in helmets)
    assert unique_by_name("Rime Gaze") in helmets
    # Unknown slot → empty.
    assert uniques_for_slot("nonexistent") == ()


def test_unique_pob_body_is_importable_and_max_rolled() -> None:
    """The PoB item body must be a UNIQUE block with name + base, and rolled
    ranges taken to their max (PoB recognises the unique and applies stats)."""
    mb = unique_by_name("Mageblood")
    assert mb is not None
    body = unique_pob_body(mb)
    lines = body.split("\n")
    assert lines[0] == "Rarity: UNIQUE"
    assert lines[1] == "Mageblood"
    assert lines[2] == mb.base_type
    assert "Implicits:" in body
    # "+(25-35) to Strength" → max "+35 to Strength"; no "(min-max)" survives.
    assert "(25-35)" not in body
    assert "+35 to Strength" in body


def test_unique_fields_are_typed() -> None:
    u = unique_by_name("Mageblood")
    assert u is not None
    assert isinstance(u.drop_level, int)
    assert isinstance(u.mods, tuple)
    assert u.mods  # non-empty modifier list
