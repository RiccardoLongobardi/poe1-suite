"""Pydantic models for the Theorycrafter Build Generator (Step 39).

A :class:`BuildSkeleton` is generated **from scratch** from vendored
3.28 data (archetype catalogue + passive tree + item bases). It is not
a real ladder build — Theorycrafter never retrieves builds (that is the
Build Finder's job).

No camelCase aliases: like :class:`PobSnapshot` and the repo's
generator-side models, these serialize with their snake_case field
names and the frontend consumes them as-is. (camelCase aliases trip the
pydantic-mypy plugin on by-name construction — see the Step 38 notes.)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BudgetTier = Literal["starter", "mid", "endgame"]


class GemLink(BaseModel):
    """One active skill plus its recommended support gems (a 6-link)."""

    model_config = ConfigDict(frozen=True)

    skill: str
    supports: tuple[str, ...] = ()


class TreeMilestone(BaseModel):
    """One passive-tree milestone — a keystone, ascendancy notable, or
    a prose-only landmark when no node id resolves."""

    model_config = ConfigDict(frozen=True)

    label: str
    node_ids: tuple[int, ...] = ()
    priority: int = Field(ge=1, description="1 = allocate first, higher = later.")


class GearSlot(BaseModel):
    """Recommended bases + priority stats for one equipment slot."""

    model_config = ConfigDict(frozen=True)

    slot: str
    recommended_bases: tuple[str, ...] = ()
    priority_stats: tuple[str, ...] = ()
    budget_tier: BudgetTier


class BuildSkeleton(BaseModel):
    """A complete from-scratch build skeleton."""

    model_config = ConfigDict(frozen=True)

    class_name: str
    ascendancy: str
    core_skill: str
    links: tuple[GemLink, ...] = ()
    tree_milestones: tuple[TreeMilestone, ...] = ()
    gear_slots: tuple[GearSlot, ...] = ()
    budget_tier: BudgetTier
    content_focus: str
    rationale_it: str
    rationale_en: str
    pob_import_hint: str


__all__ = [
    "BudgetTier",
    "BuildSkeleton",
    "GearSlot",
    "GemLink",
    "TreeMilestone",
]
