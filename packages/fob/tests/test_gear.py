"""Tests for the Step 14 T2 gear progression module."""

from __future__ import annotations

import pytest

from poe1_core.models.enums import ItemSlot
from poe1_fob.gear import (
    GearProgression,
    StageGearSet,
    StageGearSlot,
    gear_progression_for,
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_stage_gear_slot_basic() -> None:
    s = StageGearSlot(
        slot=ItemSlot.HELMET,
        item_name="Goldrim",
        kind="unique",
        notes="cheap helmet",
    )
    assert s.slot is ItemSlot.HELMET
    assert s.kind == "unique"


def test_stage_gear_slot_kind_validates() -> None:
    """Pydantic should reject an invalid GearKind literal."""

    with pytest.raises(ValueError):
        StageGearSlot(
            slot=ItemSlot.HELMET,
            item_name="x",
            kind="garbage",  # type: ignore[arg-type]
        )


def test_stage_gear_set_slot_lookup() -> None:
    s = StageGearSet(
        stage_key="early_campaign",
        slots=(
            StageGearSlot(slot=ItemSlot.HELMET, item_name="Goldrim", kind="unique"),
            StageGearSlot(slot=ItemSlot.BOOTS, item_name="Wanderlust", kind="unique"),
        ),
    )
    assert s.slot(ItemSlot.HELMET) is not None
    assert s.slot(ItemSlot.HELMET).item_name == "Goldrim"  # type: ignore[union-attr]
    assert s.slot(ItemSlot.BODY_ARMOUR) is None


def test_gear_progression_for_stage_lookup() -> None:
    p = GearProgression(
        target_name="rf_pohx",
        stages=(
            StageGearSet(
                stage_key="early_campaign",
                slots=(StageGearSlot(slot=ItemSlot.HELMET, item_name="Goldrim", kind="unique"),),
            ),
        ),
    )
    assert p.for_stage("early_campaign") is not None
    assert p.for_stage("nonexistent") is None


def test_gear_progression_rejects_duplicate_stage_keys() -> None:
    with pytest.raises(ValueError, match="duplicate stage_key"):
        GearProgression(
            target_name="bad",
            stages=(
                StageGearSet(
                    stage_key="early_campaign",
                    slots=(StageGearSlot(slot=ItemSlot.HELMET, item_name="x", kind="unique"),),
                ),
                StageGearSet(
                    stage_key="early_campaign",
                    slots=(StageGearSlot(slot=ItemSlot.HELMET, item_name="y", kind="unique"),),
                ),
            ),
        )


# ---------------------------------------------------------------------------
# RF Pohx registry hit
# ---------------------------------------------------------------------------


def test_gear_progression_for_rf_pohx_returns_six_stages() -> None:
    """RF Pohx ships a 6-stage gear progression covering every stage."""

    p = gear_progression_for("rf_pohx")
    assert p is not None
    assert p.target_name == "rf_pohx"
    assert len(p.stages) == 6
    # Each stage covers ≥ 5 slots (we want a meaningful spec, not stubs).
    for stage in p.stages:
        assert len(stage.slots) >= 5, f"{stage.stage_key} only has {len(stage.slots)} slots"


def test_gear_progression_for_unknown_returns_none() -> None:
    assert gear_progression_for("nonexistent_template") is None


def test_rf_pohx_high_investment_includes_mageblood() -> None:
    """Sanity check that the endgame stage names Mageblood in the belt slot."""

    p = gear_progression_for("rf_pohx")
    assert p is not None
    high_inv = p.for_stage("high_investment")
    assert high_inv is not None
    belt = high_inv.slot(ItemSlot.BELT)
    assert belt is not None
    assert "Mageblood" in belt.item_name


def test_rf_pohx_early_campaign_includes_tabula_rasa() -> None:
    p = gear_progression_for("rf_pohx")
    assert p is not None
    early = p.for_stage("early_campaign")
    assert early is not None
    body = early.slot(ItemSlot.BODY_ARMOUR)
    assert body is not None
    assert "Tabula" in body.item_name
