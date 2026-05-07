"""Gear progression — per-stage complete equipment specs.

Step 14 T2. Companion of :mod:`poe1_fob.tree`. Each stage of a
template can carry a :class:`StageGearSet` describing every slot the
player should fill: unique by name, rare with mod requirements, or
explicitly skipped (e.g. no off-hand for 2H weapon builds).

Public surface:

* :class:`StageGearSlot` — one slot's spec (slot enum + item name +
  kind + notes + budget cap).
* :class:`StageGearSet` — all slots for a single stage.
* :class:`GearProgression` — ordered tuple of StageGearSet per
  template.
* :func:`gear_progression_for` — registry lookup by template name.
"""

from __future__ import annotations

from .models import GearKind, GearProgression, StageGearSet, StageGearSlot
from .progressions import GEAR_REGISTRY, RF_POHX_GEAR_PROGRESSION, gear_progression_for

__all__ = [
    "GEAR_REGISTRY",
    "RF_POHX_GEAR_PROGRESSION",
    "GearKind",
    "GearProgression",
    "StageGearSet",
    "StageGearSlot",
    "gear_progression_for",
]
