"""Top-level Planner orchestration.

Pipeline:

1. Resolve the current chaos-per-divine rate.
2. Pick a :class:`BuildTemplate` from the registry based on the
   build's main skill — falls back to :class:`GenericTemplate` when
   nothing matches.
3. For every :class:`KeyItem`, derive a :class:`PriceRange`:
   * **Variant-aware uniques** — read mod text from the item, ask the
     :class:`VariantRegistry` for a poe.ninja variant string, call
     :meth:`PricingPort.quote_unique_variant`. Falls back to the
     cheapest variant (``quote_unique``) when the variant isn't listed.
   * **Plain uniques** — direct ``quote_unique`` lookup.
   * **Rare items** — when a TradePort is configured, build a
     stat-aware Trade query from the item's mods (≥ 2 recognised
     valuable mods required) and percentile-trim the listings.
   * **Anything else** — left un-priced.
4. Bucket items across the 6 stages (Early / Mid / End Campaign +
   Early / End Mapping + High Investment) by their divine-equivalent
   midpoint.
5. Run the template against each stage to produce gem changes, tree
   changes, rationale, and trigger copy. Sum each bucket into a stage
   budget and assemble the :class:`BuildPlan`.

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
from poe1_core.models.enums import ItemRarity, ItemSlot, TargetGoal
from poe1_pricing import ItemCategory, TradeQuery, VariantRegistry, build_default_registry
from poe1_shared.logging import get_logger

from ..pob.rares import valuable_stat_filters_from_mods
from .pricing import (
    PricingPort,
    TradePort,
    chaos_to_divine_rate,
    price_range_to_divines,
    quote_trade_range,
    quote_unique_range,
)
from .progress import (
    PricingProgress,
    estimate_total_seconds,
    recompute_eta,
)
from .stages import ALL_STAGES, StageSpec, stage_budget, stage_for_amount
from .templates import BuildTemplate, StagePlanContent, pick_template

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

    Carries forward ``base_type`` and the mod text lines so the
    frontend's "Cerca su Trade" dialog can populate its toggle list
    without re-fetching the original Build.
    """

    name = ki.item.name or ki.item.base_type
    return CoreItem(
        name=name,
        slot=ki.slot,
        rarity=ki.item.rarity,
        price_estimate=price,
        buy_priority=_initial_priority(ki.importance),
        notes=None,
        base_type=ki.item.base_type or None,
        mods=tuple(m.text for m in ki.item.mods),
    )


def _renumber_priorities(items: list[CoreItem]) -> list[CoreItem]:
    """Re-stamp ``buy_priority`` 1..N within a single stage.

    Sorts by the seed priority first, then by name for deterministic
    output. Pydantic models are frozen, so we rebuild via
    :py:meth:`BaseModel.model_copy`.
    """

    sorted_items = sorted(items, key=lambda c: (c.buy_priority, c.name))
    return [ci.model_copy(update={"buy_priority": i}) for i, ci in enumerate(sorted_items, start=1)]


def _stage_content(spec: StageSpec, build: Build, template: BuildTemplate) -> StagePlanContent:
    """Per-stage payload from a build template.

    Template selection happens once at the top of
    :meth:`plan_with_progress`; this is a thin pass-through so the
    streaming generator stays linear and easy to read.
    """

    return template.for_stage(spec, build)


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


