"""Reverse-progression engine — derive upgrade ladders from endgame items.

The Step 13.D planner picks a hand-tuned :class:`BuildTemplate` based on
``main_skill`` and emits the same advice for everyone with that skill,
regardless of which items they actually run. This package complements
that approach: it takes the user's **endgame** :class:`KeyItem`s and
**downgrades** each one into a ladder of progressively cheaper
predecessors, then distributes the rungs across the 6 stages by
divine cost.

Public surface:

* :class:`LadderStep` — one rung (a stage + an item kind + a price cap).
* :class:`UpgradeLadder` — ordered tuple of rungs for one endgame
  :class:`KeyItem`, cheap → endgame.
* :class:`ItemDegrader` Protocol — produces an :class:`UpgradeLadder`
  for any :class:`KeyItem`.
* :class:`HardcodedDegrader` — first implementation. Hand-curated table
  for ~10 popular uniques (Mageblood, Headhunter, Awakened gem 5, …).
  Falls back to a single-rung "endgame only" ladder when the item isn't
  in the table.

Roadmap (out of scope this turn):

* Integration with :class:`poe1_fob.planner.PlannerService` via a
  ``mode='reverse'`` parameter on :meth:`plan`.
* :class:`PoeNinjaDegrader` — derive ladders from poe.ninja unique
  history (cheapest comparable variant).
* :class:`AwakenedGemDegrader` — auto-degrade Awakened Empower 5 →
  Awakened Empower 4 → … → Empower 3 from gem name patterns.
"""

from __future__ import annotations

from .degrader import (
    AwakenedGemDegrader,
    CompositeDegrader,
    HardcodedDegrader,
    ItemDegrader,
)
from .models import LadderStep, UpgradeLadder

__all__ = [
    "AwakenedGemDegrader",
    "CompositeDegrader",
    "HardcodedDegrader",
    "ItemDegrader",
    "LadderStep",
    "UpgradeLadder",
]
