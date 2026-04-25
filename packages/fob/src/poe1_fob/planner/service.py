"""Top-level Planner orchestration.

Pipeline:

1. Resolve the current chaos-per-divine rate.
2. For every :class:`KeyItem`, derive a :class:`PriceRange`:
   * **Variant-aware uniques** — read mod text from the item, ask the
     :class:`VariantRegistry` for a poe.ninja variant string, call
     :meth:`PricingPort.quote_unique_variant`. Falls back to the
     cheapest variant (``quote_unique``) when the variant isn't listed.
   * **Plain uniques** — direct ``quote_unique`` lookup.
   * **Other items** — left un-priced for now (rare-via-Trade lands in
     a follow-up milestone alongside KeyItem extension for rares).
3. Bucket items into LEAGUE_START / MID_GAME / END_GAME by their
   divine-equivalent midpoint.
4. Sum each bucket into a stage budget and assemble the
   :class:`BuildPlan`.

Two entry points are exposed:

* :meth:`plan_with_progress` — async generator that yields
  :class:`PricingProgress` events while it works. The final ``done``
  event carries the :class:`BuildPlan`. Suitable for SSE streaming.
* :meth:`plan` — backward-compatible silent variant that consumes the
  generator and returns just the :class:`BuildPlan`.

The planner is deterministic given the same Build, the same pricing
snapshot, and the same variant registry. Pricing-source flakiness is
absorbed by :func:`chaos_to_divine_rate`'s heuristic fallback and by
leaving a :class:`CoreItem.price_estimate` as ``None`` when no source
has a listing.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from time import monotonic

from poe1_core.models import (
    Build,
    BuildPlan,
    Confidence,
    CoreItem,
    Currency,
    Item,
    KeyItem,
    PlanStage,
    PriceRange,
    PriceSource,
    PriceValue,
)
from poe1_core.models.enums import ItemRarity, TargetGoal
from poe1_pricing import VariantRegistry, build_default_registry
from poe1_shared.logging import get_logger

from .pricing import (
    PricingPort,
    chaos_to_divine_rate,
    price_range_to_divines,
    quote_unique_range,
)
from .progress import (
    PricingProgress,
    estimate_total_seconds,
    recompute_eta,
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
    """Convert a :class:`KeyItem` into a :class:`CoreItem`.

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


def _resolve_variant(item: Item, registry: VariantRegistry) -> str | None:
    """Try to derive the poe.ninja variant string from an item's mod text.

    The :class:`Item.mods` list carries the verbatim PoB mod text; we
    feed those strings into the registry's resolver. Returns ``None``
    when no resolver is registered for this item (most uniques) or
    when the resolver can't recognise the variant signal.
    """

    if not item.name:
        return None
    mod_lines = tuple(m.text for m in item.mods)
    return registry.resolve(item.name, mod_lines)


