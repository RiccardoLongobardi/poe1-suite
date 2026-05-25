"""Theorycrafter — from-scratch build generation (v2, Step 40)."""

from .generator import (
    TheoryError,
    TheoryHallucinationError,
    generate_build,
    list_active_skills,
)
from .models import (
    BudgetTier,
    BuildSkeleton,
    ContentFocus,
    DamageType,
    DefenceArchetype,
    GearSlot,
    GemLink,
    SkillEntry,
    SkillsResponse,
    StatEstimate,
    TheoryIntent,
    TreeNodeRef,
)
from .precomputed import available_count as precomputed_count
from .precomputed import lookup as lookup_precomputed
from .viability import ViabilityIssue, ViabilityReport, validate_build

__all__ = [
    "BudgetTier",
    "BuildSkeleton",
    "ContentFocus",
    "DamageType",
    "DefenceArchetype",
    "GearSlot",
    "GemLink",
    "SkillEntry",
    "SkillsResponse",
    "StatEstimate",
    "TheoryError",
    "TheoryHallucinationError",
    "TheoryIntent",
    "TreeNodeRef",
    "ViabilityIssue",
    "ViabilityReport",
    "generate_build",
    "list_active_skills",
    "lookup_precomputed",
    "precomputed_count",
    "validate_build",
]
