"""Theorycrafter Build Generator v1 (Step 39).

`generate_build` produces a :class:`BuildSkeleton` **from scratch** from
vendored 3.28 data — never from the poe.ninja ladder (that boundary is
the permanent Finder-vs-Theorycrafter rule in CLAUDE.md).

Pipeline:
1. `extract_intent` — rule-based NL parse of the query → `BuildIntent`.
2. `resolve_archetype` — score the curated archetype catalogue, pick one.
3. Gem links — the archetype's core skill + canonical supports.
4. Tree milestones — keystones + ascendancy notables resolved against
   the vendored passive tree (`data/tree/3_28.json`).
5. Gear slots — recommended bases from `data/items/base_items.json`
   plus stable per-slot priority-stat conventions.
6. Rationale — the archetype's curated IT/EN prose + budget/focus copy.

No LLM. No HTTP. Synchronous and deterministic.
"""

from __future__ import annotations

from poe1_core.models.enums import ItemSlot
from poe1_shared.config import Settings
from poe1_shared.logging import get_logger

from ..gear.base_items import bases_for_slot
from ..intent import extract_intent
from ..tree import get_tree_data
from .archetypes import Archetype, resolve_archetype
from .models import BudgetTier, BuildSkeleton, GearSlot, GemLink, TreeMilestone

log = get_logger(__name__)


class TheoryError(RuntimeError):
    """Raised when generation cannot proceed (e.g. missing vendored data)."""


# Equipment slots the skeleton covers, in display order.
_ARMOUR_SLOTS: tuple[tuple[ItemSlot, str], ...] = (
    (ItemSlot.HELMET, "Helmet"),
    (ItemSlot.BODY_ARMOUR, "Body Armour"),
    (ItemSlot.GLOVES, "Gloves"),
    (ItemSlot.BOOTS, "Boots"),
)

# Defence archetype → the base-item tag that carries it.
_DEFENCE_TAG: dict[str, str] = {
    "es": "energy_shield",
    "evasion": "evasion",
    "life": "armour",
    "hybrid": "armour",
}

# Stable, build-agnostic priority-stat conventions per slot. These are
# PoE common knowledge, not per-build data.
_BASE_STATS: dict[str, tuple[str, ...]] = {
    "Helmet": ("vita o energy shield", "resistenze elementali"),
    "Body Armour": ("vita o energy shield", "resistenze elementali"),
    "Gloves": ("vita o energy shield", "resistenze elementali"),
    "Boots": ("vita o energy shield", "resistenze elementali", "velocita di movimento"),
    "Belt": ("vita", "resistenze elementali"),
    "Amulet": ("vita o energy shield", "resistenze elementali"),
    "Ring": ("vita", "resistenze elementali"),
    "Shield": ("vita o energy shield", "resistenze elementali"),
}


def _budget_band(drop_levels: list[int], tier: BudgetTier) -> slice:
    """Pick a drop-level band of bases for the budget tier."""
    n = len(drop_levels)
    if n <= 3:
        return slice(0, n)
    third = n // 3
    if tier == "starter":
        return slice(0, third)
    if tier == "endgame":
        return slice(n - third, n)
    return slice(third, 2 * third)


def _weapon_class(arch: Archetype) -> str:
    """Pick the weapon item_class that fits the archetype."""
    t = set(arch.tags)
    if "bow" in t:
        return "Bow"
    if "wand" in t:
        return "Wand"
    if "spell" in t:
        return "Wand"
    if "melee" in t:
        return "Two Hand Sword"
    return "Wand"


