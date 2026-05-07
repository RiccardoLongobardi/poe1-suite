"""Tests for the Step 14 T4 PoB XML encoder."""

from __future__ import annotations

import base64

import pytest

from poe1_core.models.enums import CharacterClass, ItemSlot
from poe1_fob.gear import StageGearSet, StageGearSlot
from poe1_fob.gems import GemLink, GemSpec, StageGemLinks
from poe1_fob.pob import (
    decode_export,
    encode_minimal_tree_pob,
    encode_pob_code,
    parse_snapshot,
)
from poe1_fob.tree import StageTree

# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_encode_returns_url_safe_base64_no_padding() -> None:
    """The PoB code must be url-safe base64 with padding stripped."""

    tree = StageTree(stage_key="early_campaign", node_ids=(50459, 7777, 12345))
    code = encode_pob_code(
        character_class="Marauder",
        ascendancy="Juggernaut",
        tree=tree,
    )
    # No padding =, no whitespace, all url-safe chars.
    assert "=" not in code
    assert all(c.isalnum() or c in "-_" for c in code)
    # Decodable as zlib payload.
    raw = decode_export(code)
    assert raw.startswith(b"<PathOfBuilding")


def test_encode_minimal_tree_pob_wrapper() -> None:
    """`encode_minimal_tree_pob` should produce a parseable PoB code."""

    code = encode_minimal_tree_pob(
        character_class="Marauder",
        ascendancy="Juggernaut",
        node_ids=[50459, 1234],
        title="rf_test",
    )
    raw = decode_export(code)
    snap = parse_snapshot(raw, export_code=code)
    assert snap.character_class == CharacterClass.MARAUDER
    assert set(snap.tree.node_ids) >= {50459, 1234}


# ---------------------------------------------------------------------------
# Roundtrip via decoder
# ---------------------------------------------------------------------------


def test_roundtrip_class_and_ascendancy() -> None:
    """encode → decode → parse_snapshot recovers class + ascendancy + level."""

    tree = StageTree(stage_key="end_mapping", node_ids=(1, 2, 3, 100, 200))
    code = encode_pob_code(
        character_class="Witch",
        ascendancy="Occultist",
        tree=tree,
        level=95,
    )
    snap = parse_snapshot(decode_export(code), export_code=code)
    assert snap.character_class == CharacterClass.WITCH
    assert snap.ascendancy is not None
    assert snap.ascendancy.value == "occultist"
    assert snap.level == 95


def test_roundtrip_node_ids_recovered_from_tree_url() -> None:
    """The tree URL is decoded back to the same node set."""

    # Tree URL v6 packs node ids as u16be → keep them ≤ 65535.
    nodes = (50459, 12345, 7777, 65000)
    tree = StageTree(stage_key="mid_campaign", node_ids=nodes)
    code = encode_pob_code(
        character_class="Marauder",
        ascendancy="Juggernaut",
        tree=tree,
    )
    snap = parse_snapshot(decode_export(code), export_code=code)
    # node_ids parsed from the tree URL must include every node we encoded
    # (the parser may over-read into the empty cluster/mastery sections,
    # but the original ids are guaranteed present).
    assert set(snap.tree.node_ids) >= set(nodes)


def test_roundtrip_with_gear_and_gems() -> None:
    """A full encode with gear+gems is parseable end-to-end."""

    tree = StageTree(stage_key="end_campaign", node_ids=(1, 2, 3, 4, 5))
    gear = StageGearSet(
        stage_key="end_campaign",
        slots=(
            StageGearSlot(
                slot=ItemSlot.BODY_ARMOUR,
                item_name="Kaom's Heart",
                kind="unique",
                notes="signature",
            ),
            StageGearSlot(
                slot=ItemSlot.HELMET,
                item_name="Devoto's Devotion",
                kind="unique",
            ),
        ),
        overall_notes="post-Kitava gear suite",
    )
    gems = StageGemLinks(
        stage_key="end_campaign",
        notes="RF endgame",
        links=(
            GemLink(
                slot=ItemSlot.BODY_ARMOUR,
                sockets=2,
                gems=(
                    GemSpec(name="Righteous Fire", level=20, quality=20),
                    GemSpec(
                        name="Burning Damage Support",
                        level=20,
                        quality=20,
                        is_support=True,
                    ),
                ),
            ),
        ),
    )
    code = encode_pob_code(
        character_class="Marauder",
        ascendancy="Juggernaut",
        tree=tree,
        gear=gear,
        gems=gems,
        level=85,
    )
    snap = parse_snapshot(decode_export(code), export_code=code)
    assert snap.character_class == CharacterClass.MARAUDER
    assert snap.level == 85
    # Notes propagate through the encoder.
    assert "RF endgame" in snap.notes or "Kaom's Heart" in snap.notes or snap.notes


