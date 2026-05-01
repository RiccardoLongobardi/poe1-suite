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
    EARLY_CAMPAIGN,
    EARLY_MAPPING,
    END_CAMPAIGN,
    END_MAPPING,
    HIGH_INVESTMENT,
    MID_CAMPAIGN,
    stage_budget,
    stage_for_amount,
)
from poe1_pricing import ItemCategory, PriceQuote, TradeQuery

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

    async def quote_unique_variant(
        self,
        name: str,
        variant: str | None,
    ) -> PriceQuote | None:
        """Variant-aware fake.

        Variants aren't modelled in :attr:`_uniques` (the existing
        fixtures cover plain uniques only). Any non-``None`` variant
        misses, and the planner falls back to :meth:`quote_unique` via
        :func:`quote_unique_range`. ``variant=None`` is equivalent to
        :meth:`quote_unique`.
        """

        if variant is None:
            return await self.quote_unique(name)
        return None


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
    # Un-priced items go to the highest stage.
    assert stage_for_amount(None) is HIGH_INVESTMENT

    # Boundaries: ceiling-inclusive on the lower stage, so the cheaper
    # bucket wins ties.
    assert stage_for_amount(0.0) is EARLY_CAMPAIGN
    assert stage_for_amount(0.5) is EARLY_CAMPAIGN  # boundary
    assert stage_for_amount(1.0) is MID_CAMPAIGN
    assert stage_for_amount(2.0) is MID_CAMPAIGN  # boundary
    assert stage_for_amount(5.0) is END_CAMPAIGN
    assert stage_for_amount(8.0) is END_CAMPAIGN  # boundary
    assert stage_for_amount(15.0) is EARLY_MAPPING
    assert stage_for_amount(25.0) is EARLY_MAPPING  # boundary
    assert stage_for_amount(50.0) is END_MAPPING
    assert stage_for_amount(100.0) is END_MAPPING  # boundary
    assert stage_for_amount(300.0) is HIGH_INVESTMENT


def test_stage_default_budget_when_empty() -> None:
    rng = stage_budget([], EARLY_CAMPAIGN, chaos_per_divine=200.0)
    assert rng.min.amount == 0.0
    assert rng.max.amount == 0.5
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
    rng = stage_budget([cheap], END_MAPPING, chaos_per_divine=200.0)
    # Items sum to ~0.015 div but End-Mapping ceiling is 100 -> clamp
    # pushes the band to at least [25, 100].
    assert rng.min.amount >= END_MAPPING.floor_div
    assert rng.max.amount >= END_MAPPING.ceiling_div


# ---------------------------------------------------------------------------
# Service tests — full plan happy paths
# ---------------------------------------------------------------------------


async def test_plan_with_no_key_items_returns_default_stages() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])

    plan = await svc.plan(build)

    assert len(plan.stages) == 6
    labels = [s.label for s in plan.stages]
    assert labels == [
        "Early Campaign",
        "Mid Campaign",
        "End Campaign",
        "Early Mapping",
        "End Mapping",
        "High Investment",
    ]
    # Every stage falls back to its HEURISTIC default.
    for s in plan.stages:
        assert s.budget_range.source is PriceSource.HEURISTIC
        assert not s.core_items


