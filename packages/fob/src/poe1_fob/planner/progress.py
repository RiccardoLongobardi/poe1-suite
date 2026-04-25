"""Pricing-progress events for the streaming planner.

The planner can be slow (~6 s per Trade-priced rare; we deliberately
trade time for accuracy). The UI deserves a live progress bar and a
realistic ETA countdown rather than a 30-second-spinner-of-doom.

This module defines:

* :class:`PricingProgress` — one Pydantic event the planner yields
  during pricing, suitable for direct JSON serialisation over an
  ``EventSource`` SSE stream. ``kind`` discriminates the lifecycle
  (``start`` / ``item_started`` / ``item_done`` / ``item_failed`` /
  ``done``); the final event carries the assembled :class:`BuildPlan`.

* :func:`estimate_total_seconds` — upfront ETA for a plan with given
  item composition (``n_ninja`` poe.ninja-only items, ``n_trade``
  Trade-API items). Used when the ``start`` event fires, before any
  per-item timing is available.

* :func:`recompute_eta` — live ETA from elapsed wall time and items
  completed, used after every ``item_done``. Smooths over the upfront
  estimate's mistakes once we have actual numbers.

Both heuristics are deliberately simple. Realistic per-item times
fluctuate based on poe.ninja cache hits, GGG rate-limit headroom,
and sleep-pacing decisions; over-modelling them is brittle and
gives the user no extra signal.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from poe1_core.models import BuildPlan

# Per-item time budgets (seconds). Calibrated against typical 2026-Q2
# poe.ninja and GGG Trade behaviour:
#
# * poe.ninja overview lookups are essentially free after the first
#   call per category — the response is on disk for 15 minutes.
# * GGG Trade requires search + fetch. Search is ~1 s, fetch up to ~3 s
#   for a 10-listing batch, plus rate-limit pacing that averages ~2 s
#   between calls when running near capacity.
PER_ITEM_NINJA_SECONDS: float = 0.5
PER_ITEM_TRADE_SECONDS: float = 6.0


class PricingProgress(BaseModel):
    """One progress event from a streaming :meth:`PlannerService.plan_with_progress` call.

    The ``kind`` field discriminates the event:

    * ``start`` — first event, fires before any pricing. Carries the
      total item count and the upfront ETA so the UI can size its bar.
    * ``item_started`` — the planner is about to price ``item_name``.
      The frontend can update its "currently working on" line.
    * ``item_done`` — the price came back (success or miss). ``status``
      describes the outcome ("priced", "not found").
    * ``item_failed`` — the source raised an exception we swallowed;
      pricing continues. The item ends up un-priced in the plan.
    * ``done`` — last event, carries the assembled :class:`BuildPlan`
      in :attr:`final_plan`. The stream closes immediately after.

    Times are in seconds since the stream began for ``elapsed_seconds``,
    and seconds *until projected completion* for ``eta_seconds`` (so a
    countdown timer can use it directly).
    """

    model_config = ConfigDict(frozen=True)

    kind: Literal["start", "item_started", "item_done", "item_failed", "done"]

    item_index: int = Field(default=0, ge=0)
    total_items: int = Field(default=0, ge=0)

    item_name: str | None = None
    item_slot: str | None = None

    elapsed_seconds: float = Field(default=0.0, ge=0.0)
    eta_seconds: float = Field(default=0.0, ge=0.0)

    status: str = ""

    # Only set on ``done`` — saves the SSE consumer one round-trip.
    final_plan: BuildPlan | None = None


def estimate_total_seconds(*, n_ninja: int, n_trade: int) -> float:
    """Upfront ETA from item composition.

    ``n_ninja`` is the count of items priced via poe.ninja overview
    (uniques, cluster jewels, oils, gems). ``n_trade`` is items
    requiring a GGG Trade query (rare custom-craft, multi-axis variant
    uniques). The formula is the simplest sensible thing: linear in
    each population.
    """

    return float(n_ninja) * PER_ITEM_NINJA_SECONDS + float(n_trade) * PER_ITEM_TRADE_SECONDS


def recompute_eta(
    *,
    items_completed: int,
    total_items: int,
    elapsed_seconds: float,
    upfront_eta: float,
) -> float:
    """Live ETA from observed timing.

    Until we've completed at least one item we can't measure anything,
    so we fall back to ``upfront_eta - elapsed_seconds`` (clamped at 0).

    With ≥ 1 completed item we use the *observed* per-item average,
    which is more honest than the upfront heuristic — especially when
    Trade rate-limits start hitting and items take longer than expected.
    """

    remaining = max(0, total_items - items_completed)
    if items_completed == 0:
        return max(0.0, upfront_eta - elapsed_seconds)
    avg = elapsed_seconds / items_completed
    return remaining * avg


__all__ = [
    "PER_ITEM_NINJA_SECONDS",
    "PER_ITEM_TRADE_SECONDS",
    "PricingProgress",
    "estimate_total_seconds",
    "recompute_eta",
]
