"""Tests for the reverse-progression engine skeleton.

This is the Step 13.C T1 entry point. Currently exercises:

* :class:`UpgradeLadder` / :class:`LadderStep` Pydantic models — frozen,
  ordered, ``stage_keys()``/``for_stage()`` lookups.
* :class:`HardcodedDegrader` — table hits for Mageblood / Headhunter /
  Kaom's Heart / Watcher's Eye / Forbidden pair, fallback for unknown
  items, target-aware variant substitution.

No HTTP, no PlannerService integration yet (that's Step 13.C T2).
"""

from __future__ import annotations

import pytest

from poe1_core.models import Item, ItemRarity, ItemSlot, KeyItem
from poe1_fob.planner.stages import EARLY_MAPPING, END_MAPPING, HIGH_INVESTMENT
from poe1_fob.reverse import (
    HardcodedDegrader,
    LadderStep,
    UpgradeLadder,
)


def _key_item(name: str, *, slot: ItemSlot = ItemSlot.BODY_ARMOUR) -> KeyItem:
    return KeyItem(
        slot=slot,
        item=Item(
            name=name,
            base_type="(test)",
            rarity=ItemRarity.UNIQUE,
            slot=slot,
        ),
        importance=3,
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_ladder_step_is_frozen() -> None:
    rung = LadderStep(
        stage_key="early_campaign",
        item_name="Tabula Rasa",
        kind="unique",
        budget_div_max=0.5,
        rationale="early 6L stop-gap",
    )

    with pytest.raises((ValueError, TypeError)):
        rung.item_name = "Modified"


def test_upgrade_ladder_requires_at_least_one_rung() -> None:
    with pytest.raises(ValueError):
        UpgradeLadder(target_name="Mageblood", rungs=())


def test_upgrade_ladder_stage_keys_preserve_order() -> None:
    rungs = (
        LadderStep(
            stage_key="early_campaign",
            item_name="Tabula Rasa",
            kind="unique",
            rationale="early",
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Loreweave",
            kind="unique",
            rationale="mid",
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="Body 6L Mirror-tier",
            kind="rare_craft",
            rationale="endgame",
        ),
    )
    ladder = UpgradeLadder(target_name="Body 6L Mirror-tier", rungs=rungs)

    assert ladder.stage_keys() == ("early_campaign", "end_mapping", "high_investment")
    assert ladder.for_stage(END_MAPPING) is not None
    assert ladder.for_stage(END_MAPPING).item_name == "Loreweave"  # type: ignore[union-attr]
    assert ladder.for_stage(EARLY_MAPPING) is None  # not covered


# ---------------------------------------------------------------------------
# HardcodedDegrader
# ---------------------------------------------------------------------------


def test_degrader_mageblood_returns_three_rungs() -> None:
    """Mageblood ladder: Bottled Faith → flask suite → Mageblood."""

    degrader = HardcodedDegrader()
    target = _key_item("Mageblood", slot=ItemSlot.BELT)

    ladder = degrader.degrade(target)

    assert ladder.target_name == "Mageblood"
    assert len(ladder.rungs) == 3
    assert ladder.stage_keys() == ("early_mapping", "end_mapping", "high_investment")
    # Final rung is the endgame target.
    assert ladder.rungs[-1].item_name == "Mageblood"
    assert ladder.rungs[-1].budget_div_max is None
    # Bottled Faith mid-rung has a soft cap.
    assert ladder.rungs[0].item_name == "Bottled Faith"
    assert ladder.rungs[0].budget_div_max == 50.0


def test_degrader_headhunter_returns_three_rungs() -> None:
    degrader = HardcodedDegrader()
    target = _key_item("Headhunter", slot=ItemSlot.BELT)

    ladder = degrader.degrade(target)

    assert ladder.target_name == "Headhunter"
    assert ladder.stage_keys() == ("early_mapping", "end_mapping", "high_investment")
    assert ladder.rungs[0].kind == "rare_craft"  # Stygian Vise rare
    assert ladder.rungs[1].item_name == "Bisco's Leash"
    assert ladder.rungs[-1].item_name == "Headhunter"


def test_degrader_kaoms_heart_starts_with_tabula_rasa() -> None:
    """Kaom's Heart ladder spans early_campaign → early_mapping (no high investment rung)."""

    degrader = HardcodedDegrader()
    target = _key_item("Kaom's Heart")

    ladder = degrader.degrade(target)

    assert ladder.stage_keys() == ("early_campaign", "mid_campaign", "early_mapping")
    assert ladder.rungs[0].item_name == "Tabula Rasa"
    # The endgame for Kaom's Heart is early_mapping, not high_investment —
    # it's an early-mapping switch, not a megaboss endgame upgrade.
    assert ladder.for_stage(HIGH_INVESTMENT) is None


def test_degrader_watchers_eye_substitutes_target_name() -> None:
    """Watcher's Eye ladder uses the specific variant name in the endgame rung."""

    degrader = HardcodedDegrader()
    target = _key_item("Watcher's Eye", slot=ItemSlot.JEWEL)

    ladder = degrader.degrade(target)

    assert ladder.target_name == "Watcher's Eye"
    # Endgame rung carries the target's own name (so multi-mod variants
    # keep their identity in the plan UI).
    assert ladder.rungs[-1].item_name == "Watcher's Eye"


def test_degrader_forbidden_flame_routes_to_pair_ladder() -> None:
    """Both Forbidden Flame and Forbidden Flesh route to the same pair ladder."""

    degrader = HardcodedDegrader()
    flame = _key_item("Forbidden Flame", slot=ItemSlot.JEWEL)
    flesh = _key_item("Forbidden Flesh", slot=ItemSlot.JEWEL)

    flame_ladder = degrader.degrade(flame)
    flesh_ladder = degrader.degrade(flesh)

    # Same shape (2 rungs, end_mapping → high_investment), different
    # name in the rationale via target substitution.
    assert flame_ladder.stage_keys() == flesh_ladder.stage_keys()
    assert flame_ladder.stage_keys() == ("end_mapping", "high_investment")
    assert "Forbidden Flame" in flame_ladder.rungs[-1].item_name
    assert "Forbidden Flesh" in flesh_ladder.rungs[-1].item_name


def test_degrader_unknown_item_falls_back_to_single_rung() -> None:
    """An item not in the table gets a single-rung 'endgame only' ladder."""

    degrader = HardcodedDegrader()
    target = _key_item("Some Obscure Unique Nobody Plays")

    ladder = degrader.degrade(target)

    assert len(ladder.rungs) == 1
    assert ladder.rungs[0].stage_key == "high_investment"
    assert ladder.rungs[0].item_name == "Some Obscure Unique Nobody Plays"
    assert "niente ladder hardcoded" in ladder.rungs[0].rationale.lower()


def test_degrader_case_insensitive_lookup() -> None:
    """Item name lookup is case-insensitive via casefold."""

    degrader = HardcodedDegrader()
    target = _key_item("MAGEBLOOD", slot=ItemSlot.BELT)

    ladder = degrader.degrade(target)

    # MAGEBLOOD case-folds to mageblood and hits the table.
    assert len(ladder.rungs) == 3
    assert ladder.rungs[-1].item_name == "Mageblood"