async def test_plan_buckets_items_by_divine_cost() -> None:
    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={
            "Tabula Rasa": 30.0,  # 0.15 div  -> Early Campaign (idx 0, ≤0.5)
            "Inpulsa's Broken Heart": 1500.0,  # 7.5 div  -> End Campaign (idx 2, ≤8)
            "Mageblood": 60_000.0,  # 300 div -> High Investment (idx 5, >100)
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
    early_campaign, _mid, end_campaign, _early_mapping, _end_mapping, high_inv = plan.stages

    assert {ci.name for ci in early_campaign.core_items} == {"Tabula Rasa"}
    assert {ci.name for ci in end_campaign.core_items} == {"Inpulsa's Broken Heart"}
    assert {ci.name for ci in high_inv.core_items} == {"Mageblood"}


async def test_plan_respects_buy_priority_within_stage() -> None:
    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={
            "Atziri's Promise": 4.0,  # 0.02 div  -> Early Campaign
            "Goldrim": 2.0,  # 0.01 div  -> Early Campaign
            "Wanderlust": 1.0,  # 0.005 div -> Early Campaign
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
    early_campaign_items = plan.stages[0].core_items

    # Mandatory Goldrim (importance=5) should come first.
    assert early_campaign_items[0].name == "Goldrim"
    assert early_campaign_items[0].buy_priority == 1
    # Priorities are 1..N inside the stage.
    assert [ci.buy_priority for ci in early_campaign_items] == list(
        range(1, len(early_campaign_items) + 1)
    )


async def test_plan_unpriced_items_go_to_high_investment() -> None:
    fake = FakePricing(unique_quotes={})  # poe.ninja knows nothing
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Some Esoteric Unique")])

    plan = await svc.plan(build)
    high_investment = plan.stages[-1]  # last stage

    assert len(high_investment.core_items) == 1
    assert high_investment.core_items[0].name == "Some Esoteric Unique"
    assert high_investment.core_items[0].price_estimate is None


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

    A heavy mid-stage item could push that stage's budget midpoint above
    a later stage's spec default. The clamp inside :func:`stage_budget`
    is what keeps the invariant valid across all 6 stages.
    """

    fake = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={
            "Heavy Mid Item": 4_000.0,  # 20 div -> Early Mapping bucket
            "Heavy Mid Item Two": 4_000.0,  # 20 div -> Early Mapping bucket
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


async def test_plan_gem_changes_cover_main_skill_lab_and_awakened() -> None:
    """Sanity check on the per-stage gem advice across the lifecycle.

    Whether the build hits a specific template (e.g. VortexOccultist) or
    falls through to GenericTemplate, three things must be true: the
    early-campaign copy mentions the main skill, the mid-campaign copy
    mentions the lab, and the late stages mention 20/20 / awakened
    progression.
    """

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])  # main_skill="Vortex" via fixture → VortexOccultistTemplate
    plan = await svc.plan(build)

    early_campaign_gems = plan.stages[0].gem_changes
    mid_campaign_gems = plan.stages[1].gem_changes
    end_mapping_gems = plan.stages[4].gem_changes
    high_inv_gems = plan.stages[5].gem_changes

    # Early Campaign mentions the build's main skill.
    assert any("Vortex" in g for g in early_campaign_gems)
    # Mid Campaign mentions ascendancy.
    assert any("lab" in g.lower() for g in mid_campaign_gems)
    # End Mapping mentions 20/20 / 21/20 / awakened.
    assert any("20/20" in g or "21/20" in g or "awakened" in g.lower() for g in end_mapping_gems)
    # High Investment mentions awakened level 5/6.
    assert any("Awakened" in g for g in high_inv_gems)


async def test_plan_expected_content_per_stage() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[])
    plan = await svc.plan(build)

    # Map index -> expected ContentFocus tag based on the 6-stage spec.
    assert ContentFocus.LEAGUE_START in plan.stages[0].expected_content  # Early Campaign
    assert ContentFocus.LEAGUE_START in plan.stages[1].expected_content  # Mid Campaign
    assert ContentFocus.MAPPING in plan.stages[2].expected_content  # End Campaign
    assert ContentFocus.MAPPING in plan.stages[3].expected_content  # Early Mapping
    assert ContentFocus.BOSSING in plan.stages[4].expected_content  # End Mapping
    assert ContentFocus.UBERS in plan.stages[5].expected_content  # High Investment


# ---------------------------------------------------------------------------
# Streaming progress tests — plan_with_progress + ETA helpers
# ---------------------------------------------------------------------------


async def test_plan_with_progress_emits_full_lifecycle() -> None:
    """The generator emits start → item_started/item_done* → done."""

    fake = FakePricing(unique_quotes={"Mageblood": 60_000.0})
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Mageblood", slot=ItemSlot.BELT)])

    events = [e async for e in svc.plan_with_progress(build)]
    kinds = [e.kind for e in events]

    assert kinds[0] == "start"
    assert kinds[-1] == "done"
    # one item → exactly one item_started + one item_done in between.
    assert kinds.count("item_started") == 1
    assert kinds.count("item_done") == 1


async def test_plan_with_progress_start_event_carries_upfront_eta() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(
        key_items=[
            _key_item("Tabula Rasa"),
            _key_item("Mageblood", slot=ItemSlot.BELT),
            _key_item("Goldrim", slot=ItemSlot.HELMET),
        ]
    )

    first = None
    async for e in svc.plan_with_progress(build):
        first = e
        break

    assert first is not None
    assert first.kind == "start"
    assert first.total_items == 3
    # 3 ninja items at 0.5s each = 1.5s upfront ETA.
    assert first.eta_seconds == pytest.approx(1.5, abs=0.01)


async def test_plan_with_progress_eta_decreases_through_lifecycle() -> None:
    """ETA on every item_done should be strictly non-increasing."""

    fake = FakePricing(
        unique_quotes={
            "Tabula Rasa": 30.0,
            "Mageblood": 60_000.0,
            "Goldrim": 2.0,
        }
    )
    svc = PlannerService(fake)
    build = _make_build(
        key_items=[
            _key_item("Tabula Rasa"),
            _key_item("Mageblood", slot=ItemSlot.BELT),
            _key_item("Goldrim", slot=ItemSlot.HELMET),
        ]
    )

    item_done_etas = [
        e.eta_seconds async for e in svc.plan_with_progress(build) if e.kind == "item_done"
    ]
    assert item_done_etas == sorted(item_done_etas, reverse=True)
    # Final item_done should have ETA ~ 0 (one more event — done — to go).
    assert item_done_etas[-1] >= 0.0


async def test_plan_with_progress_done_event_carries_final_plan() -> None:
    fake = FakePricing(unique_quotes={"Mageblood": 60_000.0})
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Mageblood", slot=ItemSlot.BELT)])

    final = None
    async for e in svc.plan_with_progress(build):
        if e.kind == "done":
            final = e
    assert final is not None
    assert final.final_plan is not None
    assert final.final_plan.build_source_id == build.source_id
    assert len(final.final_plan.stages) == 6


async def test_plan_with_progress_item_events_carry_identity() -> None:
    fake = FakePricing(unique_quotes={"Mageblood": 60_000.0})
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Mageblood", slot=ItemSlot.BELT)])

    events = [e async for e in svc.plan_with_progress(build)]
    item_started = next(e for e in events if e.kind == "item_started")

    assert item_started.item_name == "Mageblood"
    assert item_started.item_slot == "belt"
    assert item_started.item_index == 0


async def test_plan_silent_wrapper_returns_same_plan_as_streaming_done_event() -> None:
    """The silent ``plan()`` is a thin wrapper — output must match the streaming version."""

    fake = FakePricing(unique_quotes={"Mageblood": 60_000.0})
    svc = PlannerService(fake)
    build = _make_build(key_items=[_key_item("Mageblood", slot=ItemSlot.BELT)])

    silent = await svc.plan(build)
    streamed = None
    async for e in svc.plan_with_progress(build):
        if e.kind == "done":
            streamed = e.final_plan
    assert streamed is not None
    assert silent.total_estimated_cost.min.amount == streamed.total_estimated_cost.min.amount
    assert silent.total_estimated_cost.max.amount == streamed.total_estimated_cost.max.amount


# ---------------------------------------------------------------------------
# ETA helper unit tests
# ---------------------------------------------------------------------------


def test_estimate_total_seconds_is_linear_in_each_population() -> None:
    from poe1_fob.planner.progress import (
        PER_ITEM_NINJA_SECONDS,
        PER_ITEM_TRADE_SECONDS,
        estimate_total_seconds,
    )

    assert estimate_total_seconds(n_ninja=0, n_trade=0) == 0.0
    assert estimate_total_seconds(n_ninja=10, n_trade=0) == pytest.approx(
        10 * PER_ITEM_NINJA_SECONDS
    )
    assert estimate_total_seconds(n_ninja=0, n_trade=5) == pytest.approx(5 * PER_ITEM_TRADE_SECONDS)
    assert estimate_total_seconds(n_ninja=4, n_trade=3) == pytest.approx(
        4 * PER_ITEM_NINJA_SECONDS + 3 * PER_ITEM_TRADE_SECONDS
    )


def test_recompute_eta_uses_upfront_estimate_before_any_item_done() -> None:
    from poe1_fob.planner.progress import recompute_eta

    eta = recompute_eta(
        items_completed=0,
        total_items=10,
        elapsed_seconds=0.0,
        upfront_eta=20.0,
    )
    assert eta == 20.0


def test_recompute_eta_uses_observed_average_after_first_item() -> None:
    from poe1_fob.planner.progress import recompute_eta

    # 1 item in 4 seconds -> projected 4s/item * 9 remaining = 36s.
    eta = recompute_eta(
        items_completed=1,
        total_items=10,
        elapsed_seconds=4.0,
        upfront_eta=999.0,  # ignored once we have observed data
    )
    assert eta == pytest.approx(36.0)


def test_recompute_eta_returns_zero_when_all_items_done() -> None:
    from poe1_fob.planner.progress import recompute_eta

    eta = recompute_eta(
        items_completed=5,
        total_items=5,
        elapsed_seconds=10.0,
        upfront_eta=999.0,
    )
    assert eta == 0.0


# ---------------------------------------------------------------------------
# Variant-aware unique pricing
# ---------------------------------------------------------------------------


class _VariantTrackingFake(FakePricing):
    """Fake that records (name, variant) calls for assertion."""

    def __init__(self) -> None:
        super().__init__(
            chaos_per_divine=200.0,
            unique_quotes={"Forbidden Shako": 100.0},
        )
        self.variant_calls: list[tuple[str, str | None]] = []
        self.plain_calls: list[str] = []

    async def quote_unique(self, name: str) -> PriceQuote | None:
        self.plain_calls.append(name)
        return await super().quote_unique(name)

    async def quote_unique_variant(
        self,
        name: str,
        variant: str | None,
    ) -> PriceQuote | None:
        self.variant_calls.append((name, variant))
        # Always miss on the variant lookup so the planner exercises
        # the cheapest-variant fallback path.
        return None


async def test_planner_calls_quote_unique_variant_for_registered_uniques() -> None:
    """Forbidden Shako with an Allocates mod should trigger a variant lookup."""

    from poe1_core.models import Item, ItemMod, ItemRarity, KeyItem
    from poe1_core.models.enums import ModType

    fake = _VariantTrackingFake()
    svc = PlannerService(fake)

    shako_with_keystone = KeyItem(
        slot=ItemSlot.HELMET,
        item=Item(
            name="Forbidden Shako",
            base_type="Great Crown",
            rarity=ItemRarity.UNIQUE,
            slot=ItemSlot.HELMET,
            mods=[
                ItemMod(text="Allocates Avatar of Fire", mod_type=ModType.EXPLICIT),
            ],
        ),
        importance=4,
    )
    build = _make_build(key_items=[shako_with_keystone])

    await svc.plan(build)

    # The variant-aware lookup ran with the resolved keystone.
    assert ("Forbidden Shako", "Avatar of Fire") in fake.variant_calls
    # And after that miss, fell back to the plain unique lookup.
    assert "Forbidden Shako" in fake.plain_calls


# ---------------------------------------------------------------------------
# Trade-API integration for rare items
# ---------------------------------------------------------------------------


class _FakeTradePort:
    """Minimal :class:`TradePort` for tests.

    Returns a canned :class:`PriceQuote` for any query whose stat
    filter list is non-empty (the planner already gates that, but we
    re-check defensively). Records every query for assertion.
    """

    def __init__(self, *, chaos_value: float = 8000.0) -> None:
        self._chaos = chaos_value
        self.calls: list[tuple[str | None, int]] = []  # (type, len(stats))

    async def quote(
        self,
        query: TradeQuery,
        *,
        chaos_per_divine: float,
        category: ItemCategory = ItemCategory.UNIQUE_ARMOUR,
    ) -> PriceQuote | None:
        self.calls.append((query.type, len(query.stats)))
        if not query.stats:
            return None
        return _make_quote(
            query.type or "rare",
            self._chaos,
            category=category,
            sample_count=20,
        )


def _rare_key_item(
    base_type: str,
    *,
    slot: ItemSlot,
    importance: int = 4,
    explicits: tuple[str, ...] = (
        "+122 to maximum Life",
        "+48% to Fire Resistance",
        "+38% to Cold Resistance",
    ),
) -> KeyItem:
    """Helper to build a RARE :class:`KeyItem` with mod text."""

    from poe1_core.models import ItemMod
    from poe1_core.models.enums import ModType

    return KeyItem(
        slot=slot,
        item=Item(
            name="",  # rares have no unique name
            base_type=base_type,
            rarity=ItemRarity.RARE,
            slot=slot,
            mods=[ItemMod(text=m, mod_type=ModType.EXPLICIT) for m in explicits],
        ),
        importance=importance,
    )


async def test_planner_prices_rares_via_trade_when_port_provided() -> None:
    fake_pricing = FakePricing()
    fake_trade = _FakeTradePort(chaos_value=8000.0)  # 40 div @ 200
    svc = PlannerService(fake_pricing, trade=fake_trade)
    build = _make_build(
        key_items=[_rare_key_item("Vaal Regalia", slot=ItemSlot.BODY_ARMOUR)],
    )

    plan = await svc.plan(build)

    # The Trade port was consulted with the right base type and >=2 filters.
    assert fake_trade.calls
    base_type, n_stats = fake_trade.calls[0]
    assert base_type == "Vaal Regalia"
    assert n_stats >= 2
    # The rare priced at 40 div (8000 chaos / 200) lands in End Mapping
    # (boundaries 25-100). 6-stage layout: idx 4 == End Mapping.
    end_mapping = plan.stages[4]
    assert any(ci.name == "Vaal Regalia" for ci in end_mapping.core_items)


async def test_planner_skips_trade_when_port_not_configured() -> None:
    """Without a TradePort the planner leaves rares un-priced (no exceptions)."""

    fake_pricing = FakePricing()
    svc = PlannerService(fake_pricing)  # trade=None implicit
    build = _make_build(
        key_items=[_rare_key_item("Vaal Regalia", slot=ItemSlot.BODY_ARMOUR)],
    )

    plan = await svc.plan(build)

    # Item is in the plan but un-priced.
    all_items = [ci for s in plan.stages for ci in s.core_items]
    rare = next((ci for ci in all_items if ci.name == "Vaal Regalia"), None)
    assert rare is not None
    assert rare.price_estimate is None


async def test_planner_skips_trade_when_rare_has_too_few_recognised_mods() -> None:
    """A rare with only 1 recognised mod doesn't waste a Trade query."""

    fake_pricing = FakePricing()
    fake_trade = _FakeTradePort()
    svc = PlannerService(fake_pricing, trade=fake_trade)
    build = _make_build(
        key_items=[
            _rare_key_item(
                "Vaal Regalia",
                slot=ItemSlot.BODY_ARMOUR,
                # Only one recognised mod (life). Below the 2-filter threshold.
                explicits=("+122 to maximum Life",),
            )
        ],
    )

    await svc.plan(build)

    # No Trade call should have been issued.
    assert fake_trade.calls == []


async def test_planner_eta_includes_trade_seconds_for_rares() -> None:
    """Upfront ETA scales by the per-rare Trade budget (~6s each)."""

    from poe1_fob.planner.progress import (
        PER_ITEM_NINJA_SECONDS,
        PER_ITEM_TRADE_SECONDS,
    )

    fake_pricing = FakePricing()
    fake_trade = _FakeTradePort()
    svc = PlannerService(fake_pricing, trade=fake_trade)
    build = _make_build(
        key_items=[
            _key_item("Tabula Rasa"),  # unique → ninja
            _rare_key_item("Vaal Regalia", slot=ItemSlot.BODY_ARMOUR),  # rare → trade
            _rare_key_item("Coronal Maul", slot=ItemSlot.WEAPON_MAIN),  # rare → trade
        ],
    )

    first = None
    async for e in svc.plan_with_progress(build):
        first = e
        break
    assert first is not None
    # 1 ninja item (0.5s) + 2 trade items (12s) = 12.5s upfront.
    expected = PER_ITEM_NINJA_SECONDS + 2 * PER_ITEM_TRADE_SECONDS
    assert first.eta_seconds == pytest.approx(expected, abs=0.01)


async def test_planner_skips_variant_lookup_for_unregistered_uniques() -> None:
    """A unique without a registered resolver goes straight to quote_unique."""

    fake = _VariantTrackingFake()
    svc = PlannerService(fake)
    # Mageblood has no registered resolver in the default registry.
    build = _make_build(key_items=[_key_item("Mageblood", slot=ItemSlot.BELT)])

    await svc.plan(build)

    # Variant resolver returned None → quote_unique_variant called with
    # variant=None, which short-circuits to quote_unique inside
    # quote_unique_range. We expect ZERO variant_calls in this path.
    assert fake.variant_calls == []
    assert "Mageblood" in fake.plain_calls


# ---------------------------------------------------------------------------
# Watcher's Eye combo pricing — Step 13.B
# ---------------------------------------------------------------------------


def _watchers_eye_key_item(*explicits: str) -> KeyItem:
    """Build a Watcher's Eye KeyItem with the given mod text lines."""

    from poe1_core.models import ItemMod
    from poe1_core.models.enums import ModType

    return KeyItem(
        slot=ItemSlot.JEWEL,
        item=Item(
            name="Watcher's Eye",
            base_type="Prismatic Jewel",
            rarity=ItemRarity.UNIQUE,
            slot=ItemSlot.JEWEL,
            mods=[ItemMod(text=m, mod_type=ModType.EXPLICIT) for m in explicits],
        ),
        importance=4,
    )


async def test_watchers_eye_routes_via_trade_when_port_available() -> None:
    """A Watcher's Eye with recognised aura-conditional mods goes to Trade."""

    fake_pricing = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={"Watcher's Eye": 600.0},  # cheap-variant fallback price
    )
    fake_trade = _FakeTradePort(chaos_value=12_000.0)  # 60 div Trade-priced
    svc = PlannerService(fake_pricing, trade=fake_trade)
    build = _make_build(
        key_items=[
            _watchers_eye_key_item(
                "While affected by Hatred, 18% of Physical Damage Converted to Cold Damage",
                "While affected by Malevolence, 32% increased Damage Over Time",
            )
        ],
    )

    plan = await svc.plan(build)

    # Trade was consulted with name=Watcher's Eye and 2 stat filters.
    assert fake_trade.calls
    base, n_stats = fake_trade.calls[0]
    assert base == "Prismatic Jewel"
    assert n_stats == 2
    # The item priced at 60 div ends up in End Mapping (25-100 div bucket).
    end_mapping = plan.stages[4]
    assert any(ci.name == "Watcher's Eye" for ci in end_mapping.core_items)


async def test_watchers_eye_falls_back_to_ninja_when_trade_returns_none() -> None:
    """Trade route returns None → planner uses poe.ninja as a safety net."""

    class _SilentTrade(_FakeTradePort):
        async def quote(
            self,
            query: TradeQuery,
            *,
            chaos_per_divine: float,
            category: ItemCategory = ItemCategory.UNIQUE_JEWEL,
        ) -> PriceQuote | None:
            self.calls.append((query.type, len(query.stats)))
            return None  # always misses

    fake_pricing = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={"Watcher's Eye": 6_000.0},  # 30 div via ninja
    )
    fake_trade = _SilentTrade()
    svc = PlannerService(fake_pricing, trade=fake_trade)
    build = _make_build(
        key_items=[
            _watchers_eye_key_item(
                "While affected by Hatred, 18% of Physical Damage Converted to Cold Damage",
                "While affected by Malevolence, 32% increased Damage Over Time",
            )
        ],
    )

    plan = await svc.plan(build)

    # Trade was attempted but returned None.
    assert fake_trade.calls
    # Ninja-priced Watcher's Eye landed in End Mapping (30 div).
    items = [ci for s in plan.stages for ci in s.core_items if ci.name == "Watcher's Eye"]
    assert len(items) == 1
    priced = items[0].price_estimate
    assert priced is not None  # ninja fallback worked


