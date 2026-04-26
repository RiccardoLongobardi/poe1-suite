"""Planner — turn a :class:`poe1_core.Build` into an upgrade plan.

Public surface:

* :class:`PlannerService` — orchestrator. Takes any object satisfying
  :class:`PricingPort` (the real :class:`poe1_pricing.PricingService`
  qualifies) and produces a :class:`poe1_core.BuildPlan` with **six**
  stages bucketed by divine cost: Early/Mid/End Campaign + Early/End
  Mapping + High Investment. Exposes a streaming
  :meth:`PlannerService.plan_with_progress` for SSE consumers and a
  silent :meth:`PlannerService.plan` for callers that don't need
  progress.
* :class:`BuildTemplate`, :func:`pick_template` — per-archetype
  per-stage content (gem changes, tree changes, rationale, trigger).
  RfPohx is the reference; everything else falls through to
  :class:`GenericTemplate`.
* :class:`PricingProgress` — one event in the streaming lifecycle.
* :class:`PlanRequest`, :class:`PlanResponse` — HTTP-shaped payloads
  for ``POST /fob/plan``.
"""

from __future__ import annotations

from .models import PlanRequest, PlanResponse
from .pricing import PricingPort, TradePort
from .progress import (
    PER_ITEM_NINJA_SECONDS,
    PER_ITEM_TRADE_SECONDS,
    PricingProgress,
    estimate_total_seconds,
    recompute_eta,
)
from .service import PlannerService
from .templates import (
    BuildTemplate,
    GenericTemplate,
    RfPohxTemplate,
    StagePlanContent,
    pick_template,
)

__all__ = [
    "PER_ITEM_NINJA_SECONDS",
    "PER_ITEM_TRADE_SECONDS",
    "BuildTemplate",
    "GenericTemplate",
    "PlanRequest",
    "PlanResponse",
    "PlannerService",
    "PricingPort",
    "PricingProgress",
    "RfPohxTemplate",
    "StagePlanContent",
    "TradePort",
    "estimate_total_seconds",
    "pick_template",
    "recompute_eta",
]