def _bases_for(item_class: str, tier: BudgetTier, *, limit: int = 3) -> tuple[str, ...]:
    """Recommended base names of *item_class* for the budget tier."""
    slot = {
        "Helmet": ItemSlot.HELMET,
        "Body Armour": ItemSlot.BODY_ARMOUR,
        "Gloves": ItemSlot.GLOVES,
        "Boots": ItemSlot.BOOTS,
        "Belt": ItemSlot.BELT,
        "Amulet": ItemSlot.AMULET,
        "Ring": ItemSlot.RING,
        "Shield": ItemSlot.WEAPON_OFFHAND,
    }.get(item_class, ItemSlot.WEAPON_MAIN)
    pool = [
        b
        for b in bases_for_slot(slot)
        if b.item_class == item_class or slot != ItemSlot.WEAPON_MAIN
    ]
    pool.sort(key=lambda b: b.drop_level or 0)
    if not pool:
        return ()
    band = pool[_budget_band([b.drop_level or 0 for b in pool], tier)]
    return tuple(b.name for b in band[:limit])


def _armour_bases(slot: ItemSlot, defence: str, tier: BudgetTier) -> tuple[str, ...]:
    """Recommended armour bases for a slot, filtered by defence type."""
    tag = _DEFENCE_TAG.get(defence, "armour")
    pool = [b for b in bases_for_slot(slot) if tag in b.tags]
    if not pool:
        pool = list(bases_for_slot(slot))
    pool.sort(key=lambda b: b.drop_level or 0)
    band = pool[_budget_band([b.drop_level or 0 for b in pool], tier)]
    return tuple(b.name for b in band[:3])


def _gear_slots(arch: Archetype, tier: BudgetTier) -> tuple[GearSlot, ...]:
    """Generate the gear-slot recommendations."""
    out: list[GearSlot] = []

    for slot_enum, slot_name in _ARMOUR_SLOTS:
        out.append(
            GearSlot(
                slot=slot_name,
                recommended_bases=_armour_bases(slot_enum, arch.defence, tier),
                priority_stats=_BASE_STATS[slot_name],
                budget_tier=tier,
            ),
        )

    for slot_name in ("Belt", "Amulet", "Ring"):
        out.append(
            GearSlot(
                slot=slot_name,
                recommended_bases=_bases_for(slot_name, tier),
                priority_stats=_BASE_STATS[slot_name],
                budget_tier=tier,
            ),
        )

    weapon_class = _weapon_class(arch)
    weapon_stat = {
        "physical": "danno fisico, velocita d'attacco, critico",
        "fire": "danno incantesimi/elementale, critico",
        "cold": "danno incantesimi/elementale, critico",
        "lightning": "danno incantesimi/elementale, critico",
        "chaos": "danno nel tempo / caos, critico",
    }.get(arch.damage_type, "danno principale, critico")
    out.append(
        GearSlot(
            slot=f"Weapon ({weapon_class})",
            recommended_bases=_bases_for(weapon_class, tier),
            priority_stats=(weapon_stat, "+# livelli alle gemme socketate (per caster)"),
            budget_tier=tier,
        ),
    )

    # A shield only fits a one-handed setup.
    if weapon_class not in ("Bow",) and not weapon_class.startswith("Two Hand"):
        out.append(
            GearSlot(
                slot="Shield",
                recommended_bases=_bases_for("Shield", tier),
                priority_stats=_BASE_STATS["Shield"],
                budget_tier=tier,
            ),
        )

    return tuple(out)


def _tree_milestones(arch: Archetype) -> tuple[TreeMilestone, ...]:
    """Generate ordered passive-tree milestones from vendored tree data."""
    td = get_tree_data()
    out: list[TreeMilestone] = [
        TreeMilestone(
            label=f"Area iniziale di {arch.class_name} — vita/difese di base",
            node_ids=(),
            priority=1,
        ),
    ]

    # Keystones — resolved to real node ids when found.
    for kname in arch.keystones:
        match = next(
            (n for n in td.nodes_by_id.values() if n.is_keystone and n.name == kname),
            None,
        )
        out.append(
            TreeMilestone(
                label=f"Keystone: {kname}",
                node_ids=(match.id,) if match else (),
                priority=2,
            ),
        )

    # Ascendancy notables for the chosen ascendancy.
    asc_nodes = [
        n
        for n in td.nodes_by_id.values()
        if n.ascendancy_name == arch.ascendancy and n.is_notable and n.name
    ]
    asc_nodes.sort(key=lambda n: n.id)
    if asc_nodes:
        out.append(
            TreeMilestone(
                label=(
                    f"Ascendancy {arch.ascendancy}: "
                    + ", ".join(n.name or "?" for n in asc_nodes[:4])
                ),
                node_ids=tuple(n.id for n in asc_nodes[:4]),
                priority=3,
            ),
        )
    else:
        out.append(
            TreeMilestone(
                label=f"Ascendancy: {arch.ascendancy} (4 punti dai Labyrinth)",
                node_ids=(),
                priority=3,
            ),
        )

    out.sort(key=lambda m: m.priority)
    return tuple(out)


