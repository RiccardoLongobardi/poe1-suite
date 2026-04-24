"""Domain models for the PoE 1 suite.

Every model exported from this package is a Pydantic v2 model. Import
from the individual submodules if you only need one; importing from
``poe1_core.models`` pulls in everything.
"""

from __future__ import annotations

from .build import Build, BuildMetrics, KeyItem
from .build_intent import BudgetRange, BuildIntent, ContentFocusWeight
from .enums import (
    Ascendancy,
    BudgetTier,
    BuildSourceType,
    CharacterClass,
    ClearSpeedTier,
    ComplexityLevel,
    Confidence,
    ContentFocus,
    Currency,
    DamageProfile,
    DefenseProfile,
    HardConstraint,
    ItemRarity,
    ItemSlot,
    ModType,
    ParserOrigin,
    Playstyle,
    PriceSource,
    TargetGoal,
    ascendancy_to_class,
    budget_tier_range,
)
from .item import Item, ItemMod
from .league import League
from .plan import BuildPlan, CoreItem, PlanStage
from .pricing import PriceRange, PriceValue

__all__ = [
    "Ascendancy",
    "BudgetRange",
    "BudgetTier",
    "Build",
    "BuildIntent",
    "BuildMetrics",
    "BuildPlan",
    "BuildSourceType",
    "CharacterClass",
    "ClearSpeedTier",
    "ComplexityLevel",
    "Confidence",
    "ContentFocus",
    "ContentFocusWeight",
    "CoreItem",
    "Currency",
    "DamageProfile",
    "DefenseProfile",
    "HardConstraint",
    "Item",
    "ItemMod",
    "ItemRarity",
    "ItemSlot",
    "KeyItem",
    "League",
    "ModType",
    "ParserOrigin",
    "PlanStage",
    "Playstyle",
    "PriceRange",
    "PriceSource",
    "PriceValue",
    "TargetGoal",
    "ascendancy_to_class",
    "budget_tier_range",
]
