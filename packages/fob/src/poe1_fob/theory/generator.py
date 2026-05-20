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
    "life": ("maximum life", "life regen", "life leech", "armour", "evasion"),
    "es": ("energy shield", "energy shield regen", "es leech"),
    "ward": ("ward", "maximum ward"),
    "hybrid_life_es": ("maximum life", "energy shield"),
}

# Mirror of `pob.encode._CLASS_ID` — duplicated here to avoid importing
# a private helper. PoB's class enum is stable across leagues.
_CLASS_ID: dict[str, int] = {
    "Scion": 0,
    "Marauder": 1,
    "Ranger": 2,
    "Witch": 3,
    "Duelist": 4,
    "Templar": 5,
    "Shadow": 6,
}


def _score_node(node: TreeNode, dmg: str, defence: str) -> int:
    """Higher = more relevant to the build.

    Scores both the node name and its `stats` array (the human-readable
    mod lines from the raw tree JSON — most notables are named generic
    things like "Acrobatics" and their relevance comes from the stats).
    """
    if not node.is_keystone and not node.is_notable:
        return 0
    if node.ascendancy_name is not None:
        # Ascendancy nodes are handled separately.
        return 0
    text_parts: list[str] = [node.name or ""]
    text_parts.extend(node.stats)
    stats_text = " ".join(text_parts).lower()
    score = 0
    for kw in _DAMAGE_KEYWORDS.get(dmg, ()):
        if kw in stats_text:
            score += 3
    for kw in _DEFENCE_KEYWORDS.get(defence, ()):
        if kw in stats_text:
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
    # Class start — use the real class index, not always Scion (0).
    class_idx = _CLASS_ID.get(intent.character_class, 0)
    start_id = td.class_starts.get(class_idx, 0)
    out.append(
        TreeNodeRef(
            node_id=start_id,
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
    """Per-slot stat priorities — English PoE mod stems.

    Phrases match the keys in :data:`_AFFIX_VALUES` so the same list
    drives the UI badges, Trade links and the simulated PoB affix lines.
    """
    base = "to maximum Life" if intent.defence_archetype != "es" else "to maximum Energy Shield"
    res = "to Fire Resistance" if intent.damage_type != "fire" else "to Cold Resistance"
    if slot_name == "Boots":
        return (base, res, "Movement Speed")
    if slot_name in ("Weapon", "Off-hand"):
        if intent.damage_type in ("fire", "cold", "lightning"):
            return ("increased Spell Damage", res, "critical strike")
        if intent.damage_type == "chaos":
            return ("increased Chaos Damage", "increased damage", "critical strike")
        return ("increased Physical Damage", "Attack Speed", "critical strike")
    return (base, res, "increased damage")


# Stat keyword → (starter, mid, endgame) value. The keyword is matched
# as a substring against each entry in `stat_priorities`; first hit
# wins. Values are intentionally fixed (not rolled) — the build is
# generated, not real loot.
_AFFIX_VALUES: tuple[tuple[str, str, str, str], ...] = (
    ("maximum Life", "+60 to maximum Life", "+90 to maximum Life", "+120 to maximum Life"),
    (
        "maximum Energy Shield",
        "+50 to maximum Energy Shield",
        "+80 to maximum Energy Shield",
        "+110 to maximum Energy Shield",
    ),
    (
        "Fire Resistance",
        "+30% to Fire Resistance",
        "+40% to Fire Resistance",
        "+45% to Fire Resistance",
    ),
    (
        "Cold Resistance",
        "+30% to Cold Resistance",
        "+40% to Cold Resistance",
        "+45% to Cold Resistance",
    ),
    (
        "Lightning Resistance",
        "+30% to Lightning Resistance",
        "+40% to Lightning Resistance",
        "+45% to Lightning Resistance",
    ),
    (
        "increased Spell Damage",
        "15% increased Spell Damage",
        "25% increased Spell Damage",
        "40% increased Spell Damage",
    ),
    (
        "increased Physical Damage",
        "15% increased Physical Damage",
        "25% increased Physical Damage",
        "40% increased Physical Damage",
    ),
    (
        "increased Chaos Damage",
        "15% increased Chaos Damage",
        "25% increased Chaos Damage",
        "40% increased Chaos Damage",
    ),
    ("increased damage", "15% increased Damage", "25% increased Damage", "40% increased Damage"),
    (
        "Movement Speed",
        "20% increased Movement Speed",
        "25% increased Movement Speed",
        "30% increased Movement Speed",
    ),
    (
        "critical strike",
        "25% increased Critical Strike Chance",
        "35% increased Critical Strike Chance",
        "50% increased Critical Strike Chance",
    ),
    (
        "Attack Speed",
        "10% increased Attack Speed",
        "14% increased Attack Speed",
        "18% increased Attack Speed",
    ),
)

_BUDGET_COL: dict[BudgetTier, int] = {"starter": 1, "mid": 2, "endgame": 3}


def _affix_line(priority: str, budget: BudgetTier) -> str | None:
    """Pick a simulated affix line for a stat priority + budget tier."""
    col = _BUDGET_COL[budget]
    for kw, *vals in _AFFIX_VALUES:
        if kw.lower() in priority.lower():
            return vals[col - 1]
    return None


def _theory_item_body(
    slot_name: str,
    base_name: str,
    stat_priorities: tuple[str, ...],
    budget: BudgetTier,
) -> str:
    """Multi-line PoB item body — Rarity: RARE + base + simulated affixes."""
    lines = [
        "Rarity: RARE",
        f"Theorycrafted {slot_name}",
        base_name,
        "Implicits: 0",
    ]
    for p in stat_priorities:
        affix = _affix_line(p, budget)
        if affix:
            lines.append(affix)
    return "\n".join(lines)


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
    out.extend(_select_flasks(intent))
    out.extend(_select_jewels(intent))
    return tuple(out)


# ---------------------------------------------------------------------------
# Flasks & jewels (Bug 4 fix)
# ---------------------------------------------------------------------------


def _verify_base(name: str, fallback: str) -> str:
    """Return *name* if it exists in base_items.json, else *fallback*."""
    known = {b.name for b in get_base_catalogue()}
    return name if name in known else fallback


def _select_flasks(intent: TheoryIntent) -> tuple[GearSlot, ...]:
    """5 flask slots — life/mana, mobility, defence, utility, resistance."""
    skill = _find_active(intent.primary_skill)
    is_es = intent.defence_archetype == "es"
    is_melee = "melee" in skill.tags
    is_bow = "bow" in skill.tags
    is_chaos = intent.damage_type == "chaos"

    flask_1 = _verify_base(
        "Eternal Mana Flask" if is_es else "Divine Life Flask", "Divine Life Flask"
    )
    flask_2 = _verify_base("Quicksilver Flask", "Quicksilver Flask")
    if is_bow:
        flask_3 = _verify_base("Jade Flask", "Quartz Flask")
    elif is_melee:
        flask_3 = _verify_base("Granite Flask", "Basalt Flask")
    else:
        flask_3 = _verify_base("Sulphur Flask", "Quartz Flask")
    if is_chaos:
        flask_4 = _verify_base("Amethyst Flask", "Diamond Flask")
    elif "physical" in skill.tags:
        flask_4 = _verify_base("Silver Flask", "Diamond Flask")
    else:
        flask_4 = _verify_base("Diamond Flask", "Quartz Flask")
    flask_5 = _verify_base("Bismuth Flask", "Ruby Flask")

    bases = (flask_1, flask_2, flask_3, flask_4, flask_5)
    notes = (
        ("Increased Life Recovery",),
        ("Increased Duration",),
        ("Reduced Charges Used",),
        ("Increased Charges Gained",),
        ("Reduced Charges Used",),
    )
    return tuple(
        GearSlot(
            slot=f"Flask {i + 1}",
            base_name=bases[i],
            stat_priorities=notes[i],
            budget_tier=intent.budget,
        )
        for i in range(5)
    )


def _select_jewels(intent: TheoryIntent) -> tuple[GearSlot, ...]:
    """2 jewel slots — Crimson (life) / Cobalt (ES, spell) / Viridian (dex)."""
    skill = _find_active(intent.primary_skill)
    if intent.defence_archetype == "es" or "spell" in skill.tags:
        jewel_base = _verify_base("Cobalt Jewel", "Crimson Jewel")
    elif "bow" in skill.tags or intent.defence_archetype == "ward":
        jewel_base = _verify_base("Viridian Jewel", "Crimson Jewel")
    else:
        jewel_base = _verify_base("Crimson Jewel", "Cobalt Jewel")
    priorities = ("to maximum Life", "increased damage")
    return tuple(
        GearSlot(
            slot=f"Jewel {i + 1}",
            base_name=jewel_base,
            stat_priorities=priorities,
            budget_tier=intent.budget,
        )
        for i in range(2)
    )


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
        # Flasks and jewels — the encoder counts occurrences and labels
        # them "Flask 1".."Flask 5" / "Jewel 1".."Jewel 2" at the
        # ItemSet level (Step 41 Bug 4 fix in encode.py).
        "Flask 1": ItemSlot.FLASK,
        "Flask 2": ItemSlot.FLASK,
        "Flask 3": ItemSlot.FLASK,
        "Flask 4": ItemSlot.FLASK,
        "Flask 5": ItemSlot.FLASK,
        "Jewel 1": ItemSlot.JEWEL,
        "Jewel 2": ItemSlot.JEWEL,
    }
    for g in slots:
        enum = slot_enum_map.get(g.slot)
        if enum is None:
            continue
        # Bug 3 fix: pre-build the full PoB item body (with simulated
        # affixes) and pass it as ``item_name``. ``_placeholder_item_body``
        # detects the multi-line value and emits it verbatim.
        body = _theory_item_body(g.slot, g.base_name, g.stat_priorities, g.budget_tier)
        pob_slots.append(
            StageGearSlot(
                slot=enum,
                item_name=body,
                kind="rare_craft",
                notes=", ".join(g.stat_priorities),
                budget_div_max=None,
            )
        )
    return StageGearSet(stage_key="theory_v2", slots=tuple(pob_slots))


_SLOT_NAME_TO_ENUM: dict[str, ItemSlot] = {
    "Body Armour": ItemSlot.BODY_ARMOUR,
    "Helmet": ItemSlot.HELMET,
    "Gloves": ItemSlot.GLOVES,
    "Boots": ItemSlot.BOOTS,
    "Weapon": ItemSlot.WEAPON_MAIN,
}


def _to_pob_gems(links: tuple[GemLink, ...]) -> StageGemLinks:
    """Map theory `GemLink`s to encoder `PobGemLink`s — one per slot."""
    pob_links: list[PobGemLink] = []
    for link in links:
        gems = [GemSpec(name=link.skill, level=20, quality=20, is_support=False)]
        gems.extend(
            GemSpec(name=s, level=20, quality=20, is_support=True)
            for s in link.supports
            if s != "(open)"
        )
        # PoB requires sockets == len(gems); we don't pad with empty
        # placeholders (PoB would reject them).
        sockets = max(1, min(6, len(gems)))
        slot_enum = _SLOT_NAME_TO_ENUM.get(link.slot, ItemSlot.BODY_ARMOUR)
        pob_links.append(
            PobGemLink(
                slot=slot_enum,
                sockets=sockets,
                color_pattern="R" * sockets,
                gems=tuple(gems[:sockets]),
                notes=link.label or "Theory link",
            ),
        )
    return StageGemLinks(stage_key="theory_v2", links=tuple(pob_links))


# ---------------------------------------------------------------------------
# 5-slot gem layout (Bug 2 fix)
# ---------------------------------------------------------------------------


def _known_active_names() -> set[str]:
    actives, _ = _gem_catalogue()
    return {a.name for a in actives}


def _known_support_names() -> set[str]:
    _, supports = _gem_catalogue()
    return {s.name for s in supports}


def _pick_active(name: str, fallback: str) -> str:
    """Return *name* if it exists in the active-gem catalogue, else *fallback*."""
    return name if name in _known_active_names() else fallback


def _pick_supports(prefer: tuple[str, ...], n: int) -> tuple[str, ...]:
    """Filter *prefer* down to supports in the catalogue, pad with ``(open)``."""
    known = _known_support_names()
    picked: list[str] = [s for s in prefer if s in known][:n]
    while len(picked) < n:
        picked.append("(open)")
    return tuple(picked)


_AURA_BY_DAMAGE: dict[str, str] = {
    "fire": "Anger",
    "cold": "Hatred",
    "lightning": "Wrath",
    "chaos": "Malevolence",
    "physical": "Hatred",
}


def _build_gem_layout(
    intent: TheoryIntent, primary: GemLink, skill: _Active
) -> tuple[GemLink, ...]:
    """Five gem links: Body 6L + Helmet/Gloves/Boots/Weapon 4L.

    Every gem name (active and support) is validated against
    ``gems_3_28.json``. Unknown names degrade to ``(open)`` socket
    placeholders so the anti-hallucination gate never trips.
    """
    is_melee = "melee" in skill.tags
    primary_supports_pool = tuple(primary.supports)

    # Helmet 4L: same primary skill + 3 supports.
    helmet_supports = _pick_supports(primary_supports_pool, 3)
    helmet_link = GemLink(
        skill=primary.skill,
        supports=helmet_supports,
        slot="Helmet",
        label="Secondary 4L",
    )

    # Gloves 4L: aura + 3 utility supports.
    aura = _pick_active(
        _AURA_BY_DAMAGE.get(intent.damage_type, "Hatred"),
        primary.skill,
    )
    gloves_supports = _pick_supports(
        ("Generosity", "Increased Duration", "Arcane Surge", "Inspiration"),
        3,
    )
    gloves_link = GemLink(
        skill=aura,
        supports=gloves_supports,
        slot="Gloves",
        label="Utility 4L",
    )

    # Boots 4L: movement skill + 3 supports.
    movement_pref = "Leap Slam" if is_melee else "Flame Dash"
    movement = _pick_active(movement_pref, primary.skill)
    boots_supports = _pick_supports(
        ("Faster Casting", "Second Wind", "Fortify", "Lifetap"),
        3,
    )
    boots_link = GemLink(
        skill=movement,
        supports=boots_supports,
        slot="Boots",
        label="Movement 4L",
    )

    # Weapon 4L: warcry / utility.
    warcry = _pick_active("Enduring Cry", primary.skill)
    weapon_supports = _pick_supports(
        ("Second Wind", "Increased Duration", "Lifetap", "Arcane Surge"),
        3,
    )
    weapon_link = GemLink(
        skill=warcry,
        supports=weapon_supports,
        slot="Weapon",
        label="Warcry 4L",
    )

    return (primary, helmet_link, gloves_link, boots_link, weapon_link)


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
    actives, supports = _gem_catalogue()
    known_actives = {a.name for a in actives}
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
        if link.skill not in known_actives:
            raise TheoryHallucinationError(
                f"active '{link.skill}' not in gems_3_28.json (slot {link.slot})"
            )
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
    links = _build_gem_layout(intent, primary_link, skill)
    nodes = _select_tree_nodes(intent)
    gear = _select_gear(intent)

    _assert_valid(intent, gear, nodes, links)

    stats = _stat_estimate(intent, nodes)
    pob_code = encode_pob_code(
        character_class=intent.character_class,
        ascendancy=intent.ascendancy,
        tree=_to_pob_tree(intent, nodes),
        gear=_to_pob_gear(gear),
        gems=_to_pob_gems(links),
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