async def test_watchers_eye_skips_trade_without_port() -> None:
    """No TradePort → Watcher's Eye prices via the regular unique path."""

    fake_pricing = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={"Watcher's Eye": 6_000.0},
    )
    svc = PlannerService(fake_pricing)  # trade=None
    build = _make_build(
        key_items=[
            _watchers_eye_key_item(
                "While affected by Hatred, 18% of Physical Damage Converted to Cold Damage",
            )
        ],
    )

    plan = await svc.plan(build)

    # Item is priced (via ninja fallback) and present.
    items = [ci for s in plan.stages for ci in s.core_items if ci.name == "Watcher's Eye"]
    assert len(items) == 1
    assert items[0].price_estimate is not None


async def test_watchers_eye_no_recognised_mods_falls_back_to_unique_lookup() -> None:
    """A Watcher's Eye with mods we don't recognise still gets a price (cheapest variant)."""

    fake_pricing = FakePricing(
        chaos_per_divine=200.0,
        unique_quotes={"Watcher's Eye": 4_000.0},
    )
    fake_trade = _FakeTradePort()
    svc = PlannerService(fake_pricing, trade=fake_trade)
    build = _make_build(
        key_items=[
            _watchers_eye_key_item(
                "While affected by Clarity, mods we deliberately don't pattern-match",
            )
        ],
    )

    plan = await svc.plan(build)

    # Trade NOT consulted (zero stat filters extracted).
    assert fake_trade.calls == []
    # But the item is still priced via the ninja unique fallback.
    items = [ci for s in plan.stages for ci in s.core_items if ci.name == "Watcher's Eye"]
    assert len(items) == 1
    assert items[0].price_estimate is not None