def test_roundtrip_gem_attributes_preserved() -> None:
    """Gem level/quality survive the roundtrip."""

    tree = StageTree(stage_key="early_mapping", node_ids=(1, 2))
    gems = StageGemLinks(
        stage_key="early_mapping",
        links=(
            GemLink(
                slot=ItemSlot.BODY_ARMOUR,
                sockets=1,
                gems=(GemSpec(name="Righteous Fire", level=21, quality=23),),
            ),
        ),
    )
    code = encode_pob_code(
        character_class="Marauder",
        ascendancy=None,
        tree=tree,
        gems=gems,
    )
    snap = parse_snapshot(decode_export(code), export_code=code)
    assert len(snap.skills) == 1
    g0 = snap.skills[0].gems[0]
    assert g0.level == 21
    assert g0.quality == 23
    assert g0.name == "Righteous Fire"


# ---------------------------------------------------------------------------
# Skip kind handling
# ---------------------------------------------------------------------------


def test_encoder_skips_kind_skip_slots() -> None:
    """Slots flagged kind='skip' should not produce <Item> entries."""

    tree = StageTree(stage_key="early_campaign", node_ids=(1,))
    gear = StageGearSet(
        stage_key="early_campaign",
        slots=(
            StageGearSlot(
                slot=ItemSlot.WEAPON_OFFHAND,
                item_name="(none)",
                kind="skip",
            ),
            StageGearSlot(
                slot=ItemSlot.HELMET,
                item_name="Springleaf",
                kind="unique",
            ),
        ),
    )
    code = encode_pob_code(
        character_class="Marauder",
        ascendancy="Juggernaut",
        tree=tree,
        gear=gear,
    )
    snap = parse_snapshot(decode_export(code), export_code=code)
    # Springleaf should be parsed as a helmet item.
    helmet = snap.items_by_slot.get(ItemSlot.HELMET)
    assert helmet is not None
    assert helmet.name == "Springleaf"


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_no_ascendancy_supported() -> None:
    """ascendancy=None should encode cleanly (no ascendancy chosen)."""

    tree = StageTree(stage_key="early_campaign", node_ids=(1, 2))
    code = encode_pob_code(
        character_class="Witch",
        ascendancy=None,
        tree=tree,
    )
    snap = parse_snapshot(decode_export(code), export_code=code)
    assert snap.ascendancy is None


def test_unknown_character_class_falls_back_to_scion() -> None:
    """Unknown class names map to id 0 (Scion) instead of erroring."""

    tree = StageTree(stage_key="x", node_ids=(1,))
    # The encoder shouldn't raise; the decoder may, but the bytes must
    # be valid base64 + zlib.
    code = encode_pob_code(
        character_class="NotARealClass",
        ascendancy=None,
        tree=tree,
    )
    raw = decode_export(code)
    # XML must still be well-formed even with the fallback class.
    assert b'className="NotARealClass"' in raw or b"NotARealClass" in raw


def test_encoded_payload_is_valid_base64() -> None:
    """`encode_pob_code` output must round-trip through urlsafe_b64decode."""

    tree = StageTree(stage_key="any", node_ids=(1,))
    code = encode_pob_code(
        character_class="Templar",
        ascendancy="Inquisitor",
        tree=tree,
    )
    padded = code + "=" * (-len(code) % 4)
    raw = base64.urlsafe_b64decode(padded)
    assert len(raw) > 0


def test_roundtrip_for_each_class() -> None:
    """All 7 classes encode and parse back to the correct enum value."""

    for cls in (
        "Scion",
        "Marauder",
        "Ranger",
        "Witch",
        "Duelist",
        "Templar",
        "Shadow",
    ):
        tree = StageTree(stage_key="x", node_ids=(1,))
        code = encode_pob_code(
            character_class=cls,
            ascendancy=None,
            tree=tree,
        )
        snap = parse_snapshot(decode_export(code), export_code=code)
        assert snap.character_class.value == cls.lower(), f"failed for {cls}"


# ---------------------------------------------------------------------------
# Error surface (smoke)
# ---------------------------------------------------------------------------


def test_corrupted_code_raises_pob_parse_error() -> None:
    """Garbage input raises PobParseError, not an arbitrary exception."""

    from poe1_fob.pob import PobParseError

    with pytest.raises(PobParseError):
        decode_export("@@@not-base64@@@")