# Unique items that should be priced via the GGG Trade API when a
# TradePort is configured, instead of poe.ninja's overview. These
# uniques have many price-distinct combos (Watcher's Eye stacks
# aura+stat pairs; future entries will cover Forbidden Flame/Flesh
# notable combos and other multi-axis variants) where poe.ninja's
# single "cheapest variant" doesn't reflect the rolled value.
_TRADE_PRICED_UNIQUES: frozenset[str] = frozenset(
    {
        "Watcher's Eye",
    }
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
        trade: TradePort | None = None,
        variant_registry: VariantRegistry | None = None,
        template_override: BuildTemplate | None = None,
    ) -> None:
        self._pricing = pricing
        self._trade = trade
        self._registry = variant_registry or build_default_registry()
        # Tests pass ``template_override`` to lock template behaviour
        # without going through the registry. Production leaves this
        # ``None`` so :func:`pick_template` runs against each Build.
        self._template_override = template_override

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
        template = self._template_override or pick_template(build)

        n_items = len(build.key_items)
        # Split items by which source will price them: uniques go to
        # poe.ninja (~0.5s each, mostly cached), rares go to GGG Trade
        # (~6s each with rate-limit pacing). When ``self._trade`` is
        # ``None`` rares are skipped entirely — count them as ninja so
        # the ETA stays honest.
        if self._trade is not None:
            n_trade = sum(1 for ki in build.key_items if ki.item.rarity is ItemRarity.RARE)
        else:
            n_trade = 0
        n_ninja = n_items - n_trade
        upfront_eta = estimate_total_seconds(n_ninja=n_ninja, n_trade=n_trade)
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

        # Materialise PlanStage objects via the resolved template.
        stages: list[PlanStage] = []
        for spec in ALL_STAGES:
            content = _stage_content(spec, build, template)
            stages.append(
                PlanStage(
                    label=spec.label,
                    budget_range=stage_budget(buckets[spec], spec, chaos_per_divine=rate),
                    expected_content=list(spec.expected_content),
                    core_items=buckets[spec],
                    tree_changes=content.tree_changes,
                    gem_changes=content.gem_changes,
                    upgrade_rationale=content.rationale_override or spec.rationale,
                    next_step_trigger=content.trigger_override or spec.next_trigger,
                )
            )

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

        * ``UNIQUE`` in :data:`_TRADE_PRICED_UNIQUES` (Watcher's Eye, etc.)
          — when a TradePort is configured, route via stat-aware Trade
          search instead of poe.ninja. These uniques have so many price-
          distinct variants (Watcher's Eye has ~250 aura+stat combos)
          that poe.ninja's single-line "cheapest variant" undersells the
          actual roll the player has. Trade's stat filter pins the exact
          combo the player wants priced.
        * Other ``UNIQUE`` — variant-aware lookup if the registry knows
          this unique, plain ``quote_unique`` otherwise. Variant misses
          fall back to the cheapest variant.
        * ``RARE`` — when a Trade port is configured, build a stat-aware
          query from the item's mods and price via the Trade API
          (percentile-trimmed median). Rares without enough recognised
          mods (< 2 ``StatFilter``s) skip the query altogether — they'd
          return noise, not signal.
        * Other rarities — un-priced.
        """

        if ki.item.rarity is ItemRarity.UNIQUE:
            if not ki.item.name:
                return None
            # Combo-priced uniques: route via Trade when available so the
            # exact aura+stat combo the player rolled can be priced.
            if self._trade is not None and ki.item.name in _TRADE_PRICED_UNIQUES:
                trade_price = await self._price_combo_unique(ki, rate=rate)
                if trade_price is not None:
                    return trade_price
                # Trade gave no signal (zero listings, all unconvertible
                # currencies, etc.) — fall through to poe.ninja so the
                # planner still ends up with *some* price.
            variant = _resolve_variant(ki.item, self._registry)
            return await quote_unique_range(
                self._pricing,
                ki.item.name,
                chaos_per_divine=rate,
                variant=variant,
            )
        if ki.item.rarity is ItemRarity.RARE and self._trade is not None:
            mod_texts = tuple(m.text for m in ki.item.mods)
            stats = valuable_stat_filters_from_mods(mod_texts, max_filters=6)
            if len(stats) < 2:
                return None
            query = TradeQuery(
                type=ki.item.base_type,
                stats=tuple(stats),
            )
            return await quote_trade_range(
                self._trade,
                query,
                chaos_per_divine=rate,
                category=_slot_to_category(ki.slot),
            )
        return None

    async def _price_combo_unique(
        self,
        ki: KeyItem,
        *,
        rate: float,
    ) -> PriceRange | None:
        """Trade-pricing path for combo-rich uniques like Watcher's Eye.

        Builds a Trade query keyed on the item's name + base type + the
        stat filters extracted from its rolled mods. Returns ``None``
        when the mods don't carry any recognised aura-conditional stat
        (the planner falls back to the standard variant lookup in that
        case so unrolled / fixture-empty items still get *some* price).

        Caller (``_price_key_item``) guarantees ``self._trade`` is set
        and ``ki.item.name`` is non-empty.
        """

        assert self._trade is not None  # narrowing for the type checker
        assert ki.item.name

        mod_texts = tuple(m.text for m in ki.item.mods)
        stats = valuable_stat_filters_from_mods(mod_texts, max_filters=4)
        if not stats:
            return None
        query = TradeQuery(
            name=ki.item.name,
            type=ki.item.base_type or None,
            stats=tuple(stats),
        )
        return await quote_trade_range(
            self._trade,
            query,
            chaos_per_divine=rate,
            category=_slot_to_category(ki.slot),
        )


def _slot_to_category(slot: ItemSlot) -> ItemCategory:
    """Best-effort mapping of an item slot to an :class:`ItemCategory`.

    The category is decorative metadata on the resulting
    :class:`PriceQuote`; it doesn't affect Trade search, only how
    consumers attribute the item afterwards. Slots without a clean
    mapping fall back to :attr:`ItemCategory.UNIQUE_ARMOUR` (the most
    common case).
    """

    if slot in {
        ItemSlot.HELMET,
        ItemSlot.BODY_ARMOUR,
        ItemSlot.GLOVES,
        ItemSlot.BOOTS,
    }:
        return ItemCategory.UNIQUE_ARMOUR
    if slot in {ItemSlot.WEAPON_MAIN, ItemSlot.WEAPON_OFFHAND}:
        return ItemCategory.UNIQUE_WEAPON
    if slot in {ItemSlot.RING, ItemSlot.AMULET, ItemSlot.BELT}:
        return ItemCategory.UNIQUE_ACCESSORY
    if slot in {ItemSlot.JEWEL, ItemSlot.CLUSTER_JEWEL}:
        return ItemCategory.UNIQUE_JEWEL
    return ItemCategory.UNIQUE_ARMOUR


__all__ = ["PlannerService"]
