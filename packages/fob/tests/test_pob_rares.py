"""Unit tests for rare-item mod cleaning + Trade-API filter extraction."""

from __future__ import annotations

from poe1_core.models.enums import ItemRarity
from poe1_fob.pob import (
    MOD_PATTERNS,
    PobItem,
    clean_mods,
    extract_mods,
    valuable_stat_filters,
)
from poe1_fob.pob.rares import _is_metadata, _strip_annotations


def _rare(
    explicits: tuple[str, ...] = (),
    implicits: tuple[str, ...] = (),
    base_type: str = "Leviathan Gauntlets",
) -> PobItem:
    return PobItem(
        pob_id=1,
        rarity=ItemRarity.RARE,
        name="Test Rare",
        base_type=base_type,
        implicits=implicits,
        explicits=explicits,
        raw_text="(test fixture)",
    )


# ---------------------------------------------------------------------------
# Metadata filtering
# ---------------------------------------------------------------------------


class TestIsMetadata:
    def test_recognises_pob_property_lines(self) -> None:
        assert _is_metadata("Item Level: 85")
        assert _is_metadata("Sockets: B-B-B-R")
        assert _is_metadata("Quality: 20")
        assert _is_metadata("LevelReq: 84")
        assert _is_metadata("Implicits: 2")

    def test_recognises_influence_tags(self) -> None:
        assert _is_metadata("Searing Exarch Item")
        assert _is_metadata("Eater of Worlds Item")
        assert _is_metadata("Shaper Item")
        assert _is_metadata("Synthesised Item")
        assert _is_metadata("Fractured Item")

    def test_recognises_corrupted(self) -> None:
        assert _is_metadata("Corrupted")

    def test_real_mod_lines_are_kept(self) -> None:
        assert not _is_metadata("+122 to maximum Life")
        assert not _is_metadata("21% increased Life Regeneration rate")
        assert not _is_metadata("+48% to Fire Resistance")

    def test_blank_lines_dropped(self) -> None:
        assert _is_metadata("")
        assert _is_metadata("   ")


class TestStripAnnotations:
    def test_strips_crafted_tag(self) -> None:
        assert _strip_annotations("{crafted}+30 to maximum Life") == "+30 to maximum Life"

    def test_strips_fractured_tag(self) -> None:
        assert _strip_annotations("{fractured}+15% to Fire Resistance") == "+15% to Fire Resistance"

    def test_strips_multiple_stacked_tags(self) -> None:
        assert _strip_annotations("{crafted}{prefix}+30 to maximum Life") == "+30 to maximum Life"

    def test_no_op_on_clean_lines(self) -> None:
        assert _strip_annotations("+30 to maximum Life") == "+30 to maximum Life"


class TestCleanMods:
    def test_filters_metadata_keeps_real_mods(self) -> None:
        # The Gale Claw fixture from the live test PoB.
        item = _rare(
            explicits=(
                "Searing Exarch Item",
                "Eater of Worlds Item",
                "Item Level: 85",
                "Quality: 20",
                "Sockets: B-B-B-R",
                "LevelReq: 84",
                "Implicits: 2",
                "20% of Physical Damage Converted to Fire Damage",
                "20% chance to Unnerve Enemies for 4 seconds on Hit",
                "30% of Physical Damage Converted to Fire Damage",
                "42% increased Armour",
                "+122 to maximum Life",
                "21% increased Life Regeneration rate",
                "+48% to Fire Resistance",
                "17% increased Stun and Block Recovery",
                "+15% to Fire and Chaos Resistances",
                "Fractured Item",
            ),
        )
        _, expls = clean_mods(item)
        assert "Item Level: 85" not in expls
        assert "Sockets: B-B-B-R" not in expls
        assert "Searing Exarch Item" not in expls
        assert "Fractured Item" not in expls
        # Real mods survive.
        assert "+122 to maximum Life" in expls
        assert "+48% to Fire Resistance" in expls

    def test_strips_annotations_from_surviving_mods(self) -> None:
        item = _rare(
            explicits=(
                "{crafted}+30 to maximum Life",
                "{fractured}+45% to Fire Resistance",
            ),
        )
        _, expls = clean_mods(item)
        assert "+30 to maximum Life" in expls
        assert "+45% to Fire Resistance" in expls


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


