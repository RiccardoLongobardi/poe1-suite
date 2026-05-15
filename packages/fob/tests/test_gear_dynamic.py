"""Step 17 — tests for dynamic gear progression derivation."""

from __future__ import annotations

from pathlib import Path

import pytest

from poe1_core.models.enums import ItemRarity, ItemSlot
from poe1_fob.gear.base_items import (
    base_for_name,
    bases_for_slot,
    get_base_catalogue,
)
from poe1_fob.gear.dynamic import (
    Tier,
    _fits_stage_budget,
    _is_cluster_jewel,
    classify_item,
    derive_gear_progression,
)
from poe1_fob.pob import decode_export, parse_snapshot
from poe1_fob.pob.models import PobItem

# ---------------------------------------------------------------------------
# base_items loader
# ---------------------------------------------------------------------------


def test_base_catalogue_loads_with_expected_shape() -> None:
    cat = get_base_catalogue()
    # repoe-fork ships ~1030 gear bases after our slim+filter.
    assert len(cat) > 900
    assert len(cat) < 1200


def test_base_lookup_by_name_returns_canonical_slot() -> None:
    sv = base_for_name("Stygian Vise")
    assert sv is not None
    assert sv.item_class == "Belt"
    assert sv.slot == ItemSlot.BELT

    ap = base_for_name("Astral Plate")
    assert ap is not None
    assert ap.item_class == "Body Armour"
    assert ap.slot == ItemSlot.BODY_ARMOUR


def test_base_lookup_unknown_returns_none() -> None:
    assert base_for_name("Not A Real Base Type") is None


def test_bases_for_slot_returns_only_matching_slot() -> None:
    bodies = bases_for_slot(ItemSlot.BODY_ARMOUR)
    assert len(bodies) > 50  # PoE has plenty of body armours
    for b in bodies:
        assert b.slot == ItemSlot.BODY_ARMOUR
    # Spot-check famous bases.
    names = {b.name for b in bodies}
    assert "Astral Plate" in names
    assert "Vaal Regalia" in names


# ---------------------------------------------------------------------------
# Tier classifier
# ---------------------------------------------------------------------------


def _item(
    *,
    name: str | None,
    base_type: str,
    rarity: ItemRarity,
    pob_id: int = 1,
) -> PobItem:
    """Minimal PobItem builder for tests."""

    return PobItem(
        pob_id=pob_id,
        rarity=rarity,
        name=name,
        base_type=base_type,
        raw_text="Rarity: ...\n",
    )


def test_classify_unique_with_price_dict_uses_threshold() -> None:
    """Known-name + price > 100 div → 'mageblood' tier."""

    item = _item(name="Mageblood", base_type="Heavy Belt", rarity=ItemRarity.UNIQUE)
    assert classify_item(item, prices={"Mageblood": 250.0}) == "mageblood"
    assert classify_item(item, prices={"Mageblood": 50.0}) == "high"
    assert classify_item(item, prices={"Mageblood": 10.0}) == "mid"
    assert classify_item(item, prices={"Mageblood": 2.0}) == "cheap"
    assert classify_item(item, prices={"Mageblood": 0.1}) == "leveling"


def test_classify_unique_falls_back_to_name_heuristic_without_prices() -> None:
    """When prices is None, known-name lists drive the tier."""

    mb = _item(name="Mageblood", base_type="Heavy Belt", rarity=ItemRarity.UNIQUE)
    assert classify_item(mb) == "mageblood"
    kh = _item(name="Kaom's Heart", base_type="Glorious Plate", rarity=ItemRarity.UNIQUE)
    assert classify_item(kh) == "mid"
    goldrim = _item(name="Goldrim", base_type="Leather Cap", rarity=ItemRarity.UNIQUE)
    assert classify_item(goldrim) == "leveling"


def test_classify_unknown_unique_defaults_to_mid() -> None:
    """Conservative default for unknown unique names."""

    weird = _item(name="Some Obscure Unique", base_type="Bow", rarity=ItemRarity.UNIQUE)
    assert classify_item(weird) == "mid"


def test_classify_cluster_jewel_overrides_rarity() -> None:
    """Cluster jewels classify as 'cluster' regardless of rarity."""

    cj = _item(
        name="Some Mod Combination",
        base_type="Large Cluster Jewel",
        rarity=ItemRarity.RARE,
    )
    assert classify_item(cj) == "cluster"


