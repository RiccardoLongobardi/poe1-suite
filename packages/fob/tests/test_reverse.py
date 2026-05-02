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

from poe1_core.models import Item, ItemMod, ItemRarity, ItemSlot, KeyItem
from poe1_fob.planner.stages import EARLY_MAPPING, END_MAPPING, HIGH_INVESTMENT
from poe1_fob.reverse import (
    AwakenedGemDegrader,
    CompositeDegrader,
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


# ---------------------------------------------------------------------------
# PlannerService integration (T2)
# ---------------------------------------------------------------------------


async def test_plan_reverse_requires_degrader() -> None:
    """plan_reverse without degrader raises ValueError, not silently degrading."""

    from poe1_fob.planner import PlannerService

    from .test_planner import FakePricing, _make_build

    fake = FakePricing()
    svc = PlannerService(fake)  # no degrader
    build = _make_build(key_items=[])

    with pytest.raises(ValueError, match="degrader"):
        await svc.plan_reverse(build)


async def test_plan_reverse_appends_ladder_rationale_per_stage() -> None:
    """Reverse mode appends [target] rationale tags into the right stages."""

    from poe1_fob.planner import PlannerService

    from .test_planner import FakePricing, _make_build

    mageblood = KeyItem(
        slot=ItemSlot.BELT,
        item=Item(
            name="Mageblood",
            base_type="Heavy Belt",
            rarity=ItemRarity.UNIQUE,
            slot=ItemSlot.BELT,
        ),
        importance=5,
    )
    build = _make_build(key_items=[mageblood])

    fake = FakePricing()
    svc = PlannerService(fake, degrader=HardcodedDegrader())

    plan = await svc.plan_reverse(build)

    # Mageblood ladder anchors to: early_mapping, end_mapping, high_investment.
    early_camp = plan.stages[0]
    early_map = plan.stages[3]
    end_map = plan.stages[4]
    high_inv = plan.stages[5]

    # No rung in early_campaign for Mageblood ladder → no [Mageblood] tag.
    assert not any("[Mageblood]" in g for g in early_camp.gem_changes)
    # Rungs surface as "[Mageblood] {rationale}" in the right stages.
    assert any("[Mageblood]" in g and "Bottled Faith" in g for g in early_map.gem_changes)
    assert any("[Mageblood]" in g for g in end_map.gem_changes)
    assert any("[Mageblood]" in g and "Mageblood" in g for g in high_inv.gem_changes)


async def test_plan_reverse_preserves_template_gem_changes() -> None:
    """Reverse mode doesn't replace template advice — it appends to it."""

    from poe1_fob.planner import PlannerService

    from .test_planner import FakePricing, _make_build

    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Vortex"})

    fake = FakePricing()
    svc_template = PlannerService(fake)
    svc_reverse = PlannerService(fake, degrader=HardcodedDegrader())

    template_plan = await svc_template.plan(build)
    reverse_plan = await svc_reverse.plan_reverse(build)

    # Vortex template advice should be present in BOTH plans.
    template_early = template_plan.stages[0]
    reverse_early = reverse_plan.stages[0]
    assert any("Cold Snap" in g for g in template_early.gem_changes)
    assert any("Cold Snap" in g for g in reverse_early.gem_changes)
    # With no key_items → no rungs → reverse plan is identical to template.
    assert reverse_early.gem_changes == template_early.gem_changes


def test_degrader_case_insensitive_lookup() -> None:
    """Item name lookup is case-insensitive via casefold."""

    degrader = HardcodedDegrader()
    target = _key_item("MAGEBLOOD", slot=ItemSlot.BELT)

    ladder = degrader.degrade(target)

    # MAGEBLOOD case-folds to mageblood and hits the table.
    assert len(ladder.rungs) == 3
    assert ladder.rungs[-1].item_name == "Mageblood"


# ---------------------------------------------------------------------------
# AwakenedGemDegrader (T3)
# ---------------------------------------------------------------------------


def test_awakened_gem_degrader_returns_three_rungs() -> None:
    """Awakened gem ladder: regular support → level 1 → level 5."""

    degrader = AwakenedGemDegrader()
    target = _key_item("Awakened Empower", slot=ItemSlot.JEWEL)

    ladder = degrader.degrade(target)

    assert ladder.target_name == "Awakened Empower"
    assert len(ladder.rungs) == 3
    assert ladder.stage_keys() == ("mid_campaign", "early_mapping", "high_investment")
    # Mid Campaign rung is the regular support gem.
    assert ladder.rungs[0].item_name == "Empower Support"
    # Endgame is the Awakened level 5.
    assert "level 5" in ladder.rungs[-1].item_name.lower() or "5" in ladder.rungs[-1].item_name
    assert ladder.rungs[-1].budget_div_max is None


def test_awakened_gem_degrader_recognises_compound_names() -> None:
    """Awakened Cast on Critical Strike (multi-word) maps correctly."""

    degrader = AwakenedGemDegrader()
    target = _key_item("Awakened Cast on Critical Strike", slot=ItemSlot.JEWEL)

    ladder = degrader.degrade(target)

    assert len(ladder.rungs) == 3
    assert ladder.rungs[0].item_name == "Cast on Critical Strike Support"


def test_awakened_gem_degrader_falls_back_for_non_awakened() -> None:
    """Non-awakened items fall back to single-rung."""

    degrader = AwakenedGemDegrader()
    target = _key_item("Mageblood", slot=ItemSlot.BELT)  # known unique, not gem

    ladder = degrader.degrade(target)

    # Falls through to _endgame_only_fallback.
    assert len(ladder.rungs) == 1
    assert "niente ladder hardcoded" in ladder.rungs[0].rationale.lower()


# ---------------------------------------------------------------------------
# CompositeDegrader (T3)
# ---------------------------------------------------------------------------


def test_composite_degrader_routes_to_first_match() -> None:
    """Composite tries each degrader; first multi-rung ladder wins."""

    composite = CompositeDegrader(
        [AwakenedGemDegrader(), HardcodedDegrader()],
    )

    # Awakened gem → AwakenedGemDegrader matches.
    awak = _key_item("Awakened Empower", slot=ItemSlot.JEWEL)
    awak_ladder = composite.degrade(awak)
    assert awak_ladder.rungs[0].item_name == "Empower Support"

    # Mageblood → AwakenedGemDegrader misses (single-rung), HardcodedDegrader matches.
    mageblood = _key_item("Mageblood", slot=ItemSlot.BELT)
    mb_ladder = composite.degrade(mageblood)
    assert len(mb_ladder.rungs) == 3
    assert mb_ladder.rungs[-1].item_name == "Mageblood"


def test_composite_degrader_returns_fallback_when_all_miss() -> None:
    """If all degraders fall back, composite returns the last fallback ladder."""

    composite = CompositeDegrader(
        [AwakenedGemDegrader(), HardcodedDegrader()],
    )
    target = _key_item("Some Random Unique Nobody Plays")

    ladder = composite.degrade(target)

    # Both miss → HardcodedDegrader's fallback wins.
    assert len(ladder.rungs) == 1
    assert ladder.rungs[0].stage_key == "high_investment"


def test_composite_degrader_requires_non_empty_list() -> None:
    with pytest.raises(ValueError, match="at least one"):
        CompositeDegrader([])


# ---------------------------------------------------------------------------
# Forbidden Jewel ascendancy-aware ladder (T4)
# ---------------------------------------------------------------------------


def _forbidden_jewel(name: str, allocates: str | None) -> KeyItem:
    """Build a Forbidden Flame/Flesh KeyItem with optional 'Allocates X' mod."""

    mods = []
    if allocates is not None:
        mods.append(ItemMod(text=f"Allocates {allocates}"))
    return KeyItem(
        slot=ItemSlot.JEWEL,
        item=Item(
            name=name,
            base_type="Crimson Jewel",
            rarity=ItemRarity.UNIQUE,
            slot=ItemSlot.JEWEL,
            mods=mods,
        ),
        importance=4,
    )


def test_forbidden_ladder_extracts_notable_from_mods() -> None:
    """Forbidden Flame with 'Allocates Avatar of Fire' surfaces the notable."""

    degrader = HardcodedDegrader()
    target = _forbidden_jewel("Forbidden Flame", allocates="Avatar of Fire")

    ladder = degrader.degrade(target)

    assert len(ladder.rungs) == 2
    end_map = ladder.rungs[0]
    high_inv = ladder.rungs[1]
    # Notable surfaces in both item names and rationale.
    assert "Avatar of Fire" in end_map.item_name
    assert "Avatar of Fire" in end_map.rationale
    assert "Avatar of Fire" in high_inv.item_name
    assert "Avatar of Fire" in high_inv.rationale


def test_forbidden_ladder_falls_back_when_no_allocates_mod() -> None:
    """No 'Allocates X' line → ladder still produces 2 rungs with generic copy."""

    degrader = HardcodedDegrader()
    target = _forbidden_jewel("Forbidden Flesh", allocates=None)

    ladder = degrader.degrade(target)

    assert len(ladder.rungs) == 2
    assert "(any notable)" in ladder.rungs[0].item_name
    # Generic phrasing — no specific notable name in rationale.
    assert "Forbidden Flame + Flesh matched pair" in ladder.rungs[1].rationale
