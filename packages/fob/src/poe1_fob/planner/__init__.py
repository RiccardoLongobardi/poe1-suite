"""Planner — turn a :class:`poe1_core.Build` into an upgrade plan.

Public surface:

* :class:`PlannerService` — orchestrator. Takes any object satisfying
  :class:`PricingPort` (the real :class:`poe1_pricing.PricingService`
  qualifies) and produces a :class:`poe1_core.BuildPlan` with three
  stages bucketed by divine cost. Exposes a streaming
  :meth:`PlannerService.plan_with_progress` for SSE consumers and a
  silent :meth:`PlannerService.plan` for callers that don't need
  progress.
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

__all__ = [
    "PER_ITEM_NINJA_SECONDS",
    "PER_ITEM_TRADE_SECONDS",
    "PlanRequest",
    "PlanResponse",
    "PlannerService",
    "PricingPort",
    "PricingProgress",
    "TradePort",
    "estimate_total_seconds",
    "recompute_eta",
]
