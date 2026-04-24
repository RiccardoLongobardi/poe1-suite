"""JSON round-trip tests for every core model.

These tests enforce the invariant ``M.model_validate_json(m.model_dump_json()) == m``
for every public model. They double as a rough smoke test: if a model's
defaults or field types drift in a way that breaks serialisation, this
file will catch it before the breakage reaches any downstream package.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import BaseModel, ValidationError

from poe1_core.models import (
    Ascendancy,
    BudgetRange,
    BudgetTier,
    Build,
    BuildIntent,
    BuildMetrics,
    BuildPlan,
    BuildSourceType,
    CharacterClass,
    ComplexityLevel,
    Confidence,
    ContentFocus,
    ContentFocusWeight,
    CoreItem,
    Currency,
    DamageProfile,
    DefenseProfile,
    HardConstraint,
    Item,
    ItemMod,
    ItemRarity,
    ItemSlot,
    KeyItem,
    League,
    ModType,
    ParserOrigin,
    PlanStage,
    Playstyle,
    PriceRange,
    PriceSource,
    PriceValue,
    TargetGoal,
    ascendancy_to_class,
    budget_tier_range,
)


def _assert_roundtrip(model: BaseModel) -> None:
    """Assert that ``model`` survives a JSON round-trip."""

    cls = type(model)
    dumped = model.model_dump_json()
    loaded = cls.model_validate_json(dumped)
    assert loaded == model, f"{cls.__name__} failed round-trip"


# ---------------------------------------------------------------------------
# League
# ---------------------------------------------------------------------------


def test_league_roundtrip() -> None:
    league = League(
        slug="Settlers",
        name="Settlers of Kalguur",
        started_at=date(2024, 7, 26),
        ended_at=date(2024, 11, 18),
        is_event=False,
        is_hardcore=False,
        is_ssf=False,
    )
    _assert_roundtrip(league)


def test_league_end_before_start_rejected() -> None:
    with pytest.raises(ValidationError):
        League(
            slug="X",
            name="X",
            started_at=date(2024, 12, 1),
            ended_at=date(2024, 11, 1),
        )


def test_league_standard_factory() -> None:
    std = League.standard()
    assert std.slug == "Standard"
    assert std.started_at is None


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------


def test_price_range_roundtrip() -> None:
    pr = PriceRange(
        min=PriceValue(amount=2.5, currency=Currency.DIVINE),
        max=PriceValue(amount=4.0, currency=Currency.DIVINE),
        source=PriceSource.POE_NINJA,
        observed_at=datetime(2026, 4, 23, 10, 0, tzinfo=UTC),
        sample_size=38,
        confidence=Confidence.HIGH,
    )
    _assert_roundtrip(pr)
    assert pr.midpoint == pytest.approx(3.25)
    assert pr.currency is Currency.DIVINE


def test_price_range_rejects_mixed_currency() -> None:
    with pytest.raises(ValidationError):
        PriceRange(
            min=PriceValue(amount=1.0, currency=Currency.CHAOS),
            max=PriceValue(amount=2.0, currency=Currency.DIVINE),
            source=PriceSource.UNKNOWN,
        )


def test_price_range_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        PriceRange(
            min=PriceValue(amount=10.0, currency=Currency.DIVINE),
            max=PriceValue(amount=1.0, currency=Currency.DIVINE),
            source=PriceSource.UNKNOWN,
        )


def test_price_value_as_divines() -> None:
    chaos = PriceValue(amount=600.0, currency=Currency.CHAOS)
    assert chaos.as_divines(chaos_per_divine=200.0) == pytest.approx(3.0)

    div = PriceValue(amount=5.0, currency=Currency.DIVINE)
    assert div.as_divines(chaos_per_divine=200.0) == 5.0


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------


def test_item_roundtrip() -> None:
    item = Item(
        name="Mageblood",
        base_type="Heavy Belt",
        rarity=ItemRarity.UNIQUE,
        slot=ItemSlot.BELT,
        item_level=86,
        mods=[
            ItemMod(
                text="+(15–25) to all Attributes",  # PoE uses en dash in mod ranges  # noqa: RUF001
                mod_type=ModType.IMPLICIT,
            ),
            ItemMod(
                text="Magic Utility Flasks cannot be removed from Inventory",
                mod_type=ModType.EXPLICIT,
            ),
        ],
        corrupted=False,
    )
    _assert_roundtrip(item)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def test_build_roundtrip_minimal() -> None:
    build = Build(
        source_id="pob::abc123",
        source_type=BuildSourceType.POB,
        character_class=CharacterClass.WITCH,
        ascendancy=Ascendancy.OCCULTIST,
        main_skill="Creeping Frost",
        damage_profile=DamageProfile.COLD_DOT,
        playstyle=Playstyle.SELF_CAST,
        defense_profile=DefenseProfile.CHAOS_INOCULATION,
    )
    _assert_roundtrip(build)
    assert build.is_from_pob is True


def test_build_roundtrip_full() -> None:
    price = PriceRange.point(5.0, source=PriceSource.POE_NINJA, confidence=Confidence.MEDIUM)
    build = Build(
        source_id="ninja::char-12345",
        source_type=BuildSourceType.POE_NINJA_BUILDS,
        character_class=CharacterClass.WITCH,
        ascendancy=Ascendancy.OCCULTIST,
        main_skill="Creeping Frost",
        support_gems=["Awakened Spell Echo", "Inspiration", "Swift Affliction"],
        damage_profile=DamageProfile.COLD_DOT,
        playstyle=Playstyle.SELF_CAST,
        content_tags=[ContentFocus.MAPPING, ContentFocus.BOSSING],
        defense_profile=DefenseProfile.CHAOS_INOCULATION,
        estimated_cost=price,
        metrics=BuildMetrics(
            total_dps=2_500_000.0,
            effective_hp=7500,
            energy_shield=7500,
            chaos_res=75,
            fire_res=75,
            cold_res=75,
            lightning_res=75,
        ),
        key_items=[
            KeyItem(
                slot=ItemSlot.AMULET,
                item=Item(
                    name="Ashes of the Stars",
                    base_type="Onyx Amulet",
                    rarity=ItemRarity.UNIQUE,
                ),
                importance=4,
            ),
        ],
        origin_url="https://poe.ninja/builds/settlers/character/foo",
        tree_version="3.25.0",
        league_slug="Settlers",
        captured_at=datetime(2026, 4, 20, 14, 30, tzinfo=UTC),
    )
    _assert_roundtrip(build)
    assert build.is_from_pob is False


# ---------------------------------------------------------------------------
# BuildIntent
# ---------------------------------------------------------------------------


def test_build_intent_roundtrip() -> None:
    intent = BuildIntent(
        damage_profile=DamageProfile.COLD_DOT,
        alternative_damage_profiles=[DamageProfile.COLD],
        playstyle=Playstyle.SELF_CAST,
        content_focus=[
            ContentFocusWeight(focus=ContentFocus.MAPPING, weight=0.7),
            ContentFocusWeight(focus=ContentFocus.BOSSING, weight=0.3),
        ],
        budget=BudgetRange(tier=BudgetTier.MEDIUM, min_divines=5.0, max_divines=25.0),
        complexity_cap=ComplexityLevel.MEDIUM,
        defense_profile=DefenseProfile.CHAOS_INOCULATION,
        hard_constraints={HardConstraint.NO_MINION, HardConstraint.NO_TOTEM},
        confidence=0.87,
        raw_input="voglio una cold dot comfy per mapping budget medio",
        parser_origin=ParserOrigin.RULE_BASED,
    )
    _assert_roundtrip(intent)


def test_build_intent_rejects_oversum_weights() -> None:
    with pytest.raises(ValidationError):
        BuildIntent(
            content_focus=[
                ContentFocusWeight(focus=ContentFocus.MAPPING, weight=0.8),
                ContentFocusWeight(focus=ContentFocus.BOSSING, weight=0.5),
            ],
            confidence=0.5,
            raw_input="x",
            parser_origin=ParserOrigin.RULE_BASED,
        )


def test_budget_range_rejects_inversion() -> None:
    with pytest.raises(ValidationError):
        BudgetRange(min_divines=10.0, max_divines=1.0)


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------


def test_build_plan_roundtrip() -> None:
    stage1 = PlanStage(
        label="Stage 1 — League start",
        budget_range=PriceRange(
            min=PriceValue(amount=0.0, currency=Currency.DIVINE),
            max=PriceValue(amount=2.0, currency=Currency.DIVINE),
            source=PriceSource.HEURISTIC,
        ),
        expected_content=[ContentFocus.MAPPING, ContentFocus.LEAGUE_START],
        core_items=[
            CoreItem(
                name="Tabula Rasa",
                slot=ItemSlot.BODY_ARMOUR,
                rarity=ItemRarity.UNIQUE,
                buy_priority=1,
                price_estimate=PriceRange.point(0.2, source=PriceSource.POE_NINJA),
            ),
        ],
        upgrade_rationale="Unlocks 6-link for core skill during acts.",
        next_step_trigger="Quando hai ~2 div, passa allo Stage 2.",
    )
    stage2 = PlanStage(
        label="Stage 2 — Mid budget",
        budget_range=PriceRange(
            min=PriceValue(amount=2.0, currency=Currency.DIVINE),
            max=PriceValue(amount=15.0, currency=Currency.DIVINE),
            source=PriceSource.HEURISTIC,
        ),
        core_items=[],
    )
    plan = BuildPlan(
        build_source_id="pob::abc123",
        target_goal=TargetGoal.MAPPING_AND_BOSS,
        stages=[stage1, stage2],
        total_estimated_cost=PriceRange(
            min=PriceValue(amount=0.0, currency=Currency.DIVINE),
            max=PriceValue(amount=15.0, currency=Currency.DIVINE),
            source=PriceSource.HEURISTIC,
        ),
    )
    _assert_roundtrip(plan)


def test_build_plan_rejects_unordered_stages() -> None:
    high = PlanStage(
        label="High",
        budget_range=PriceRange(
            min=PriceValue(amount=20.0, currency=Currency.DIVINE),
            max=PriceValue(amount=30.0, currency=Currency.DIVINE),
            source=PriceSource.HEURISTIC,
        ),
    )
    low = PlanStage(
        label="Low",
        budget_range=PriceRange(
            min=PriceValue(amount=0.0, currency=Currency.DIVINE),
            max=PriceValue(amount=1.0, currency=Currency.DIVINE),
            source=PriceSource.HEURISTIC,
        ),
    )
    with pytest.raises(ValidationError):
        BuildPlan(
            build_source_id="x",
            target_goal=TargetGoal.MAPPING_ONLY,
            stages=[high, low],
            total_estimated_cost=PriceRange.point(30.0, source=PriceSource.HEURISTIC),
        )


# ---------------------------------------------------------------------------
# Enum helpers
# ---------------------------------------------------------------------------


def test_ascendancy_to_class_covers_all() -> None:
    for asc in Ascendancy:
        cls = ascendancy_to_class(asc)
        assert isinstance(cls, CharacterClass)


def test_budget_tier_ranges_monotonic() -> None:
    order = [
        BudgetTier.LEAGUE_START,
        BudgetTier.LOW,
        BudgetTier.MEDIUM,
        BudgetTier.HIGH,
        BudgetTier.MIRROR,
    ]
    prev_max = -1.0
    for tier in order:
        lo, hi = budget_tier_range(tier)
        assert lo >= prev_max
        assert hi > lo
        prev_max = hi if hi != float("inf") else prev_max