# ---------------------------------------------------------------------------
# Build template dispatch (Step 10)
# ---------------------------------------------------------------------------


def _make_rf_build() -> Build:
    """Build fixture with main_skill='Righteous Fire' so RfPohx matches."""

    return Build(
        source_id="pob::rf-test",
        source_type=BuildSourceType.POB,
        character_class=CharacterClass.MARAUDER,
        ascendancy=None,
        main_skill="Righteous Fire",
        support_gems=["Concentrated Effect", "Burning Damage", "Empower"],
        damage_profile=DamageProfile.FIRE_DOT,
        playstyle=Playstyle.DEGEN_AURA,
        content_tags=[ContentFocus.MAPPING],
        defense_profile=DefenseProfile.LIFE,
        key_items=[],
    )


def test_pick_template_returns_rf_for_righteous_fire() -> None:
    from poe1_fob.planner import pick_template

    build = _make_rf_build()
    template = pick_template(build)
    assert template.name == "rf_pohx"


def test_pick_template_falls_back_to_generic_for_unknown_skill() -> None:
    """A skill that isn't covered by any registered template hits the generic fallback.

    Step 12 added templates for the most popular skills (Vortex, Spark,
    Cyclone, Spectre, etc.); we use a deliberately exotic / unmatched
    skill name here to exercise the fallback path.
    """

    from poe1_fob.planner import pick_template

    obscure = _make_build(key_items=[]).model_copy(update={"main_skill": "Bladestorm"})
    template = pick_template(obscure)
    assert template.name == "generic"


