"""Unit tests for the FOB Planner.

Fully offline. Pricing is faked via :class:`FakePricing` — a tiny
adapter satisfying :class:`PricingPort` that returns canned
:class:`PriceQuote` objects for known item names. No HTTP calls, no
poe.ninja, no FastAPI client.

The fixture builds match what :func:`snapshot_to_build` would produce:
:class:`KeyItem` only contains uniques, with ``importance=3`` by
default.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from poe1_core.models import (
    Build,
    BuildSourceType,
    CharacterClass,
    Confidence,
    ContentFocus,
    Currency,
    DamageProfile,
    DefenseProfile,
    Item,
    ItemRarity,
    ItemSlot,
    KeyItem,
    Playstyle,
    PriceSource,
)
from poe1_core.models.enums import TargetGoal
from poe1_fob.planner.pricing import (
    chaos_to_divine_rate,
    price_range_to_divines,
    quote_to_range,
    quote_unique_range,
)
from poe1_fob.planner.service import PlannerService
from poe1_fob.planner.stages import (
    END_GAME,
    LEAGUE_START,
    MID_GAME,
    stage_budget,
    stage_for_amount,
)
from poe1_pricing import ItemCategory, PriceQuote

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _make_quote(
    name: str,
    chaos: float,
    *,
    category: ItemCategory = ItemCategory.UNIQUE_ARMOUR,
    sample_count: int | None = 30,
    low_confidence: bool = False,
) -> PriceQuote:
    return PriceQuote(
        name=name,
        category=category,
        chaos_value=chaos,
        sample_count=sample_count,
        low_confidence=low_confidence,
        league="Mirage",
        fetched_at=datetime.now(UTC),
    )


class FakePricing:
    """Minimal :class:`PricingPort` for tests.

    Maps ``"Divine Orb"`` to a fixed chaos rate so every test sees the
    same conversion. ``unique_quotes`` lookups are case-insensitive.
    """

    def __init__(
        self,
        *,
        chaos_per_divine: float = 200.0,
        unique_quotes: dict[str, float] | None = None,
    ) -> None:
        self._divine_chaos = chaos_per_divine
        self._uniques: dict[str, float] = {
            (k or "").casefold(): v for k, v in (unique_quotes or {}).items()
        }

    async def quote_currency(self, name: str) -> PriceQuote | None:
        if name == "Divine Orb":
            return _make_quote(
                "Divine Orb",
                self._divine_chaos,
                category=ItemCategory.CURRENCY,
            )
        return None

    async def quote_unique(self, name: str) -> PriceQuote | None:
        chaos = self._uniques.get(name.casefold())
        if chaos is None:
            return None
        return _make_quote(name, chaos)


# ---------------------------------------------------------------------------
# Build fixtures
# ---------------------------------------------------------------------------


def _key_item(
    name: str,
    *,
    base_type: str = "Cloak Of Whatever",
    slot: ItemSlot = ItemSlot.BODY_ARMOUR,
    importance: int = 3,
) -> KeyItem:
    return KeyItem(
        slot=slot,
        item=Item(
            name=name,
            base_type=base_type,
            rarity=ItemRarity.UNIQUE,
            slot=slot,
        ),
        importance=importance,
    )


def _make_build(*, key_items: list[KeyItem]) -> Build:
    return Build(
        source_id="pob::test123",
        source_type=BuildSourceType.POB,
        character_class=CharacterClass.WITCH,
        ascendancy=None,
        main_skill="Vortex",
        support_gems=["Bonechill", "Hypothermia"],
        damage_profile=DamageProfile.COLD_DOT,
        playstyle=Playstyle.SELF_CAST,
        content_tags=[ContentFocus.MAPPING],
        defense_profile=DefenseProfile.LIFE,
        key_items=key_items,
    )


# ---------------------------------------------------------------------------
# pricing.py tests
# ---------------------------------------------------------------------------


async def test_chaos_to_divine_rate_uses_quote() -> None:
    fake = FakePricing(chaos_per_divine=180.0)
    assert await chaos_to_divine_rate(fake) == 180.0


async def test_chaos_to_divine_rate_falls_back_when_missing() -> None:
    class NoCurrency(FakePricing):
        async def quote_currency(self, name: str) -> PriceQuote | None:
            return None

    fake = NoCurrency()
    # Default heuristic fallback; not the FakePricing default.
    assert await chaos_to_divine_rate(fake) == 200.0


def test_quote_to_range_under_one_div_stays_in_chaos() -> None:
    quote = _make_quote("Tabula Rasa", 30.0, sample_count=80)
    rng = quote_to_range(quote, chaos_per_divine=200.0)
    assert rng.currency is Currency.CHAOS
    assert rng.min.amount < 30.0 < rng.max.amount
    assert rng.confidence is Confidence.HIGH
    assert rng.source is PriceSource.POE_NINJA


def test_quote_to_range_over_one_div_uses_divines() -> None:
    quote = _make_quote("Mageblood", 60_000.0, sample_count=100)  # 300 div @200
    rng = quote_to_range(quote, chaos_per_divine=200.0)
    assert rng.currency is Currency.DIVINE
    # Mid-point should be ~300 div.
    assert 250.0 < rng.midpoint < 350.0


def test_quote_to_range_low_confidence_flag() -> None:
    quote = _make_quote("Obscure Unique", 100.0, sample_count=2, low_confidence=True)
    rng = quote_to_range(quote, chaos_per_divine=200.0)
    assert rng.confidence is Confidence.LOW


async def test_quote_unique_range_returns_none_when_unknown() -> None:
    fake = FakePricing(unique_quotes={"Mageblood": 50_000.0})
    out = await quote_unique_range(fake, "Headhunter", chaos_per_divine=200.0)
    assert out is None


def test_price_range_to_divines_handles_currencies() -> None:
    quote = _make_quote("Mageblood", 60_000.0)
    rng_div = quote_to_range(quote, chaos_per_divine=200.0)
    div = price_range_to_divines(rng_div, 200.0)
    assert div is not None
    assert 250.0 < div < 350.0

    quote_chaos = _make_quote("Tabula Rasa", 30.0)
    rng_chaos = quote_to_range(quote_chaos, chaos_per_divine=200.0)
    div_from_chaos = price_range_to_divines(rng_chaos, 200.0)
    assert div_from_chaos is not None
    assert 0.1 < div_from_chaos < 0.2  # 30 chaos / 200 ~= 0.15 div

    assert price_range_to_divines(None, 200.0) is None


# ---------------------------------------------------------------------------
# stages.py tests
# ---------------------------------------------------------------------------


def test_stage_for_amount_buckets_correctly() -> None:
    assert stage_for_amount(None) is END_GAME
    assert stage_for_amount(0.5) is LEAGUE_START
    assert stage_for_amount(1.0) is LEAGUE_START  # boundary -> cheaper bucket wins
    assert stage_for_amount(5.0) is MID_GAME
    assert stage_for_amount(25.0) is MID_GAME
    assert stage_for_amount(50.0) is END_GAME


def test_stage_default_budget_when_empty() -> None:
    rng = stage_budget([], LEAGUE_START, chaos_per_divine=200.0)
    assert rng.min.amount == 0.0
    assert rng.max.amount == 1.0
    assert rng.source is PriceSource.HEURISTIC
    assert rng.confidence is Confidence.LOW


def test_stage_budget_clamps_to_spec_floor_and_ceiling() -> None:
    """Stage with one cheap item still covers the spec range, so monotone holds."""

    from poe1_core.models import CoreItem, PriceRange, PriceValue

    cheap = CoreItem(
        name="Goldrim",
        slot=ItemSlot.HELMET,
        rarity=ItemRarity.UNIQUE,
        price_estimate=PriceRange(
            min=PriceValue(amount=2.0, currency=Currency.CHAOS),
            max=PriceValue(amount=4.0, currency=Currency.CHAOS),
            source=PriceSource.POE_NINJA,
        ),
        buy_priority=1,
    )
    rng = stage_budget([cheap], MID_GAME, chaos_per_divine=200.0)
    # Items sum to ~0.015 div but Mid spec ceiling is 25 -> clamp pushes
    # the band to at least [1, 25].
    assert rng.min.amount >= MID_GAME.floor_div
    assert rng.max.amount >= MID_GAME.ceiling_div


# ---------------------------------------------------------------------------
# Service tests — full plan happy paths
# ---------------------------------------------------------------------------


async def test_plan_with_no_key_items_returns_default_stages() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])

    plan = await svc.plan(build)

    assert len(plan.stages) == 3
    labels = [s.label for s in plan.stages]
    assert labels == ["League start", "Mid-game", "End-game"]
    # Every stage falls back to its HEURISTIC default.
    for s in plan.stages:
        assert s.budget_range.source is PriceSource.HEURISTIC
        assert not s.core_items


async def test_plan_buckets_items_by_divine_cost() -> None:
    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={
            "Tabula Rasa": 30.0,  # 0.15 div  -> league start
            "Inpulsa's Broken Heart": 1500.0,  # 7.5 div    -> mid-game
            "Mageblood": 60_000.0,  # 300 div    -> end-game
        },
    )
    svc = PlannerService(fake)
    build = _make_build(
        key_items=[
            _key_item("Tabula Rasa", slot=ItemSlot.BODY_ARMOUR, importance=2),
            _key_item("Inpulsa's Broken Heart", slot=ItemSlot.BODY_ARMOUR, importance=4),
            _key_item("Mageblood", slot=ItemSlot.BELT, importance=5),
        ],
    )

    plan = await svc.plan(build)
    [ls, mid, end] = plan.stages

    assert {ci.name for ci in ls.core_items} == {"Tabula Rasa"}
    assert {ci.name for ci in mid.core_items} == {"Inpulsa's Broken Heart"}
    assert {ci.name for ci in end.core_items} == {"Mageblood"}


async def test_plan_respects_buy_priority_within_stage() -> None:
    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={
            "Atziri's Promise": 4.0,  # 0.02 div
            "Goldrim": 2.0,  # 0.01 div
            "Wanderlust": 1.0,
        },
    )
    svc = PlannerService(fake)
    build = _make_build(
        key_items=[
            _key_item("Atziri's Promise", slot=ItemSlot.AMULET, importance=2),
            _key_item("Goldrim", slot=ItemSlot.HELMET, importance=5),  # mandatory
            _key_item("Wanderlust", slot=ItemSlot.BOOTS, importance=3),
        ],
    )
    plan = await svc.plan(build)
    ls_items = plan.stages[0].core_items

    # Mandatory Goldrim (importance=5) should come first.
    assert ls_items[0].name == "Goldrim"
    assert ls_items[0].buy_priority == 1
    # Priorities are 1..N inside the stage.
    assert [ci.buy_priority for ci in ls_items] == list(range(1, len(ls_items) + 1))


async def test_plan_unpriced_items_go_to_end_game() -> None:
    fake = FakePricing(unique_quotes={})  # poe.ninja knows nothing
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Some Esoteric Unique")])

    plan = await svc.plan(build)
    end_stage = plan.stages[2]

    assert len(end_stage.core_items) == 1
    assert end_stage.core_items[0].name == "Some Esoteric Unique"
    assert end_stage.core_items[0].price_estimate is None


async def test_plan_total_cost_is_sum_of_stages() -> None:
    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={"Mageblood": 60_000.0},
    )
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Mageblood", slot=ItemSlot.BELT)])
    plan = await svc.plan(build)

    total_min = sum(s.budget_range.min.amount for s in plan.stages)
    total_max = sum(s.budget_range.max.amount for s in plan.stages)
    assert plan.total_estimated_cost.min.amount == pytest.approx(round(total_min, 2))
    assert plan.total_estimated_cost.max.amount == pytest.approx(round(total_max, 2))


async def test_plan_stages_are_monotone_even_with_expensive_mid_items() -> None:
    """Regression guard: BuildPlan validator requires monotone stage midpoints.

    A heavy mid-game item could push MID's budget midpoint above
    END_GAME's spec default. The clamp inside :func:`stage_budget` is
    what keeps the invariant valid.
    """

    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={
            "Heavy Mid Item": 4_000.0,  # 20 div -> mid bucket
            "Heavy Mid Item Two": 4_000.0,  # 20 div -> mid bucket
        },
    )
    svc = PlannerService(fake)
    build = _make_build(
        key_items=[
            _key_item("Heavy Mid Item", slot=ItemSlot.BODY_ARMOUR),
            _key_item("Heavy Mid Item Two", slot=ItemSlot.GLOVES),
        ]
    )
    plan = await svc.plan(build)
    midpoints = [s.budget_range.midpoint for s in plan.stages]
    assert midpoints == sorted(midpoints)


async def test_plan_target_goal_is_propagated() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])
    plan = await svc.plan(build, target_goal=TargetGoal.UBER_CAPABLE)
    assert plan.target_goal is TargetGoal.UBER_CAPABLE


async def test_plan_gem_changes_are_stage_appropriate() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])
    plan = await svc.plan(build)

    league_start_gems = plan.stages[0].gem_changes
    mid_gems = plan.stages[1].gem_changes
    end_gems = plan.stages[2].gem_changes

    assert any("Vortex" in g for g in league_start_gems)
    assert any("20/20" in g for g in mid_gems)
    assert any("awakened" in g.lower() for g in end_gems)


async def test_plan_expected_content_per_stage() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])
    plan = await svc.plan(build)

    assert ContentFocus.LEAGUE_START in plan.stages[0].expected_content
    assert ContentFocus.MAPPING in plan.stages[1].expected_content
    assert ContentFocus.UBERS in plan.stages[2].expected_content
