"""Tests for the PoB XML parser.

These tests operate on the real fixture at
``packages/fob/tests/fixtures/pob_YNQeadFwNBmX.txt`` — a level-100
Chieftain Marauder Raise Spectre build — plus a handful of synthetic
inputs to cover error paths. We deliberately avoid mocking the XML:
the whole point of this module is to handle the exact bytes PoB emits.
"""

from __future__ import annotations

import base64
import zlib
from pathlib import Path

import pytest

from poe1_core.models.enums import Ascendancy, CharacterClass, ItemRarity, ItemSlot
from poe1_fob.pob import PobParseError, decode_export, parse_snapshot
from poe1_fob.pob.parser import (
    _coerce_ascendancy,
    _coerce_class,
    _coerce_rarity,
    _decode_tree_url,
    _parse_item_text,
    _slot_for,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REAL_POB = (FIXTURE_DIR / "pob_YNQeadFwNBmX.txt").read_text().strip()


# ---------------------------------------------------------------------------
# decode_export
# ---------------------------------------------------------------------------


def test_decode_export_real_fixture() -> None:
    xml = decode_export(REAL_POB)
    assert xml.startswith(b"<?xml") or xml.startswith(b"<PathOfBuilding")
    assert b"Raise Spectre" in xml


def test_decode_export_invalid_base64() -> None:
    with pytest.raises(PobParseError):
        decode_export("not base64 at all $$$ ###")


def test_decode_export_invalid_zlib() -> None:
    # Valid base64, invalid zlib payload.
    garbage = base64.urlsafe_b64encode(b"not zlib compressed").decode()
    with pytest.raises(PobParseError):
        decode_export(garbage)


# ---------------------------------------------------------------------------
# Enum coercers
# ---------------------------------------------------------------------------


def test_coerce_class_known() -> None:
    assert _coerce_class("Marauder") is CharacterClass.MARAUDER
    assert _coerce_class("witch") is CharacterClass.WITCH


def test_coerce_class_missing_raises() -> None:
    with pytest.raises(PobParseError):
        _coerce_class(None)


def test_coerce_class_unknown_raises() -> None:
    with pytest.raises(PobParseError):
        _coerce_class("Alchemist")


def test_coerce_ascendancy_none_returns_none() -> None:
    assert _coerce_ascendancy(None) is None
    assert _coerce_ascendancy("None") is None
    assert _coerce_ascendancy("") is None


def test_coerce_ascendancy_known() -> None:
    assert _coerce_ascendancy("Chieftain") is Ascendancy.CHIEFTAIN


def test_coerce_ascendancy_unknown_returns_none() -> None:
    # Unknown ascendancy names are soft-failed so new leagues don't break us.
    assert _coerce_ascendancy("Warden") is None


def test_coerce_rarity_relic_folds_to_unique() -> None:
    assert _coerce_rarity("RELIC") is ItemRarity.UNIQUE


def test_coerce_rarity_unknown_raises() -> None:
    with pytest.raises(PobParseError):
        _coerce_rarity("LEGENDARY")


# ---------------------------------------------------------------------------
# Item text parsing
# ---------------------------------------------------------------------------


MAGEBLOOD_TEXT = """\
Rarity: UNIQUE
Mageblood
Heavy Belt
Unique ID: c0ffee
Item Level: 86
LevelReq: 78
Implicits: 1
+25 to Strength
{crafted}Magic Utility Flasks cannot be removed from Inventory
You can have an additional Magic Utility Flask
Corrupted
"""


def test_parse_item_text_unique_with_crafted_mod() -> None:
    item = _parse_item_text(1, MAGEBLOOD_TEXT)
    assert item.rarity is ItemRarity.UNIQUE
    assert item.name == "Mageblood"
    assert item.base_type == "Heavy Belt"
    assert item.item_level == 86
    assert item.level_req == 78
    assert item.implicits == ("+25 to Strength",)
    # The {crafted} annotation must be stripped from the explicit text.
    assert item.explicits[0] == "Magic Utility Flasks cannot be removed from Inventory"
    assert len(item.explicits) == 2
    assert item.corrupted is True


RARE_RING_TEXT = """\
Rarity: RARE
Death Beam
Sapphire Ring
Item Level: 84
LevelReq: 63
Sockets: R
Implicits: 1
+(17-23)% to Cold Resistance
+85 to maximum Life
+30% to Lightning Resistance
"""


def test_parse_item_text_rare_with_sockets() -> None:
    item = _parse_item_text(7, RARE_RING_TEXT)
    assert item.rarity is ItemRarity.RARE
    assert item.name == "Death Beam"
    assert item.base_type == "Sapphire Ring"
    assert item.sockets == "R"
    assert len(item.implicits) == 1
    assert len(item.explicits) == 2
    assert not item.corrupted


def test_parse_item_text_empty_raises() -> None:
    with pytest.raises(PobParseError):
        _parse_item_text(1, "")


def test_parse_item_text_missing_rarity_raises() -> None:
    with pytest.raises(PobParseError):
        _parse_item_text(1, "Some Random Item\nBase Type\n")


# ---------------------------------------------------------------------------
# Slot mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Helmet", ItemSlot.HELMET),
        ("Body Armour", ItemSlot.BODY_ARMOUR),
        ("Ring 1", ItemSlot.RING),
        ("Ring 2", ItemSlot.RING),
        ("Weapon 1", ItemSlot.WEAPON_MAIN),
        ("Weapon 2", ItemSlot.WEAPON_OFFHAND),
        ("Flask 3", ItemSlot.FLASK),
    ],
)
def test_slot_mapping_main_set(raw: str, expected: ItemSlot) -> None:
    assert _slot_for(raw, use_swap_set=False) is expected