def test_template_registry_covers_popular_skills() -> None:
    """Step 12 coverage — every flagship skill resolves to a specific template.

    If someone removes a template by accident the test fires immediately.
    """

    from poe1_fob.planner import pick_template

    canonical = {
        "Righteous Fire": "rf_pohx",
        "Vortex": "vortex_occultist",
        "Spark": "spark_inquisitor",
        "Bone Spear": "bone_spear_necromancer",
        "Hexblast": "hexblast_mines",
        "Volatile Dead": "detonate_dead_necromancer",
        "Bane": "bane_occultist",
        "Cyclone": "cyclone_slayer",
        "Lightning Strike": "lightning_strike_raider",
        "Tornado Shot": "tornado_shot_deadeye",
        "Frost Blades": "frost_blades_raider",
        "Toxic Rain": "toxic_rain_pathfinder",
        "Raise Spectre": "spectre_necromancer",
        "Summon Skeletons": "skeleton_mages_necromancer",
        "Animate Weapon": "animate_weapon_necromancer",
        "Holy Flame Totem": "holy_flame_totem_hierophant",
        "Shrapnel Ballista": "ballista_totem_deadeye",
        "Boneshatter": "boneshatter_marauder",
        "Earthshatter": "earthshatter_juggernaut",
        "Tectonic Slam": "tectonic_slam_chieftain",
        "Molten Strike": "molten_strike_chieftain",
        "Ground Slam": "ground_slam_juggernaut",
        "Volcanic Fissure": "volcanic_fissure_juggernaut",
        "Reave": "reave_slayer",
        "Lacerate": "lacerate_gladiator",
        "Splitting Steel": "splitting_steel_gladiator",
        "Sunder": "sunder_champion",
        "Static Strike": "static_strike_gladiator",
        "Spectral Throw": "spectral_throw_champion",
        "Ice Shot": "ice_shot_deadeye",
        "Poisonous Concoction": "poisonous_concoction_pathfinder",
        "Penance Brand": "penance_brand_inquisitor",
        "Crackling Lance": "crackling_lance_inquisitor",
        "Arc": "arc_hierophant",
        "Smite": "smite_guardian",
        "Blade Vortex": "poison_blade_vortex_assassin",
        "Cobra Lash": "cobra_lash_assassin",
        "Pyroclast Mine": "pyroclast_mines_saboteur",
    }
    base_build = _make_build(key_items=[])
    for skill, expected in canonical.items():
        build = base_build.model_copy(update={"main_skill": skill})
        template = pick_template(build)
        assert template.name == expected, (
            f"main_skill={skill!r} should resolve to {expected!r}, got {template.name!r}"
        )


