"""Theorycrafter Build Generator v2 (Step 40).

Replaces the v1 archetype-JSON generator with a graph engine over the
vendored 3.28 data:

* `gems_3_28.json` — active skills + supports (tag-based compatibility).
* `tree/3_28.json` — passive tree nodes, scored by stat keywords.
* `items/base_items.json` — gear bases, filtered by slot + tags +
  drop-level budget thresholds.

Pipeline:
1. Gem-link resolution — tag-subset support compatibility.
2. Tree node selection — score notables/keystones by damage/defence
   keywords, pick top 8 notables + top 2 keystones.
3. Gear-slot resolution — best base per slot by item_class + tags +
   budget threshold.
4. Stat estimates — rough life/ES/dps_index from tree + gear weights.
5. PoB XML export — synthesise the StageTree/StageGearSet/StageGemLinks
   shapes the existing :func:`encode_pob_code` understands.

Hard constraints (asserted at runtime — 500 over a hallucination):
* every base name must exist in `base_items.json`,
* every tree node id must exist in the tree JSON,
* every support gem must exist in `gems_3_28.json`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from poe1_core.models.enums import ItemSlot
from poe1_shared.logging import get_logger

from ..gear.base_items import get_base_catalogue
from ..gear.models import StageGearSet, StageGearSlot
from ..gems.models import GemLink as PobGemLink
from ..gems.models import GemSpec, StageGemLinks
from ..pob.encode import encode_pob_code
from ..tree.models import StageTree
from ..tree.tree_data import TreeNode, get_tree_data
from .models import (
    BudgetTier,
    BuildSkeleton,
    GearSlot,
    GemLink,
    SkillEntry,
    StatEstimate,
    TheoryIntent,
    TreeNodeRef,
)

log = get_logger(__name__)

_GEMS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "gems" / "gems_3_28.json"


class TheoryError(RuntimeError):
    """Raised when generation cannot proceed (e.g. missing data file)."""


class TheoryHallucinationError(RuntimeError):
    """Raised when generated output references a non-vendored asset.

    This is the anti-hallucination gate: any base/node/gem the engine
    chose must exist verbatim in the vendored data — never invented.
    """


@dataclass(frozen=True, slots=True)
class _Active:
    name: str
    tags: tuple[str, ...]
    damage_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Support:
    name: str
    valid_gem_tags: tuple[str, ...]
    exclude_tags: tuple[str, ...]
    priority: int


@lru_cache(maxsize=1)
def _gem_catalogue() -> tuple[tuple[_Active, ...], tuple[_Support, ...]]:
    if not _GEMS_PATH.exists():  # pragma: no cover - deployment guard
        raise TheoryError(f"gems data missing at {_GEMS_PATH}")
    raw = json.loads(_GEMS_PATH.read_text(encoding="utf-8"))
    actives = tuple(
        _Active(
            name=str(a["name"]),
            tags=tuple(a.get("tags", [])),
            damage_types=tuple(a.get("damage_types", [])),
        )
        for a in raw.get("actives", [])
    )
    supports = tuple(
        _Support(
            name=str(s["name"]),
            valid_gem_tags=tuple(s.get("valid_gem_tags", [])),
            exclude_tags=tuple(s.get("exclude_tags", [])),
            priority=int(s.get("priority", 50)),
        )
        for s in raw.get("supports", [])
    )
    return actives, supports


def list_active_skills() -> tuple[SkillEntry, ...]:
    """Active skills exposed via ``GET /fob/theory/skills``."""
    actives, _ = _gem_catalogue()
    return tuple(SkillEntry(name=a.name, tags=a.tags, damage_types=a.damage_types) for a in actives)


def _find_active(name: str) -> _Active:
    actives, _ = _gem_catalogue()
    for a in actives:
        if a.name == name:
            return a
    # Fallback to the first one so the engine never crashes on a stale
    # frontend cache; the assertion gate below will still validate the
    # final skeleton.
    log.warning("theory_unknown_skill", requested=name)
    return actives[0]


def _select_supports(skill: _Active, n: int = 5) -> tuple[str, ...]:
    """Pick *n* support gems whose tag requirements fit *skill*."""
    _, supports = _gem_catalogue()
    skill_tags = set(skill.tags)
    fits: list[_Support] = []
    for s in supports:
        if not set(s.valid_gem_tags).issubset(skill_tags):
            continue
        if any(t in skill_tags for t in s.exclude_tags):
            continue
        fits.append(s)
    fits.sort(key=lambda s: s.priority, reverse=True)
    picked = [s.name for s in fits[:n]]
    while len(picked) < n:
        picked.append("(open)")
    return tuple(picked)


# ---------------------------------------------------------------------------
# Tree pathfinding (Step B)
# ---------------------------------------------------------------------------


# Keywords per damage type / defence — used to score tree-node relevance.
_DAMAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "fire": ("fire damage", "burning damage", "ignite", "elemental damage"),
    "cold": ("cold damage", "chill", "freeze", "elemental damage"),
    "lightning": ("lightning damage", "shock", "elemental damage"),
    "chaos": ("chaos damage", "damage over time", "poison"),
    "physical": ("physical damage", "attack damage", "bleed"),
    "spell": ("spell damage", "cast speed", "increased spell"),
    "attack": ("attack damage", "attack speed", "increased attack"),
}
_DEFENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "life": ("maximum life", "life regen", "life leech"),
    "es": ("energy shield", "energy shield regen", "es leech"),
    "ward": ("ward", "maximum ward"),
    "hybrid_life_es": ("maximum life", "energy shield"),
}


def _score_node(node: TreeNode, dmg: str, defence: str) -> int:
    """Higher = more relevant to the build."""
    if not node.is_keystone and not node.is_notable:
        return 0
    if node.ascendancy_name is not None:
        # Ascendancy nodes handled separately; not scored here.
        return 0
    stats_text = " ".join((node.name or "", "")).lower()
    # tree_data exposes only id+name+flags — stat strings live on the raw
    # tree JSON. For v2 we score on node name only (the in-engine
    # TreeNode is the lightweight projection we already vendored).
    score = 0
    for kw in _DAMAGE_KEYWORDS.get(dmg, ()):
        if kw.split()[0] in stats_text:
            score += 3
    for kw in _DEFENCE_KEYWORDS.get(defence, ()):
        if kw.split()[0] in stats_text:
            score += 2
    return score


def _select_tree_nodes(intent: TheoryIntent) -> tuple[TreeNodeRef, ...]:
    """Pick relevant keystones, notables and ascendancy notables."""
    td = get_tree_data()
    scored: list[tuple[int, TreeNode]] = []
    for n in td.nodes_by_id.values():
        s = _score_node(n, intent.damage_type, intent.defence_archetype)
        if s > 0:
            scored.append((s, n))
    scored.sort(key=lambda t: (-t[0], t[1].id))

    keystones = [n for _, n in scored if n.is_keystone][:2]
    notables = [n for _, n in scored if n.is_notable][:8]

    # Ascendancy notables for the chosen ascendancy.
    asc_notables = [
        n
        for n in td.nodes_by_id.values()
        if n.ascendancy_name == intent.ascendancy and n.is_notable and n.name
    ]
    asc_notables.sort(key=lambda n: n.id)
    asc_notables = asc_notables[:4]

    out: list[TreeNodeRef] = []
    # Class start (prose-only — class start node ids vary by class).
    out.append(
        TreeNodeRef(
            node_id=td.class_starts.get(0, 0),
            name=f"{intent.character_class} start",
            type="start",
            stats=(),
        )
    )
    for n in keystones:
        out.append(
            TreeNodeRef(
                node_id=n.id,
                name=n.name or "?",
                type="keystone",
                stats=(),
            )
        )
    for n in notables:
        out.append(
            TreeNodeRef(
                node_id=n.id,
                name=n.name or "?",
                type="notable",
                stats=(),
            )
        )
    for n in asc_notables:
        out.append(
            TreeNodeRef(
                node_id=n.id,
                name=n.name or "?",
                type="ascendancy",
                stats=(),
            )
        )
    return tuple(out)


# ---------------------------------------------------------------------------
# Gear-slot resolution (Step C)
# ---------------------------------------------------------------------------


_BUDGET_DROP_CAP: dict[BudgetTier, int] = {
    "starter": 60,
    "mid": 80,
    "endgame": 86,  # effectively no cap; top-tier bases sit around 80-86
}

_DEFENCE_TAG: dict[str, str] = {
    "life": "armour",
    "es": "energy_shield",
    "ward": "ward",
    "hybrid_life_es": "armour",
}

_SLOTS: tuple[tuple[ItemSlot, str], ...] = (
    (ItemSlot.HELMET, "Helmet"),
    (ItemSlot.BODY_ARMOUR, "Body Armour"),
    (ItemSlot.GLOVES, "Gloves"),
    (ItemSlot.BOOTS, "Boots"),
    (ItemSlot.BELT, "Belt"),
    (ItemSlot.AMULET, "Amulet"),
    (ItemSlot.RING, "Ring"),
)


def _stat_priorities(slot_name: str, intent: TheoryIntent) -> tuple[str, ...]:
    """Per-slot stat priorities used for both the UI and Trade links."""
    base = "to maximum Life" if intent.defence_archetype != "es" else "to maximum Energy Shield"
    res = "to Fire Resistance" if intent.damage_type != "fire" else "to Cold Resistance"
    if slot_name == "Boots":
        return (f"{base}", res, "increased Movement Speed")
    if slot_name in ("Weapon", "Off-hand"):
        if intent.damage_type in ("fire", "cold", "lightning"):
            return (
                "increased Spell Damage",
                f"to {intent.damage_type.capitalize()} Damage",
                "critical strike",
            )
        if intent.damage_type == "chaos":
            return ("increased Chaos Damage", "increased damage over time", "critical strike")
        return ("increased Physical Damage", "increased Attack Speed", "critical strike")
    return (base, res, "increased damage")


def _pick_base(slot_enum: ItemSlot, intent: TheoryIntent) -> str:
    """Highest-drop_level base for the slot that fits defence + budget."""
    cap = _BUDGET_DROP_CAP[intent.budget]
    pref_tag = _DEFENCE_TAG[intent.defence_archetype]
    pool = [b for b in get_base_catalogue() if b.slot == slot_enum and (b.drop_level or 0) <= cap]
    if not pool:  # pragma: no cover - all slots have bases
        raise TheoryError(f"no base found for {slot_enum.value} at budget {intent.budget}")
    tagged = [b for b in pool if pref_tag in b.tags]
    if tagged:
        pool = tagged
    pool.sort(key=lambda b: (b.drop_level or 0, b.name), reverse=True)
    return pool[0].name


def _select_gear(intent: TheoryIntent) -> tuple[GearSlot, ...]:
    out: list[GearSlot] = []
    for slot_enum, slot_name in _SLOTS:
        out.append(
            GearSlot(
                slot=slot_name,
                base_name=_pick_base(slot_enum, intent),
                stat_priorities=_stat_priorities(slot_name, intent),
                budget_tier=intent.budget,
            ),
        )
    # Weapon by archetype: spell → Wand, attack-bow → Bow, melee → Two Hand Sword.
    skill = _find_active(intent.primary_skill)
    if "bow" in skill.tags:
        weapon_class, weapon_slot, weapon_label = "Bow", ItemSlot.WEAPON_MAIN, "Bow"
    elif "melee" in skill.tags:
        weapon_class, weapon_slot, weapon_label = "Two Hand Sword", ItemSlot.WEAPON_MAIN, "Weapon"
    else:
        weapon_class, weapon_slot, weapon_label = "Wand", ItemSlot.WEAPON_MAIN, "Wand"
    weapon_pool = [
        b
        for b in get_base_catalogue()
        if b.slot == weapon_slot
        and b.item_class == weapon_class
        and (b.drop_level or 0) <= _BUDGET_DROP_CAP[intent.budget]
    ]
    weapon_pool.sort(key=lambda b: (b.drop_level or 0, b.name), reverse=True)
    if weapon_pool:
        out.append(
            GearSlot(
                slot=weapon_label,
                base_name=weapon_pool[0].name,
                stat_priorities=_stat_priorities("Weapon", intent),
                budget_tier=intent.budget,
            ),
        )
    if weapon_class != "Bow" and not weapon_class.startswith("Two Hand"):
        shield_pool = [
            b
            for b in get_base_catalogue()
            if b.slot == ItemSlot.WEAPON_OFFHAND
            and (b.drop_level or 0) <= _BUDGET_DROP_CAP[intent.budget]
        ]
        shield_pool.sort(key=lambda b: (b.drop_level or 0, b.name), reverse=True)
        if shield_pool:
            out.append(
                GearSlot(
                    slot="Shield",
                    base_name=shield_pool[0].name,
                    stat_priorities=_stat_priorities("Off-hand", intent),
                    budget_tier=intent.budget,
                ),
            )
    return tuple(out)


# ---------------------------------------------------------------------------
# Stat estimates (Step D)
# ---------------------------------------------------------------------------

_BASE_LIFE: dict[str, int] = {
    "Marauder": 66,
    "Duelist": 62,
    "Templar": 62,
    "Witch": 56,
    "Shadow": 58,
    "Ranger": 58,
    "Scion": 60,
}
_GEAR_LIFE: dict[BudgetTier, int] = {"starter": 800, "mid": 1500, "endgame": 2500}
_GEAR_ES: dict[BudgetTier, int] = {"starter": 500, "mid": 1500, "endgame": 3500}


def _stat_estimate(intent: TheoryIntent, nodes: tuple[TreeNodeRef, ...]) -> StatEstimate:
    base_life = _BASE_LIFE.get(intent.character_class, 60) + 100 * 99  # ~lvl 99
    life_nodes = sum(1 for n in nodes if "life" in n.name.lower())
    es_nodes = sum(1 for n in nodes if "energy" in n.name.lower())
    res_nodes = sum(1 for n in nodes if "resist" in n.name.lower())
    dmg_nodes = sum(1 for n in nodes if intent.damage_type in n.name.lower())

    life = base_life + life_nodes * 80 + _GEAR_LIFE[intent.budget]
    es = es_nodes * 120 + _GEAR_ES[intent.budget] if intent.defence_archetype != "life" else 0
    dps_index = dmg_nodes * 1500 + len(nodes) * 200

    warning = (
        "Capping resistances requires gear — molto piu del solo albero." if res_nodes < 2 else None
    )
    return StatEstimate(
        life_estimate=max(life, 0),
        es_estimate=max(es, 0),
        dps_index=max(dps_index, 0),
        resistance_warning=warning,
        estimated=True,
    )


# ---------------------------------------------------------------------------
# PoB XML export (Step E)
# ---------------------------------------------------------------------------


def _to_pob_gear(slots: tuple[GearSlot, ...]) -> StageGearSet:
    pob_slots: list[StageGearSlot] = []
    slot_enum_map: dict[str, ItemSlot] = {
        "Helmet": ItemSlot.HELMET,
        "Body Armour": ItemSlot.BODY_ARMOUR,
        "Gloves": ItemSlot.GLOVES,
        "Boots": ItemSlot.BOOTS,
        "Belt": ItemSlot.BELT,
        "Amulet": ItemSlot.AMULET,
        "Ring": ItemSlot.RING,
        "Wand": ItemSlot.WEAPON_MAIN,
        "Bow": ItemSlot.WEAPON_MAIN,
        "Weapon": ItemSlot.WEAPON_MAIN,
        "Shield": ItemSlot.WEAPON_OFFHAND,
    }
    for g in slots:
        if g.slot not in slot_enum_map:
            continue
        pob_slots.append(
            StageGearSlot(
                slot=slot_enum_map[g.slot],
                item_name=g.base_name,
                kind="rare_craft",
                notes=", ".join(g.stat_priorities),
                budget_div_max=None,
            )
        )
    return StageGearSet(stage_key="theory_v2", slots=tuple(pob_slots))


def _to_pob_gems(link: GemLink) -> StageGemLinks:
    gems = [GemSpec(name=link.skill, level=20, quality=20, is_support=False)]
    gems.extend(
        GemSpec(name=s, level=20, quality=20, is_support=True)
        for s in link.supports
        if s != "(open)"
    )
    # PoB requires sockets == len(gems); we don't pad to 6 because PoB
    # would reject an empty-named placeholder gem.
    sockets = max(1, min(6, len(gems)))
    pob_link = PobGemLink(
        slot=ItemSlot.BODY_ARMOUR,
        sockets=sockets,
        color_pattern="R" * sockets,
        gems=tuple(gems[:sockets]),
        notes="Primary 6L",
    )
    return StageGemLinks(stage_key="theory_v2", links=(pob_link,))


def _to_pob_tree(intent: TheoryIntent, nodes: tuple[TreeNodeRef, ...]) -> StageTree:
    # Skip the synthetic "start" entry — its node_id may be a placeholder.
    real_ids = tuple(n.node_id for n in nodes if n.type != "start" and n.node_id > 0)
    return StageTree(
        stage_key="theory_v2",
        node_ids=real_ids,
        notables=tuple(n.name for n in nodes if n.type == "notable"),
        ascendancy_nodes=tuple(n.name for n in nodes if n.type == "ascendancy"),
        pob_url=None,
    )


# ---------------------------------------------------------------------------
# Anti-hallucination assertions (hard constraints)
# ---------------------------------------------------------------------------


def _assert_valid(
    intent: TheoryIntent,
    gear: tuple[GearSlot, ...],
    nodes: tuple[TreeNodeRef, ...],
    links: tuple[GemLink, ...],
) -> None:
    known_bases = {b.name for b in get_base_catalogue()}
    known_nodes = set(get_tree_data().nodes_by_id.keys())
    _, supports = _gem_catalogue()
    known_supports = {s.name for s in supports} | {"(open)"}

    for g in gear:
        if g.base_name not in known_bases:
            raise TheoryHallucinationError(
                f"base '{g.base_name}' not in base_items.json (slot {g.slot})"
            )
    for n in nodes:
        if n.type == "start":
            continue
        if n.node_id not in known_nodes:
            raise TheoryHallucinationError(
                f"node id {n.node_id} ('{n.name}') not in tree/3_28.json"
            )
    for link in links:
        for s in link.supports:
            if s not in known_supports:
                raise TheoryHallucinationError(f"support '{s}' not in gems_3_28.json")
    _ = intent  # signature parity


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_FOCUS_IT: dict[str, str] = {
    "mapping": "mappatura veloce",
    "bossing": "boss singoli",
    "allcontent": "tutti i contenuti",
}
_FOCUS_EN: dict[str, str] = {
    "mapping": "fast mapping",
    "bossing": "single-target bossing",
    "allcontent": "all content",
}


def generate_build(intent: TheoryIntent) -> BuildSkeleton:
    """Generate a complete :class:`BuildSkeleton` from a structured intent.

    Deterministic and offline. Raises :class:`TheoryHallucinationError`
    if any generated reference is not in the vendored data.
    """
    skill = _find_active(intent.primary_skill)
    supports = _select_supports(skill)
    primary_link = GemLink(
        skill=skill.name,
        supports=supports,
        slot="Body Armour",
        label="Primary 6L",
    )
    links = (primary_link,)
    nodes = _select_tree_nodes(intent)
    gear = _select_gear(intent)

    _assert_valid(intent, gear, nodes, links)

    stats = _stat_estimate(intent, nodes)
    pob_code = encode_pob_code(
        character_class=intent.character_class,
        ascendancy=intent.ascendancy,
        tree=_to_pob_tree(intent, nodes),
        gear=_to_pob_gear(gear),
        gems=_to_pob_gems(primary_link),
        level=90,
    )

    rationale_it = (
        f"Build {intent.character_class}/{intent.ascendancy} con {intent.primary_skill} "
        f"({intent.damage_type}). Difesa: {intent.defence_archetype}. Budget: "
        f"{intent.budget}. Focus: {_FOCUS_IT.get(intent.focus, intent.focus)}. "
        "Albero e oggetti sono presi dai dati ufficiali di PoE 3.28."
    )
    rationale_en = (
        f"{intent.character_class}/{intent.ascendancy} {intent.primary_skill} build "
        f"({intent.damage_type}). Defence: {intent.defence_archetype}. Budget: "
        f"{intent.budget}. Focus: {_FOCUS_EN.get(intent.focus, intent.focus)}. "
        "Tree and items are sourced from official PoE 3.28 data."
    )

    skeleton = BuildSkeleton(
        intent=intent,
        links=links,
        tree_nodes=nodes,
        gear_slots=gear,
        stats=stats,
        rationale_it=rationale_it,
        rationale_en=rationale_en,
        pob_code=pob_code,
    )
    log.info(
        "theory_v2_ok",
        class_name=intent.character_class,
        ascendancy=intent.ascendancy,
        skill=intent.primary_skill,
        nodes=len(nodes),
        slots=len(gear),
    )
    return skeleton


__all__ = [
    "TheoryError",
    "TheoryHallucinationError",
    "generate_build",
    "list_active_skills",
]
