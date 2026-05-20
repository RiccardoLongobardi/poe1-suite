"""Unit tests for the Theorycrafter Build Generator (Step 39).

The generator is rule-based, deterministic and offline — no ladder, no
LLM. Tests construct ``Settings(anthropic_api_key=None)`` so intent
extraction stays rule-based.

Tests are ``async def`` — the repo runs pytest-asyncio in ``auto`` mode,
so the generator coroutine is awaited on the managed loop (a bare
``asyncio.run`` would spawn an extra loop and leak its self-pipe).
"""

from __future__ import annotations

from poe1_fob.gear.base_items import get_base_catalogue
from poe1_fob.theory import BuildSkeleton, generate_build
from poe1_fob.theory.models import BudgetTier
from poe1_shared.config import Settings


async def _gen(
    query: str,
    *,
    budget_tier: BudgetTier = "mid",
    content_focus: str | None = None,
) -> BuildSkeleton:
    settings = Settings(anthropic_api_key=None)
    return await generate_build(
        query,
        settings=settings,
        budget_tier=budget_tier,
        content_focus=content_focus,
    )


async def test_generate_returns_build_skeleton() -> None:
    sk = await _gen("RF tank per tutti i contenuti")
    assert isinstance(sk, BuildSkeleton)
    assert sk.class_name
    assert sk.ascendancy
    assert sk.core_skill
    assert sk.links and sk.links[0].supports
    assert sk.tree_milestones
    assert sk.gear_slots
    assert sk.rationale_it and sk.rationale_en
    assert sk.pob_import_hint


async def test_generate_known_archetype() -> None:
    sk = await _gen("Elementalist Fireball mapping")
    assert sk.class_name == "Witch"
    assert sk.ascendancy == "Elementalist"
    assert "Fire" in sk.core_skill


async def test_generate_unknown_query_fallback() -> None:
    # Garbage in → still a coherent skeleton (fallback archetype, no crash).
    sk = await _gen("asdfqwerzxcv 12345")
    assert isinstance(sk, BuildSkeleton)
    assert sk.core_skill
    assert sk.gear_slots


async def test_generate_all_budget_tiers() -> None:
    bases: dict[str, tuple[str, ...]] = {}
    for tier in ("starter", "mid", "endgame"):
        sk = await _gen("Elementalist Fireball mapping", budget_tier=tier)
        # Every gear slot is tagged with the requested tier.
        assert all(g.budget_tier == tier for g in sk.gear_slots)
        bases[tier] = tuple(b for g in sk.gear_slots for b in g.recommended_bases)
    # Starter and endgame must not produce an identical base list.
    assert bases["starter"] != bases["endgame"]


async def test_generate_gear_slots_use_known_bases() -> None:
    known = {b.name for b in get_base_catalogue()}
    sk = await _gen("Cyclone Slayer endgame", budget_tier="endgame")
    for g in sk.gear_slots:
        for base in g.recommended_bases:
            assert base in known, f"{base} not in base_items.json"


async def test_generate_tree_milestones_have_priority_order() -> None:
    sk = await _gen("Spark Inquisitor")
    priorities = [m.priority for m in sk.tree_milestones]
    assert priorities == sorted(priorities)
    # The first milestone is always the class start area.
    assert sk.tree_milestones[0].priority == 1