async def test_vortex_template_emits_signature_advice() -> None:
    """Spot-check VortexOccultistTemplate produces its key Cold Snap → Vortex advice."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Vortex"})
    plan = await svc.plan(build)

    early = plan.stages[0]
    assert any("Cold Snap" in g for g in early.gem_changes)
    assert any("Frostblink" in g for g in early.gem_changes)
    # Profane Bloom is the Vortex-specific lab pick.
    mid = plan.stages[1]
    assert any("Profane Bloom" in g for g in mid.gem_changes)


async def test_cyclone_template_emits_signature_advice() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Cyclone"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    end_map = plan.stages[4]
    assert any("Cyclone" in g for g in mid.gem_changes)
    assert any("Atziri's Disfavour" in t for t in end_map.tree_changes)


async def test_boneshatter_template_emits_signature_advice() -> None:
    """Boneshatter template advice mentions trauma stack mechanic + lab pick."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Boneshatter"})
    plan = await svc.plan(build)

    early = plan.stages[0]
    mid = plan.stages[1]
    # Early uses Sunder/Ground Slam pre-skill-unlock.
    assert any("Sunder" in g or "Ground Slam" in g for g in early.gem_changes)
    # Mid Campaign: Unflinching (Jugg) o Crave the Slaughter (Berserker).
    assert any("Unflinching" in g or "Crave the Slaughter" in g for g in mid.gem_changes)


async def test_earthshatter_template_emits_signature_advice() -> None:
    """Earthshatter template hits Slam Skills crafting + Tukohama's Coffer."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Earthshatter"})
    plan = await svc.plan(build)

    early_map = plan.stages[3]
    assert any("Slam" in g for g in early_map.gem_changes)
    assert any("Tukohama" in t or "+1 socketed" in t for t in early_map.tree_changes)


async def test_tectonic_slam_template_emits_signature_advice() -> None:
    """Tectonic Slam template mentions Tukohama War's Herald + EC mechanic."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Tectonic Slam"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Tukohama" in g for g in mid.gem_changes)
    assert any("Endurance Charge" in t or "Kaom's Way" in t for t in early_map.tree_changes)


