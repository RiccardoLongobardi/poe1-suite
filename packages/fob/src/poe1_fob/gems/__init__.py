"""Gem links — per-stage structured skill gem progression.

Step 14 T3. Companion of :mod:`poe1_fob.tree` and :mod:`poe1_fob.gear`.
Each stage of a template can carry a :class:`StageGemLinks` describing
every gem socket the player should fill: main skill 6L, plus 4L
laterals (CWDT, auras, movement, defense).

Public surface:

* :class:`GemSpec` — one gem (name + level + quality + alt-quality).
* :class:`GemLink` — one socket group (slot + N sockets + ordered gems).
* :class:`StageGemLinks` — all links for one stage.
* :class:`GemProgression` — ordered tuple per template.
* :func:`gem_progression_for` — registry lookup.
"""

from __future__ import annotations

from .dynamic import derive_gem_progression
from .models import (
    AltQuality,
    GemLink,
    GemProgression,
    GemSpec,
    StageGemLinks,
)
from .progressions import (
    GEM_REGISTRY,
    RF_POHX_GEM_PROGRESSION,
    gem_progression_for,
)

__all__ = [
    "GEM_REGISTRY",
    "RF_POHX_GEM_PROGRESSION",
    "AltQuality",
    "GemLink",
    "GemProgression",
    "GemSpec",
    "StageGemLinks",
    "derive_gem_progression",
    "gem_progression_for",
]