_CONTENT_LABEL_IT: dict[str, str] = {
    "mapping": "mappatura veloce",
    "bossing": "boss singoli",
    "allcontent": "tutti i contenuti",
    "league": "meccaniche di lega",
}
_CONTENT_LABEL_EN: dict[str, str] = {
    "mapping": "fast mapping",
    "bossing": "single-target bossing",
    "allcontent": "all content",
    "league": "league mechanics",
}
_BUDGET_LABEL_IT: dict[str, str] = {
    "starter": "budget da inizio lega",
    "mid": "budget medio",
    "endgame": "budget endgame",
}
_BUDGET_LABEL_EN: dict[str, str] = {
    "starter": "league-start budget",
    "mid": "mid budget",
    "endgame": "endgame budget",
}


async def generate_build(
    query: str,
    *,
    settings: Settings,
    budget_tier: BudgetTier = "mid",
    content_focus: str | None = None,
) -> BuildSkeleton:
    """Generate a from-scratch build skeleton for *query*."""
    intent = await extract_intent(query, settings=settings)
    arch = resolve_archetype(intent)

    focus = (content_focus or arch.content).strip() or arch.content
    links = (GemLink(skill=arch.skill_name, supports=arch.canonical_supports),)
    milestones = _tree_milestones(arch)
    gear = _gear_slots(arch, budget_tier)

    focus_it = _CONTENT_LABEL_IT.get(focus, focus)
    focus_en = _CONTENT_LABEL_EN.get(focus, focus)
    rationale_it = (
        f"{arch.rationale_it} Configurazione consigliata: {_BUDGET_LABEL_IT[budget_tier]}, "
        f"orientata a {focus_it}. Questo scheletro e generato dai dati ufficiali di "
        "PoE 3.28 — non e copiato da un giocatore reale."
    )
    rationale_en = (
        f"{arch.rationale_en} Recommended setup: {_BUDGET_LABEL_EN[budget_tier]}, "
        f"geared towards {focus_en}. This skeleton is generated from official "
        "PoE 3.28 data — it is not copied from a real player."
    )
    pob_hint = (
        f"IT: Apri Path of Building -> New -> classe {arch.class_name}, ascendancy "
        f"{arch.ascendancy} -> alloca i nodi nell'ordine dei milestone -> socket "
        f"{arch.skill_name} con i support indicati. / EN: Open Path of Building -> "
        f"New -> class {arch.class_name}, ascendancy {arch.ascendancy} -> allocate "
        f"the milestone nodes in order -> socket {arch.skill_name} with the listed "
        "supports."
    )

    skeleton = BuildSkeleton(
        class_name=arch.class_name,
        ascendancy=arch.ascendancy,
        core_skill=arch.skill_name,
        links=links,
        tree_milestones=milestones,
        gear_slots=gear,
        budget_tier=budget_tier,
        content_focus=focus,
        rationale_it=rationale_it,
        rationale_en=rationale_en,
        pob_import_hint=pob_hint,
    )
    log.info(
        "theory_generate_ok",
        archetype=arch.skill_id,
        class_name=arch.class_name,
        ascendancy=arch.ascendancy,
        budget=budget_tier,
    )
    return skeleton


__all__ = ["TheoryError", "generate_build"]