async def test_molten_strike_template_emits_signature_advice() -> None:
    """Molten Strike template hits Tukohama lab + Avatar of Fire keystone."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Molten Strike"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    assert any("Tukohama" in g for g in mid.gem_changes)
    assert any("Avatar of Fire" in t for t in mid.tree_changes)


async def test_ground_slam_template_emits_signature_advice() -> None:
    """Ground Slam template covers day-1 pickup + Marohi/Slam crafting path."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Ground Slam"})
    plan = await svc.plan(build)

    early = plan.stages[0]
    early_map = plan.stages[3]
    assert any("Ground Slam" in g for g in early.gem_changes)
    assert any("Marohi" in g or "Slam Skills" in g for g in early_map.gem_changes)


async def test_volcanic_fissure_template_emits_signature_advice() -> None:
    """Volcanic Fissure template mentions Avatar of Fire + Forbidden Flame/Flesh."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Volcanic Fissure"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    end_map = plan.stages[4]
    assert any("Avatar of Fire" in t for t in mid.tree_changes)
    assert any("Forbidden" in t for t in end_map.tree_changes)


async def test_reave_template_emits_signature_advice() -> None:
    """Reave template hits Headsman lab + Paradoxica weapon path."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Reave"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Headsman" in g for g in mid.gem_changes)
    assert any("Paradoxica" in g or "Foil" in g for g in early_map.gem_changes)


async def test_lacerate_template_emits_signature_advice() -> None:
    """Lacerate template covers Painforged + corpse explode + Crimson Dance."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Lacerate"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    assert any("Painforged" in g for g in mid.gem_changes)
    assert any("Crimson Dance" in t for t in mid.tree_changes)


async def test_splitting_steel_template_emits_signature_advice() -> None:
    """Splitting Steel template covers Steel Skills + impale + Painforged/Champion."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Splitting Steel"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    assert any("Painforged" in g or "Worthy Foe" in g for g in mid.gem_changes)
    assert any("Steel Skills" in t for t in mid.tree_changes)


async def test_sunder_template_emits_signature_advice() -> None:
    """Sunder template hits Worthy Foe lab + Marohi Erqi/Slam Skills crafting."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Sunder"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Worthy Foe" in g for g in mid.gem_changes)
    assert any("Marohi" in g or "Slam Skills" in g for g in early_map.gem_changes)


async def test_static_strike_template_emits_signature_advice() -> None:
    """Static Strike template covers Versatile Combatant + Saviour shield."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Static Strike"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Versatile Combatant" in g or "Inspirational" in g for g in mid.gem_changes)
    assert any("Saviour" in t for t in early_map.tree_changes)


async def test_spectral_throw_template_emits_signature_advice() -> None:
    """Spectral Throw template hits Worthy Foe + Vaal ST burst + GMP scaling."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Spectral Throw"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Worthy Foe" in g for g in mid.gem_changes)
    assert any("Vaal Spectral Throw" in g for g in early_map.gem_changes)


async def test_ice_shot_template_emits_signature_advice() -> None:
    """Ice Shot template hits Endless Munitions + Lioneye's Glare/+3 bow path."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Ice Shot"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    end_map = plan.stages[4]
    assert any("Endless Munitions" in g for g in mid.gem_changes)
    assert any("+3 bow" in t or "Voltaxic Rift" in t for t in end_map.tree_changes)


async def test_poisonous_concoction_template_emits_signature_advice() -> None:
    """PConc template covers Master Surgeon + Nature's Reprisal + Mageblood."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Poisonous Concoction"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    end_map = plan.stages[4]
    assert any("Master Surgeon" in g for g in mid.gem_changes)
    assert any("Nature's Reprisal" in t for t in mid.tree_changes)
    assert any("Mageblood" in t for t in end_map.tree_changes)


async def test_penance_brand_template_emits_signature_advice() -> None:
    """Penance Brand template hits Inevitable Judgment + Brand Recall + Pious Path."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Penance Brand"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    assert any("Inevitable Judgment" in g for g in mid.gem_changes)
    assert any("Pious Path" in t for t in mid.tree_changes)


async def test_crackling_lance_template_emits_signature_advice() -> None:
    """Crackling Lance template covers Augury of Penitence + Slower Projectiles boss."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Crackling Lance"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    end_map = plan.stages[4]
    assert any("Inevitable Judgment" in g for g in mid.gem_changes)
    assert any("Augury of Penitence" in t for t in mid.tree_changes)
    assert any("Slower Projectiles" in g for g in end_map.gem_changes)


async def test_arc_template_emits_signature_advice() -> None:
    """Arc Hierophant template hits Conviction of Power + MoM + Arcane Cloak."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Arc"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    assert any("Conviction of Power" in g for g in mid.gem_changes)
    assert any("Mind Over Matter" in t for t in mid.tree_changes)