class TestExtractMods:
    def test_extracts_life_value(self) -> None:
        out = extract_mods(["+122 to maximum Life"])
        assert len(out) == 1
        assert out[0].value == 122.0
        assert out[0].stat_id == "explicit.stat_3299347043"

    def test_extracts_resistances(self) -> None:
        out = extract_mods(["+48% to Fire Resistance"])
        assert len(out) == 1
        assert out[0].value == 48.0

    def test_movement_speed(self) -> None:
        out = extract_mods(["35% increased Movement Speed"])
        assert len(out) == 1
        assert out[0].value == 35.0
        assert "Movement Speed" in out[0].label

    def test_socketed_gems(self) -> None:
        out = extract_mods(["+1 to Level of Socketed Gems"])
        assert len(out) == 1
        assert out[0].value == 1.0

    def test_attribute_mods(self) -> None:
        out = extract_mods(["+30 to Strength"])
        assert len(out) == 1
        assert out[0].value == 30.0

    def test_unknown_mods_are_dropped(self) -> None:
        # Made-up mod text → no match.
        out = extract_mods(["This is not a real PoE modifier"])
        assert out == []

    def test_metadata_lines_are_dropped(self) -> None:
        # The pattern matcher doesn't itself filter metadata; that's
        # clean_mods's job. Sanity: passing metadata produces no matches
        # because the regex anchors don't fit.
        out = extract_mods(["Item Level: 85", "Sockets: B-B-B-R"])
        assert out == []

    def test_case_insensitive(self) -> None:
        out = extract_mods(["+122 TO MAXIMUM LIFE"])
        assert len(out) == 1
        assert out[0].value == 122.0


# ---------------------------------------------------------------------------
# Stat filter pipeline
# ---------------------------------------------------------------------------


class TestValuableStatFilters:
    def test_extracts_filters_from_real_rare(self) -> None:
        # Loosely modelled on the Gale Claw rare from the test PoB.
        item = _rare(
            explicits=(
                "Item Level: 85",
                "Sockets: B-B-B-R",
                "+122 to maximum Life",
                "+48% to Fire Resistance",
                "21% increased Life Regeneration rate",  # not in pattern table
                "+15% to Fire and Chaos Resistances",
                "17% increased Stun and Block Recovery",
            ),
        )
        filters = valuable_stat_filters(item)
        # life + fire res + fire-and-chaos res + stun-and-block = 4 filters.
        assert len(filters) >= 3
        stat_ids = {f.stat_id for f in filters}
        assert "explicit.stat_3299347043" in stat_ids  # life
        assert "explicit.stat_3372524247" in stat_ids  # fire res

    def test_floor_ratio_applied(self) -> None:
        item = _rare(explicits=("+100 to maximum Life",))
        filters = valuable_stat_filters(item, floor_ratio=0.8)
        assert len(filters) == 1
        assert filters[0].min == 80.0  # 100 * 0.8

    def test_dedupes_repeated_stat_ids(self) -> None:
        # Hybrid mods can match the same stat_id twice; we keep the first.
        item = _rare(
            explicits=(
                "+50 to maximum Life",
                "+80 to maximum Life",
            ),
        )
        filters = valuable_stat_filters(item)
        assert len([f for f in filters if f.stat_id == "explicit.stat_3299347043"]) == 1

    def test_max_filters_caps_output(self) -> None:
        item = _rare(
            explicits=(
                "+100 to maximum Life",
                "+40% to Fire Resistance",
                "+40% to Cold Resistance",
                "+40% to Lightning Resistance",
                "+15% to Chaos Resistance",
                "+30 to Strength",
                "+30 to Dexterity",
                "+30 to Intelligence",
            ),
        )
        filters = valuable_stat_filters(item, max_filters=4)
        assert len(filters) == 4

    def test_metadata_does_not_leak_into_filters(self) -> None:
        item = _rare(
            explicits=(
                "Item Level: 85",
                "Sockets: B-B-B-R",
                "Searing Exarch Item",
                "+122 to maximum Life",
            ),
        )
        filters = valuable_stat_filters(item)
        assert len(filters) == 1
        assert filters[0].stat_id == "explicit.stat_3299347043"

    def test_clean_item_produces_empty_filters(self) -> None:
        # An item with only mods we don't track → no filters.
        item = _rare(
            explicits=("21% increased Life Regeneration rate",),
        )
        filters = valuable_stat_filters(item)
        assert filters == []


# ---------------------------------------------------------------------------
# Pattern table integrity
# ---------------------------------------------------------------------------


class TestModPatternsTable:
    def test_all_patterns_capture_a_numeric_group(self) -> None:
        # Every pattern must yield a number for the StatFilter min.
        for mp in MOD_PATTERNS:
            assert mp.regex.groups >= 1, f"pattern {mp.label!r} has no capture group"

    def test_no_duplicate_stat_id_for_same_label(self) -> None:
        # We deliberately allow the same stat_id across multiple patterns
        # (e.g. 'Spell Damage' uses the same id as 'Spell Skill Gems' as
        # a placeholder); but the (label, stat_id) pair should be unique
        # so the table stays auditable.
        seen: set[tuple[str, str]] = set()
        for mp in MOD_PATTERNS:
            key = (mp.label, mp.stat_id)
            assert key not in seen, f"duplicate (label, stat_id) entry: {key}"
            seen.add(key)