def test_classify_rare_craft() -> None:
    """Non-unique non-cluster items default to 'rare_craft'."""

    rare = _item(name="Bramble Halo", base_type="Hubris Circlet", rarity=ItemRarity.RARE)
    assert classify_item(rare) == "rare_craft"


def test_is_cluster_jewel_recognises_all_sizes() -> None:
    """Large / Medium / Small Cluster Jewel all detected."""

    for size in ("Large", "Medium", "Small"):
        item = _item(name="Mod Combo", base_type=f"{size} Cluster Jewel", rarity=ItemRarity.RARE)
        assert _is_cluster_jewel(item)


# ---------------------------------------------------------------------------
# Stage budget logic
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tier,stage_key,expected",
    [
        # leveling fits everywhere
        ("leveling", "early_campaign", True),
        ("leveling", "high_investment", True),
        # cheap fits stage 2 onward
        ("cheap", "early_campaign", False),
        ("cheap", "mid_campaign", True),
        # mid fits stage 3+
        ("mid", "mid_campaign", False),
        ("mid", "end_campaign", True),
        # high fits stage 4+
        ("high", "end_campaign", False),
        ("high", "early_mapping", True),
        # mageblood / mirror only stage 5+
        ("mageblood", "early_mapping", False),
        ("mageblood", "end_mapping", True),
        # cluster goes into stage 5+ too (it's endgame)
        ("cluster", "end_campaign", False),
        ("cluster", "high_investment", True),
    ],
)
def test_fits_stage_budget_thresholds(tier: Tier, stage_key: str, expected: bool) -> None:
    assert _fits_stage_budget(tier, stage_key) is expected


# ---------------------------------------------------------------------------
# End-to-end derive_gear_progression on real fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_snapshot() -> object:
    code = (Path(__file__).parent / "fixtures" / "pob_YNQeadFwNBmX.txt").read_text().strip()
    return parse_snapshot(decode_export(code), export_code=code)


def test_derive_gear_progression_six_stages(fixture_snapshot: object) -> None:
    prog = derive_gear_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    assert len(prog.stages) == 6
    assert [s.stage_key for s in prog.stages] == [
        "early_campaign",
        "mid_campaign",
        "end_campaign",
        "early_mapping",
        "end_mapping",
        "high_investment",
    ]


def test_derive_gear_progression_high_investment_keeps_user_items(
    fixture_snapshot: object,
) -> None:
    """High investment stage must contain every slot the user has filled."""

    snap = fixture_snapshot
    prog = derive_gear_progression(snap)  # type: ignore[arg-type]
    assert prog is not None
    final = prog.stages[-1]
    final_slots = {sl.slot for sl in final.slots}
    user_slots = set(snap.items_by_slot.keys())  # type: ignore[attr-defined]
    # High investment must cover every slot the user has.
    assert final_slots >= user_slots


def test_derive_gear_progression_early_uses_leveling_placeholders(
    fixture_snapshot: object,
) -> None:
    """Stage 1 should substitute the user's mid+ uniques with leveling uniques."""

    prog = derive_gear_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    early = prog.stages[0]
    # At least one slot should land on a known leveling unique.
    leveling_names = {
        "Goldrim",
        "Wanderlust",
        "Tabula Rasa",
        "Lochtonial Caress",
        "Karui Ward",
        "Meginord's Girdle",
        "Springleaf",
        "Brightbeak",
        "Praxis",
    }
    early_names = {sl.item_name for sl in early.slots}
    assert early_names & leveling_names, (
        f"Stage 1 has no leveling unique substitutions: {early_names}"
    )


def test_derive_gear_progression_empty_snapshot_returns_none(
    fixture_snapshot: object,
) -> None:
    """A snapshot with no equipped items → None."""

    empty = fixture_snapshot.model_copy(update={"items_by_slot": {}})  # type: ignore[attr-defined]
    assert derive_gear_progression(empty) is None


def test_derive_gear_progression_stages_grow_or_stay(fixture_snapshot: object) -> None:
    """Later stages should never have fewer slots than earlier ones.

    Gear isn't strictly monotone the way the tree is (an item gets
    replaced, not added), but the stage's slot count should never
    shrink — every slot the user has filled must appear at every
    stage, either as the user's item or as a placeholder.
    """

    prog = derive_gear_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    prev = 0
    for stage in prog.stages:
        assert len(stage.slots) >= prev
        prev = len(stage.slots)
