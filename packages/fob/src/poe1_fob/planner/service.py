"""Top-level Planner orchestration.

Pipeline:

1. Resolve the current chaos-per-divine rate.
2. Price every :class:`KeyItem` on the build via poe.ninja.
3. Bucket items into LEAGUE_START / MID_GAME / END_GAME by their
   divine-equivalent midpoint.
4. Sum each bucket into a stage budget and assemble the
   :class:`BuildPlan`.

The planner is fully deterministic given the same Build and the same
pricing snapshot. Pricing-source flakiness is absorbed by
:func:`chaos_to_divine_rate`'s heuristic fallback and by leaving a
:class:`CoreItem.price_estimate` as ``None`` when poe.ninja has no
listing for a given unique.
"""

from __future__ import annotations

from poe1_core.models import (
    Build,
    BuildPlan,
    Confidence,
    CoreItem,
    Currency,
    KeyItem,
    PlanStage,
    PriceRange,
    PriceSource,
    PriceValue,
)
from poe1_core.models.enums import TargetGoal
from poe1_shared.logging import get_logger

from .pricing import (
    PricingPort,
    chaos_to_divine_rate,
    price_range_to_divines,
    quote_unique_range,
)
from .stages import ALL_STAGES, StageSpec, stage_budget, stage_for_amount

log = get_logger(__name__)


# ``importance`` runs 1..5 in :class:`KeyItem` (5 = mandatory). For
# :class:`CoreItem.buy_priority` we want 1 = "buy first", so a higher
# importance maps to a lower priority number. This is a per-stage
# pre-sort key; final 1..N ordering is re-applied after bucketing.
def _initial_priority(importance: int) -> int:
    return max(1, 6 - importance)


def _key_item_to_core_item(ki: KeyItem, *, price: PriceRange | None) -> CoreItem:
    """Convert a :class:`KeyItem` (uniques only here) into a :class:`CoreItem`.

    Falls back to ``base_type`` when the item has no name (defensive —
    proper uniques always carry a name in PoB exports).
    """

    name = ki.item.name or ki.item.base_type
    return CoreItem(
        name=name,
        slot=ki.slot,
        rarity=ki.item.rarity,
        price_estimate=price,
        buy_priority=_initial_priority(ki.importance),
        notes=None,
    )


def _renumber_priorities(items: list[CoreItem]) -> list[CoreItem]:
    """Re-stamp ``buy_priority`` 1..N within a single stage.

    Sorts by the seed priority first, then by name for deterministic
    output. Pydantic models are frozen, so we rebuild via
    :py:meth:`BaseModel.model_copy`.
    """

    sorted_items = sorted(items, key=lambda c: (c.buy_priority, c.name))
    return [ci.model_copy(update={"buy_priority": i}) for i, ci in enumerate(sorted_items, start=1)]


def _gem_changes_for_stage(spec: StageSpec, build: Build) -> list[str]:
    """Stage-flavoured gem hints derived from the build's main skill."""

    if spec.label == "League start":
        supports = ", ".join(build.support_gems[:3]) or "(usa i support che hai dalle quest)"
        return [f"Setup base: {build.main_skill} + {supports}."]
    if spec.label == "Mid-game":
        return [
            "Porta tutti i support gem a 20/20 (quality + level).",
            "Compra eventuali gem 21/20 corruptati se il prezzo è ragionevole.",
        ]
    if spec.label == "End-game" and build.support_gems:
        return [
            "Sostituisci con awakened support gem dove esistono "
            "(es. Awakened Added Fire / Awakened Spell Echo)."
        ]
    return []


def _total_cost(stages: list[PlanStage]) -> PriceRange:
    """Sum stage budgets into a single divine PriceRange."""

    total_min = sum(s.budget_range.min.amount for s in stages)
    total_max = sum(s.budget_range.max.amount for s in stages)
    return PriceRange(
        min=PriceValue(amount=round(total_min, 2), currency=Currency.DIVINE),
        max=PriceValue(amount=round(total_max, 2), currency=Currency.DIVINE),
        source=PriceSource.POE_NINJA,
        confidence=Confidence.MEDIUM,
    )


class PlannerService:
    """Build a :class:`BuildPlan` for a given :class:`Build`.

    The service is stateless and cheap — instantiate one per request.
    The injected ``pricing`` port handles the only side-effects
    (HTTP calls to poe.ninja).
    """

    def __init__(self, pricing: PricingPort) -> None:
        self._pricing = pricing

    async def plan(
        self,
        build: Build,
        *,
        target_goal: TargetGoal = TargetGoal.MAPPING_AND_BOSS,
    ) -> BuildPlan:
        rate = await chaos_to_divine_rate(self._pricing)

        # 1) Price each key item, then bucket by divine midpoint.
        buckets: dict[StageSpec, list[CoreItem]] = {s: [] for s in ALL_STAGES}
        priced_count = 0

        for ki in build.key_items:
            price: PriceRange | None = None
            if ki.item.name:  # uniques expose a non-empty name
                price = await quote_unique_range(
                    self._pricing,
                    ki.item.name,
                    chaos_per_divine=rate,
                )
            if price is not None:
                priced_count += 1

            div_amount = price_range_to_divines(price, rate)
            stage = stage_for_amount(div_amount)
            buckets[stage].append(_key_item_to_core_item(ki, price=price))

        # 2) Stable 1..N priority within each stage.
        for spec in ALL_STAGES:
            buckets[spec] = _renumber_priorities(buckets[spec])

        # 3) Materialise PlanStage objects.
        stages: list[PlanStage] = [
            PlanStage(
                label=spec.label,
                budget_range=stage_budget(buckets[spec], spec, chaos_per_divine=rate),
                expected_content=list(spec.expected_content),
                core_items=buckets[spec],
                tree_changes=[],
                gem_changes=_gem_changes_for_stage(spec, build),
                upgrade_rationale=spec.rationale,
                next_step_trigger=spec.next_trigger,
            )
            for spec in ALL_STAGES
        ]

        plan = BuildPlan(
            build_source_id=build.source_id,
            target_goal=target_goal,
            stages=stages,
            total_estimated_cost=_total_cost(stages),
        )

        log.info(
            "fob_plan_built",
            source_id=build.source_id,
            target_goal=target_goal.value,
            key_items=len(build.key_items),
            priced=priced_count,
            stages=len(stages),
            total_min_div=plan.total_estimated_cost.min.amount,
            total_max_div=plan.total_estimated_cost.max.amount,
        )
        return plan


__all__ = ["PlannerService"]
