"""Planner — turn a :class:`poe1_core.Build` into an upgrade plan.

Public surface:

* :class:`PlannerService` — orchestrator. Takes any object satisfying
  :class:`PricingPort` (the real :class:`poe1_pricing.PricingService`
  qualifies) and produces a :class:`poe1_core.BuildPlan` with three
  stages bucketed by divine cost.
* :class:`PlanRequest`, :class:`PlanResponse` — HTTP-shaped payloads
  for ``POST /fob/plan``.
"""

from __future__ import annotations

from .models import PlanRequest, PlanResponse
from .pricing import PricingPort
from .service import PlannerService

__all__ = [
    "PlanRequest",
    "PlanResponse",
    "PlannerService",
    "PricingPort",
]