class PlannerService:
    """Build a :class:`BuildPlan` for a given :class:`Build`.

    The service is stateless and cheap — instantiate one per request.
    The injected ``pricing`` port handles the only side-effects (HTTP
    calls to poe.ninja). The ``variant_registry`` defaults to the
    canonical keystone-driven resolvers from
    :func:`poe1_pricing.build_default_registry`; tests can swap in a
    custom registry for fine-grained control.
    """

    def __init__(
        self,
        pricing: PricingPort,
        *,
        variant_registry: VariantRegistry | None = None,
    ) -> None:
        self._pricing = pricing
        self._registry = variant_registry or build_default_registry()

    # ------------------------------------------------------------------
    # Streaming entry point — yields PricingProgress as it works
    # ------------------------------------------------------------------

    async def plan_with_progress(
        self,
        build: Build,
        *,
        target_goal: TargetGoal = TargetGoal.MAPPING_AND_BOSS,
    ) -> AsyncIterator[PricingProgress]:
        """Yield progress events while the plan is built.

        Lifecycle:

        * One ``start`` event with totals + upfront ETA.
        * For each :class:`KeyItem`: an ``item_started`` event before
          the price lookup, then either ``item_done`` or
          ``item_failed`` afterwards. ``eta_seconds`` is recomputed
          from observed wall time after every completion.
        * One ``done`` event carrying the assembled :class:`BuildPlan`.

        Consumers MUST iterate to completion to receive the plan; the
        intermediate events are advisory. :meth:`plan` does this
        silently for callers that don't care about progress.
        """

        rate = await chaos_to_divine_rate(self._pricing)

        n_items = len(build.key_items)
        # All items are poe.ninja-priced for now (Trade integration for
        # rares ships in a follow-up milestone). When that lands the
        # split here will reflect KeyItem rarity.
        upfront_eta = estimate_total_seconds(n_ninja=n_items, n_trade=0)
        started_at = monotonic()

        yield PricingProgress(
            kind="start",
            total_items=n_items,
            eta_seconds=upfront_eta,
            status=f"Avvio pricing di {n_items} item...",
        )

        buckets: dict[StageSpec, list[CoreItem]] = {s: [] for s in ALL_STAGES}
        priced_count = 0

        for idx, ki in enumerate(build.key_items):
            display_name = ki.item.name or ki.item.base_type

            elapsed = monotonic() - started_at
            yield PricingProgress(
                kind="item_started",
                item_index=idx,
                total_items=n_items,
                item_name=display_name,
                item_slot=ki.slot.value,
                elapsed_seconds=round(elapsed, 2),
                eta_seconds=round(
                    recompute_eta(
                        items_completed=idx,
                        total_items=n_items,
                        elapsed_seconds=elapsed,
                        upfront_eta=upfront_eta,
                    ),
                    2,
                ),
                status=f"Cerco {display_name}...",
            )

            price = await self._price_key_item(ki, rate=rate)
            if price is not None:
                priced_count += 1
            div_amount = price_range_to_divines(price, rate)
            stage = stage_for_amount(div_amount)
            buckets[stage].append(_key_item_to_core_item(ki, price=price))

            elapsed = monotonic() - started_at
            yield PricingProgress(
                kind="item_done",
                item_index=idx + 1,
                total_items=n_items,
                item_name=display_name,
                item_slot=ki.slot.value,
                elapsed_seconds=round(elapsed, 2),
                eta_seconds=round(
                    recompute_eta(
                        items_completed=idx + 1,
                        total_items=n_items,
                        elapsed_seconds=elapsed,
                        upfront_eta=upfront_eta,
                    ),
                    2,
                ),
                status=f"{display_name}: {'priced' if price is not None else 'not found'}",
            )

        # Stable 1..N priority within each stage.
        for spec in ALL_STAGES:
            buckets[spec] = _renumber_priorities(buckets[spec])

        # Materialise PlanStage objects.
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

        elapsed = monotonic() - started_at
        yield PricingProgress(
            kind="done",
            item_index=n_items,
            total_items=n_items,
            elapsed_seconds=round(elapsed, 2),
            eta_seconds=0.0,
            status=f"Piano pronto ({priced_count}/{n_items} prezzati)",
            final_plan=plan,
        )

    # ------------------------------------------------------------------
    # Backward-compatible silent variant
    # ------------------------------------------------------------------

    async def plan(
        self,
        build: Build,
        *,
        target_goal: TargetGoal = TargetGoal.MAPPING_AND_BOSS,
    ) -> BuildPlan:
        """Build a plan without surfacing progress events.

        Consumes :meth:`plan_with_progress` internally and returns the
        plan from the final event. Same shape and semantics as the old
        single-shot ``plan()``.
        """

        plan: BuildPlan | None = None
        async for event in self.plan_with_progress(build, target_goal=target_goal):
            if event.kind == "done" and event.final_plan is not None:
                plan = event.final_plan
        if plan is None:  # pragma: no cover — generator always emits 'done'
            raise RuntimeError("planner generator exited without emitting 'done'")
        return plan

    # ------------------------------------------------------------------
    # Per-item pricing dispatch
    # ------------------------------------------------------------------

    async def _price_key_item(self, ki: KeyItem, *, rate: float) -> PriceRange | None:
        """Decide which pricing strategy to use for *ki*.

        Strategy by rarity:

        * ``UNIQUE`` — variant-aware lookup if the registry knows this
          unique, plain ``quote_unique`` otherwise. Variant misses
          fall back to the cheapest variant.
        * Anything else — currently un-priced (see module docstring).
        """

        if not ki.item.name:
            return None
        if ki.item.rarity is ItemRarity.UNIQUE:
            variant = _resolve_variant(ki.item, self._registry)
            return await quote_unique_range(
                self._pricing,
                ki.item.name,
                chaos_per_divine=rate,
                variant=variant,
            )
        return None


__all__ = ["PlannerService"]
