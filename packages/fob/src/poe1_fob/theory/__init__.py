"""Theorycrafter — from-scratch build generation for FOB.

Step 39 ships Pillar 1: the rule-based Build Generator. It synthesises
a :class:`BuildSkeleton` from vendored 3.28 data — it never retrieves
builds from the poe.ninja ladder (that is the Build Finder's job).
"""

from .archetypes import Archetype, get_archetypes, resolve_archetype
from .generator import TheoryError, generate_build
from .models import BudgetTier, BuildSkeleton, GearSlot, GemLink, TreeMilestone

__all__ = [
    "Archetype",
    "BudgetTier",
    "BuildSkeleton",
    "GearSlot",
    "GemLink",
    "TheoryError",
    "TreeMilestone",
    "generate_build",
    "get_archetypes",
    "resolve_archetype",
]
