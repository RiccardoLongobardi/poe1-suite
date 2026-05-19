"""Theorycrafter — build-from-scratch tooling for FOB.

Step 38 ships Pillar 1 only: the rule-based Build Generator. Future
pillars (item/modifier browser, atlas strategy, item filter) will join
this package.
"""

from .generator import TheoryError, generate_build
from .models import SkeletonUnique, TheoryBuildSkeleton

__all__ = [
    "SkeletonUnique",
    "TheoryBuildSkeleton",
    "TheoryError",
    "generate_build",
]