def test_slot_ignores_swap_when_main_set_active() -> None:
    assert _slot_for("Weapon 1 Swap", use_swap_set=False) is None


def test_slot_reads_swap_when_swap_active() -> None:
    assert _slot_for("Weapon 1 Swap", use_swap_set=True) is ItemSlot.WEAPON_MAIN


def test_slot_ignores_abyssal_socket() -> None:
    assert _slot_for("Helmet Abyssal Socket 1", use_swap_set=False) is None


# ---------------------------------------------------------------------------
# Tree URL decoder
# ---------------------------------------------------------------------------


def test_decode_tree_url_real_fixture() -> None:
    """Real-world URL produces a plausible class + non-empty node list."""

    snap = parse_snapshot(decode_export(REAL_POB), export_code=REAL_POB, origin_url=None)
    assert snap.tree.url.startswith("https://")
    # class_id 1 in the tree payload is Marauder (matches the Build element).
    assert snap.tree.class_id == 1
    # A level-100 character has >90 allocated passive points plus clusters.
    assert len(snap.tree.node_ids) > 90
    # Bounds check: PoE node ids fit in uint16.
    assert all(0 <= n <= 0xFFFF for n in snap.tree.node_ids)


def test_decode_tree_url_too_short_raises() -> None:
    payload = base64.urlsafe_b64encode(b"abc").decode().rstrip("=")
    with pytest.raises(PobParseError):
        _decode_tree_url(f"https://www.pathofexile.com/passive-skill-tree/{payload}")


def test_decode_tree_url_bad_base64_raises() -> None:
    with pytest.raises(PobParseError):
        _decode_tree_url("https://www.pathofexile.com/passive-skill-tree/$$$")


# ---------------------------------------------------------------------------
# parse_snapshot end-to-end
# ---------------------------------------------------------------------------


def test_parse_snapshot_real_fixture_header() -> None:
    snap = parse_snapshot(
        decode_export(REAL_POB), export_code=REAL_POB, origin_url="https://pobb.in/X"
    )
    assert snap.character_class is CharacterClass.MARAUDER
    assert snap.ascendancy is Ascendancy.CHIEFTAIN
    assert snap.level == 100
    assert snap.export_code == REAL_POB
    assert snap.origin_url == "https://pobb.in/X"
    assert snap.target_version  # non-empty


def test_parse_snapshot_real_fixture_skills() -> None:
    snap = parse_snapshot(decode_export(REAL_POB), export_code=REAL_POB)
    # The build is Raise Spectre; it must appear as an active (non-support)
    # gem in at least one skill group.
    all_gem_names = {g.name for grp in snap.skills for g in grp.gems}
    assert "Raise Spectre" in all_gem_names
    assert snap.main_skill_group_index >= 1
    # The main skill group contains at least one active gem.
    main = next(g for g in snap.skills if g.socket_group == snap.main_skill_group_index)
    assert any(gem.enabled and not gem.is_support for gem in main.gems)


def test_parse_snapshot_real_fixture_items() -> None:
    snap = parse_snapshot(decode_export(REAL_POB), export_code=REAL_POB)
    # Every equipped slot must map to a canonical ItemSlot enum.
    for slot, item in snap.items_by_slot.items():
        assert isinstance(slot, ItemSlot)
        assert item.base_type
    # Weapon and body armour are always equipped on a mapping build.
    assert ItemSlot.WEAPON_MAIN in snap.items_by_slot
    assert ItemSlot.BODY_ARMOUR in snap.items_by_slot
    # Flasks: there are 5 flask slots, all filled in this fixture.
    assert len(snap.flasks) == 5


def test_parse_snapshot_real_fixture_stats() -> None:
    snap = parse_snapshot(decode_export(REAL_POB), export_code=REAL_POB)
    # Stats must include DPS and life numbers.
    assert "Life" in snap.stats
    assert snap.stats["Life"] > 0
    # At least one of the DPS flavours has a meaningful value.
    dps = (
        snap.stats.get("FullDPS", 0.0)
        + snap.stats.get("CombinedDPS", 0.0)
        + snap.stats.get("TotalDPS", 0.0)
    )
    assert dps > 1_000_000.0


def test_parse_snapshot_rejects_non_pob_xml() -> None:
    with pytest.raises(PobParseError):
        parse_snapshot(b"<Root/>", export_code="x")


def test_parse_snapshot_rejects_malformed_xml() -> None:
    with pytest.raises(PobParseError):
        parse_snapshot(b"<notxml", export_code="x")


def test_parse_snapshot_rejects_missing_build() -> None:
    with pytest.raises(PobParseError):
        parse_snapshot(b"<PathOfBuilding/>", export_code="x")


def test_decode_export_roundtrip_on_synthetic_xml() -> None:
    """Sanity: any base64(zlib(xml)) is decodable."""
    xml = b"<PathOfBuilding/>"
    code = base64.urlsafe_b64encode(zlib.compress(xml)).decode()
    assert decode_export(code) == xml