async def test_smite_template_emits_signature_advice() -> None:
    """Smite Guardian template hits Radiant Crusade + Aegis Aurora + Sublime Vision."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Smite"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Radiant Crusade" in g for g in mid.gem_changes)
    assert any("Aegis Aurora" in g for g in early_map.gem_changes)
    assert any("Sublime Vision" in t for t in early_map.tree_changes)


def test_aurabot_matcher_routes_on_aura_count() -> None:
    """A build with 5+ aura supports routes to AurabotGuardianTemplate.

    Aurabot is identified by aura stack, not main_skill — a Smite Guardian
    with only 2 auras still goes to SmiteGuardianTemplate, but a build
    with 5+ auras (regardless of main_skill) goes to Aurabot.
    """

    from poe1_fob.planner import pick_template

    base = _make_build(key_items=[])
    aurabot = base.model_copy(
        update={
            "main_skill": "Smite",  # throwaway DPS
            "support_gems": [
                "Wrath",
                "Anger",
                "Hatred",
                "Determination",
                "Discipline",
                "Vitality",
            ],
        }
    )
    template = pick_template(aurabot)
    assert template.name == "aurabot_guardian"

    # 2 auras only → still smite_guardian.
    smite = base.model_copy(
        update={
            "main_skill": "Smite",
            "support_gems": ["Wrath", "Determination", "Multistrike"],
        }
    )
    assert pick_template(smite).name == "smite_guardian"


async def test_aurabot_template_emits_signature_advice() -> None:
    """Aurabot template covers Radiant Crusade + Generosity + Crown of the Tyrant."""

    fake = FakePricing()
    svc = PlannerService(fake)
    aurabot = _make_build(key_items=[]).model_copy(
        update={
            "main_skill": "Smite",
            "support_gems": [
                "Wrath",
                "Anger",
                "Hatred",
                "Determination",
                "Discipline",
                "Pride",
            ],
        }
    )
    plan = await svc.plan(aurabot)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    end_map = plan.stages[4]
    assert any("Radiant Crusade" in g for g in mid.gem_changes)
    assert any("Generosity" in g for g in mid.gem_changes)
    assert any("Crown of the Tyrant" in t for t in early_map.tree_changes)
    assert any("Generosity" in g for g in end_map.gem_changes)


async def test_poison_blade_vortex_template_emits_signature_advice() -> None:
    """Poison BV Assassin template hits Mistwalker + Cospri's Will + Cold Iron Point."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Blade Vortex"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Mistwalker" in g for g in mid.gem_changes)
    assert any("Cospri's Will" in g for g in early_map.gem_changes)
    assert any("Cold Iron Point" in g for g in early_map.gem_changes)


async def test_cobra_lash_template_emits_signature_advice() -> None:
    """Cobra Lash Assassin template covers Toxic Delivery + Awakened Chain."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Cobra Lash"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Toxic Delivery" in t for t in mid.tree_changes)
    assert any("Awakened Chain" in g for g in early_map.gem_changes)


async def test_pyroclast_mines_template_emits_signature_advice() -> None:
    """Pyroclast Mines Saboteur template covers Pyromaniac + Bombardier + Bottled Faith."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Pyroclast Mine"})
    plan = await svc.plan(build)

    mid = plan.stages[1]
    early_map = plan.stages[3]
    assert any("Pyromaniac" in g for g in mid.gem_changes)
    assert any("Bombardier" in t for t in mid.tree_changes)
    assert any("Bottled Faith" in t for t in early_map.tree_changes)


async def test_spectre_template_routes_to_minion_setup() -> None:
    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_build(key_items=[]).model_copy(update={"main_skill": "Raise Spectre"})
    plan = await svc.plan(build)

    early_map = plan.stages[3]
    assert any(
        "Spectre" in g or "Convocation" in g for g in early_map.gem_changes + early_map.tree_changes
    )


async def test_planner_uses_rf_template_when_main_skill_is_rf() -> None:
    """RF Pohx template emits its signature 'no RF before lab' warning."""

    fake = FakePricing()
    svc = PlannerService(fake)
    build = _make_rf_build()
    plan = await svc.plan(build)

    early_campaign = plan.stages[0]

    # The Holy Flame Totem advice and the RF warning are RF-specific.
    assert any("Holy Flame Totem" in g for g in early_campaign.gem_changes)
    assert any("righteous fire" in g.lower() for g in early_campaign.gem_changes)
    # Rationale is overridden by the template (mentions Holy Flame Totem).
    assert "Holy Flame Totem" in early_campaign.upgrade_rationale


async def test_planner_rf_template_advice_evolves_across_stages() -> None:
    """RF template hits its full lifecycle: HFT → RF switch → Kaom's → Mageblood."""

    fake = FakePricing()
    svc = PlannerService(fake)
    plan = await svc.plan(_make_rf_build())

    _early, mid, _end_camp, early_map, _end_map, high_inv = plan.stages

    # Mid Campaign: lab + switch to RF.
    assert any("Unflinching" in g for g in mid.gem_changes)
    assert any("Righteous Fire" in g for g in mid.gem_changes)
    # Early Mapping: Kaom's Heart milestone in tree_changes.
    assert any("Kaom" in t for t in early_map.tree_changes)
    # High Investment: Mageblood mention.
    assert any("Mageblood" in t for t in high_inv.tree_changes)


async def test_template_override_bypasses_registry() -> None:
    """Tests can lock template behaviour by passing template_override."""

    from poe1_fob.planner import GenericTemplate

    fake = FakePricing()
    # Even though main_skill='Righteous Fire' would match RfPohx, the
    # override forces GenericTemplate.
    svc = PlannerService(fake, template_override=GenericTemplate())
    plan = await svc.plan(_make_rf_build())

    early = plan.stages[0]
    # GenericTemplate doesn't say "Holy Flame Totem".
    assert not any("Holy Flame Totem" in g for g in early.gem_changes)
    # GenericTemplate does mention the build's main_skill.
    assert any("Righteous Fire" in g for g in early.gem_changes)
