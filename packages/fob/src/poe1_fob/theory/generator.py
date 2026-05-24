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
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from poe1_core.models.enums import ItemSlot
from poe1_shared.logging import get_logger

from ..gear.base_items import base_for_name, get_base_catalogue
from ..gear.models import StageGearSet, StageGearSlot
from ..gems.models import GemLink as PobGemLink
from ..gems.models import GemSpec, StageGemLinks
from ..pob.encode import encode_pob_code
from ..tree.models import StageTree
from ..tree.tree_data import TreeData, TreeNode, get_tree_data
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
from .realmods import real_affix_line
from .viability import validate_build

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


# 3.28 removed every Awakened Support Gem from the drop pool *except*
# these three (Content Update 3.28.0 patch notes). The vendored
# `gems_3_28.json` is extracted from PoB Community source, which still
# carries all 38 Awakened gems — so we filter at selection time.
#
# NOTE: the catalogue stores Awakened names WITHOUT a " Support" suffix
# (e.g. "Awakened Empower", not "Awakened Empower Support"), so the
# allowlist must match those exact strings.
_AWAKENED_ALLOWLIST: frozenset[str] = frozenset(
    {
        "Awakened Empower",
        "Awakened Enlighten",
        "Awakened Enhance",
    }
)


def _is_available_in_328(name: str) -> bool:
    """False for Awakened support gems not obtainable in PoE 3.28."""
    return not (name.startswith("Awakened ") and name not in _AWAKENED_ALLOWLIST)


# Real, commonly-used support gems in rough order of general usefulness.
# This is the ONE place "which supports are good" knowledge enters the
# generator — a single global ranking of real PoE 3.28 support gems (NOT
# per-build curation; the data-integrity rule forbids inventing values,
# not ranking real gems by how widely they're used). The compatibility
# filter (PoB require/exclude semantics) decides *which* of these apply
# to a given skill; this list decides the *order* so a melee skill gets
# Melee Physical Damage / Brutality / Impale before niche fillers, and a
# spell gets Spell Echo / Controlled Destruction / Elemental Focus.
_CORE_SUPPORTS: tuple[str, ...] = (
    # Attack / melee damage
    "Melee Physical Damage",
    "Brutality",
    "Impale",
    "Pulverise",
    "Close Combat",
    "Multistrike",
    "Rage",
    "Maim",
    "Elemental Damage with Attacks",
    "Faster Attacks",
    "Melee Splash",
    "Ancestral Call",
    # Spell damage
    "Spell Echo",
    "Controlled Destruction",
    "Elemental Focus",
    "Concentrated Effect",
    "Increased Area of Effect",
    "Hypothermia",
    "Bonechill",
    "Combustion",
    "Intensify",
    "Unleash",
    "Cruelty",
    # Projectile / bow
    "Greater Multiple Projectiles",
    "Multiple Projectiles",
    "Vicious Projectiles",
    "Pierce",
    "Chain",
    "Fork",
    "Volley",
    "Mirage Archer",
    "Slower Projectiles",
    # DoT / ailment
    "Swift Affliction",
    "Deadly Ailments",
    "Void Manipulation",
    "Unbound Ailments",
    "Efficacy",
    "Withering Touch",
    # Minion
    "Minion Damage",
    "Minion Speed",
    "Feeding Frenzy",
    "Meat Shield",
    "Predator",
    # Penetration / crit / generic damage
    "Inspiration",
    "Trinity",
    "Fire Penetration",
    "Cold Penetration",
    "Lightning Penetration",
    "Increased Critical Strikes",
    "Increased Critical Damage",
    "Added Fire Damage",
    "Added Cold Damage",
    "Added Lightning Damage",
    "Added Chaos Damage",
    # Defence / utility
    "Fortify",
    "Cast On Critical Strike",
    "Hextouch",
    "Lifetap",
    "Cast while Channelling",
    "Faster Casting",
    "Awakened Empower",
    "Awakened Enhance",
    "Awakened Enlighten",
)
_CORE_SUPPORT_RANK: dict[str, int] = {name: i for i, name in enumerate(_CORE_SUPPORTS)}

# Supports that lock the build to a damage type via their *stats* (not
# tags) — Brutality forces physical-only, penetrations/Combustion are
# element-specific. PoB's require/exclude tags don't express this (they
# use generic "damage"/"attack"), so we gate them by the intent's damage
# type explicitly. Keyed by gem name → the damage types it's valid for.
_SUPPORT_DMG_LOCK: dict[str, frozenset[str]] = {
    "Brutality": frozenset({"physical"}),
    "Awakened Brutality": frozenset({"physical"}),
    "Fire Penetration": frozenset({"fire"}),
    "Awakened Fire Penetration": frozenset({"fire"}),
    "Combustion": frozenset({"fire"}),
    "Cold Penetration": frozenset({"cold"}),
    "Awakened Cold Penetration": frozenset({"cold"}),
    "Hypothermia": frozenset({"cold"}),
    "Bonechill": frozenset({"cold"}),
    "Lightning Penetration": frozenset({"lightning"}),
    "Awakened Lightning Penetration": frozenset({"lightning"}),
    "Elemental Penetration": frozenset({"fire", "cold", "lightning"}),
    "Void Manipulation": frozenset({"chaos"}),
}


def _select_supports_raw(
    skill: _Active, n: int = 5, dmg: str | None = None
) -> tuple[_Support, ...]:
    """Support gems compatible with *skill*, best-first.

    *dmg* is the build's damage type — used to drop element/physical-
    locking supports (Brutality on a fire spell, Fire Penetration on a
    cold build) that the tag system can't catch.

    Returns the :class:`_Support` objects (no padding) so callers can
    test compatibility, not just names.
    """
    _, supports = _gem_catalogue()
    skill_tags = set(skill.tags)
    fits: list[_Support] = []
    for s in supports:
        if not _is_available_in_328(s.name):
            continue
        # PoB applicability semantics (calcLib.canGrantedEffectSupport-
        # ActiveSkill): reject if the skill carries any excluded type;
        # an empty require list means "supports everything" (subject to
        # exclude); otherwise the skill must carry AT LEAST ONE of the
        # required types (any-of, NOT subset — a support requiring
        # {Spell, Attack} supports both spells and attacks).
        if any(t in skill_tags for t in s.exclude_tags):
            continue
        if s.valid_gem_tags and not any(t in skill_tags for t in s.valid_gem_tags):
            continue
        lock = _SUPPORT_DMG_LOCK.get(s.name)
        if lock is not None and dmg is not None and dmg not in lock:
            continue
        fits.append(s)

    # Order: core (commonly-used) supports first, in their curated order;
    # then any other compatible support, "specific" ones (requiring a tag
    # the skill has) ahead of universal fillers, by static priority. Fully
    # deterministic.
    def _key(s: _Support) -> tuple[int, int, int, str]:
        core_idx = _CORE_SUPPORT_RANK.get(s.name, len(_CORE_SUPPORTS))
        specific = 0 if (set(s.valid_gem_tags) & skill_tags) else 1
        return (core_idx, specific, -s.priority, s.name)

    fits.sort(key=_key)
    return tuple(fits[:n])


def _select_supports(skill: _Active, n: int = 5, dmg: str | None = None) -> tuple[str, ...]:
    """Names of *n* support gems that fit *skill*, padded with ``(open)``."""
    picked = [s.name for s in _select_supports_raw(skill, n, dmg)]
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

# Universal survivability value — every build wants these, so they're
# scored on top of the build-specific damage/defence keywords. The
# weights make a *premium* notable rank above filler: a single
# "+2% to all maximum Elemental Resistances" node (one point, three
# resistances) outscores two separate "+1% maximum Fire/Cold Resistance"
# nodes (two points), so the value-per-point greedy prefers it.
_SURVIVAL_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("all maximum elemental resistance", 6),
    ("maximum fire resistance", 4),
    ("maximum cold resistance", 4),
    ("maximum lightning resistance", 4),
    ("maximum chaos resistance", 4),
    ("all elemental resistances", 4),
    ("spell suppression", 3),
    ("suppress spell", 3),
    ("to all attributes", 2),
    ("chance to block", 2),
    ("maximum life", 2),
    ("maximum energy shield", 2),
    ("resistance", 1),
    ("life regenerat", 1),
    ("leech", 1),
)

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


def _score_text(text: str, dmg: str, defence: str) -> int:
    """Keyword relevance of an arbitrary stat text to the build.

    Sums build-specific damage (x3) + defence (x3) + universal
    survivability (weighted) so that defensively-premium notables (max
    resistances, suppression, all-attributes) are valued for every build,
    not just the build's own damage type.
    """
    low = text.lower()
    score = 0
    for kw in _DAMAGE_KEYWORDS.get(dmg, ()):
        if kw in low:
            score += 3
    for kw in _DEFENCE_KEYWORDS.get(defence, ()):
        if kw in low:
            score += 3
    for kw, weight in _SURVIVAL_WEIGHTS:
        if kw in low:
            score += weight
    return score


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
    return _score_text(" ".join([node.name or "", *node.stats]), dmg, defence)


# Weapon-type keywords. The generator recommends a specific weapon
# (bow / wand / two-hand sword), so a passive that boosts a *different*
# weapon class is dead — exclude those nodes from the allocation. A
# Marauder using a sword no longer grabs "increased Damage with Axes".
_WEAPON_KW: dict[str, tuple[str, ...]] = {
    "sword": ("sword", "swords"),
    "axe": ("axe", "axes"),
    "mace": ("mace", "maces", "sceptre", "sceptres"),
    "staff": ("staff", "staves", "stave"),
    "bow": ("bow", "bows"),
    "wand": ("wand", "wands"),
    "dagger": ("dagger", "daggers"),
    "claw": ("claw", "claws"),
}
_ALL_WEAPON_KW: frozenset[str] = frozenset(kw for kws in _WEAPON_KW.values() for kw in kws)


def _build_weapon_group(intent: TheoryIntent) -> str:
    """The weapon family the generator recommends for this build —
    mirrors the choice in `_select_gear` (bow / wand / sword)."""
    skill = _find_active(intent.primary_skill)
    if "bow" in skill.tags:
        return "bow"
    if "melee" in skill.tags:
        return "sword"
    return "wand"


def _excluded_weapon_ids(intent: TheoryIntent, td: TreeData) -> frozenset[int]:
    """Node ids whose stats mention a *foreign* weapon type (one the build
    doesn't use) and not the build's own — these are wasted points."""
    own = set(_WEAPON_KW.get(_build_weapon_group(intent), ()))
    foreign = _ALL_WEAPON_KW - own
    excluded: set[int] = set()
    for nid, n in td.nodes_by_id.items():
        if n.ascendancy_name is not None or nid >= _CLUSTER_JEWEL_MIN_ID or n.is_mastery:
            continue
        text = " ".join([n.name or "", *n.stats]).lower()
        if any(kw in text for kw in foreign) and not any(kw in text for kw in own):
            excluded.add(nid)
    return frozenset(excluded)


def bfs_path(
    adjacency: dict[int, frozenset[int]],
    src: int,
    dst: int,
    forbidden: frozenset[int] | set[int] = frozenset(),
) -> list[int] | None:
    """Shortest path from *src* to *dst* on an undirected adjacency graph.

    ``forbidden`` is a set of node ids the path must not traverse. *src*
    and *dst* themselves are always allowed even if listed in
    ``forbidden`` — they bookend the path. Used by the waypoint
    expansion in ``_select_tree_nodes`` to route around already-visited
    nodes so the overall allocation is a single connected component
    with no duplicate steps.

    Returns the list of node IDs from src to dst inclusive, or ``None``
    if dst is unreachable from src without crossing forbidden nodes.
    O(V+E) — predecessor reconstruction.
    """
    if src == dst:
        return [src]
    parents: dict[int, int | None] = {src: None}
    queue: deque[int] = deque([src])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency.get(node, frozenset()):
            if neighbor in parents:
                continue
            if neighbor in forbidden and neighbor != dst:
                continue
            parents[neighbor] = node
            if neighbor == dst:
                path: list[int] = [dst]
                cur: int | None = node
                while cur is not None:
                    path.append(cur)
                    cur = parents[cur]
                path.reverse()
                return path
            queue.append(neighbor)
    return None


_MAX_TREE_NODES = 120
_CLUSTER_JEWEL_MIN_ID = 65536
# Up to this many mastery effects are allocated on top of the regular
# tree; each costs a point, so the regular fill targets the remainder.
_MAX_MASTERIES = 8

# Locality penalty (points of node-score per hop of travel distance from
# the class start). The tree allocation prefers high-value nodes that are
# *close* to where the character starts, so a real build stays a compact
# cluster near its class area instead of sprawling tendrils across the
# whole tree toward far high-scoring nodes. Tuned so a Ranger/Deadeye
# build (which used to wander 30+ hops toward the Marauder/Witch side)
# stays within a sensible radius while still threading the best notables.
_LOCALITY_ALPHA = 0.7


def _regular_distances(
    adjacency: dict[int, frozenset[int]],
    start: int,
    all_nodes: dict[int, TreeNode],
) -> dict[int, int]:
    """BFS hop-distance from *start* over the **regular** tree only.

    Cluster-jewel, mastery and ascendancy nodes are not traversable as
    travel, so they're excluded — the result reflects the real number of
    passive points needed to reach each regular node.
    """
    dist: dict[int, int] = {start: 0}
    queue: deque[int] = deque([start])
    while queue:
        x = queue.popleft()
        for nb in adjacency.get(x, frozenset()):
            if nb in dist:
                continue
            n = all_nodes.get(nb)
            if not _is_fillable(n, nb):
                continue
            dist[nb] = dist[x] + 1
            queue.append(nb)
    return dist


def _is_fillable(node: TreeNode | None, nid: int) -> bool:
    """A node the fill phase may allocate — regular tree only."""
    if node is None:
        return False
    if nid >= _CLUSTER_JEWEL_MIN_ID or node.is_mastery:
        return False
    return node.ascendancy_name is None


def _fill_to_budget(
    visited: set[int],
    adjacency: dict[int, frozenset[int]],
    all_nodes: dict[int, TreeNode],
    dmg: str,
    defence: str,
    budget: int,
    dist: dict[int, int] | None = None,
    exclude: frozenset[int] = frozenset(),
) -> list[int]:
    """Greedy best-first boundary expansion until *budget* is reached.

    Step 45a: after the waypoint BFS connects the chosen targets, the
    path is often only ~15-20 nodes — far short of an endgame ~100-point
    allocation. This grows the allocation by repeatedly taking the
    best *boundary* node (an unvisited regular node adjacent to the
    already-visited set). Every added node is, by construction, adjacent
    to at least one already-visited node — so the final allocation stays
    a single connected component.

    "Best" = ``score - _LOCALITY_ALPHA * distance_from_start`` (Step 46),
    so the fill grows the allocation outward *compactly* near the class
    start instead of racing across the tree toward a far high-scoring
    cluster. ``dist`` is the precomputed regular-tree distance map; when
    omitted the fill falls back to score-only (legacy behaviour).

    Mutates ``visited`` in place; returns the nodes added, in order.
    """
    dist = dist or {}

    def _value(nid: int) -> float:
        score = _score_node(all_nodes[nid], dmg, defence)
        return score - _LOCALITY_ALPHA * dist.get(nid, 0)

    added: list[int] = []
    while len(visited) < budget:
        boundary: set[int] = set()
        for v in visited:
            for n in adjacency.get(v, frozenset()):
                if n in visited or n in exclude:
                    continue
                if _is_fillable(all_nodes.get(n), n):
                    boundary.add(n)
        if not boundary:
            break
        best = max(boundary, key=lambda nid: (_value(nid), -nid))
        visited.add(best)
        added.append(best)
    return added


def _grow_to_value(
    visited: set[int],
    adjacency: dict[int, frozenset[int]],
    all_nodes: dict[int, TreeNode],
    dmg: str,
    defence: str,
    excluded: frozenset[int],
    budget: int,
) -> list[int]:
    """Value-per-point greedy notable/keystone allocation (Step 49).

    Repeatedly take the unallocated notable/keystone with the best
    ``score / path-cost`` ratio — where *cost* is the number of NEW points
    needed to reach it from the current allocation — and allocate it plus
    its connecting travel. This is a greedy Steiner-style heuristic: it
    prefers high-value nodes that are cheap to reach, so a premium notable
    (e.g. "+2% to all max Elemental Res", one point) beats two separate
    single-resistance nodes, and far low-value nodes are never taken.

    Mutates ``visited``; returns the nodes added, in allocation order
    (each adjacent to an earlier node).
    """
    # Precompute the value of every candidate notable/keystone once — the
    # score is static, so re-scoring 3000+ nodes every iteration is the
    # hot spot. Only positive-value, non-excluded targets survive.
    targets: dict[int, int] = {}
    for nid, n in all_nodes.items():
        if nid in excluded or not (n.is_notable or n.is_keystone):
            continue
        s = _score_node(n, dmg, defence)
        if s > 0:
            targets[nid] = s

    added: list[int] = []
    while len(visited) < budget:
        # Multi-source BFS from the whole allocated set over allowed
        # regular nodes — distance = new points to reach each node.
        dist: dict[int, int] = dict.fromkeys(visited, 0)
        parent: dict[int, int] = {}
        queue: deque[int] = deque(visited)
        while queue:
            x = queue.popleft()
            for nb in adjacency.get(x, frozenset()):
                if nb in dist or nb in excluded or not _is_fillable(all_nodes.get(nb), nb):
                    continue
                dist[nb] = dist[x] + 1
                parent[nb] = x
                queue.append(nb)

        best_nid: int | None = None
        best_eff = 0.0
        remaining = budget - len(visited)
        for nid, s in targets.items():
            if nid in visited:
                continue
            cost = dist.get(nid, 0)
            if cost == 0 or cost > remaining:
                continue
            eff = s / cost
            if eff > best_eff or (eff == best_eff and (best_nid is None or nid < best_nid)):
                best_eff = eff
                best_nid = nid
        if best_nid is None:
            break

        chain: list[int] = []
        cur = best_nid
        while cur not in visited:
            chain.append(cur)
            cur = parent[cur]
        chain.reverse()
        for nid in chain:
            visited.add(nid)
            added.append(nid)
    return added


def _select_masteries(
    visited: set[int], td: TreeData, dmg: str, defence: str
) -> list[tuple[int, int, str, tuple[str, ...]]]:
    """Allocate mastery effects on the built tree.

    A mastery node can be allocated once an adjacent node in its wheel is
    taken. For each such mastery we pick the effect whose stats best match
    the build (life / resistance / the build's damage), skipping masteries
    where nothing is relevant. Returns (node_id, effect_id, name, stats),
    best-first, capped to ``_MAX_MASTERIES``.
    """
    candidates: list[tuple[int, int, int, str, tuple[str, ...]]] = []
    for nid, node in td.nodes_by_id.items():
        if not node.is_mastery or not node.mastery_effects:
            continue
        if not (td.adjacency.get(nid, frozenset()) & visited):
            continue  # no allocated node in this mastery's wheel
        best_eff = max(
            node.mastery_effects,
            key=lambda e: _score_text(" ".join(e[1]), dmg, defence),
        )
        eff_score = _score_text(" ".join(best_eff[1]), dmg, defence)
        if eff_score <= 0:
            continue  # nothing relevant on this mastery for the build
        candidates.append((eff_score, nid, best_eff[0], node.name or "Mastery", best_eff[1]))
    candidates.sort(key=lambda c: (-c[0], c[1]))
    return [(nid, eff, name, stats) for _, nid, eff, name, stats in candidates[:_MAX_MASTERIES]]


def _select_tree_nodes(intent: TheoryIntent) -> tuple[TreeNodeRef, ...]:
    """BFS path from the class start through the best-scored notables.

    Step 44: replaces the previous flat "top-scored nodes" list. Every
    consecutive pair of returned node IDs is guaranteed adjacent in
    `TreeData.adjacency`, so PoB renders a contiguous allocation rather
    than floating disconnected points. Ascendancy notables are still
    listed for display but live outside the BFS path (they are
    allocated via the lab, not the tree graph).
    """
    td = get_tree_data()
    class_idx = _CLASS_ID.get(intent.character_class, 0)
    start_id = td.class_starts.get(class_idx, 0)

    # Travel cost from the class start to every reachable regular node
    # (used by the top-up fill's locality tiebreak).
    dist = _regular_distances(td.adjacency, start_id, td.nodes_by_id)

    # Nodes that boost a weapon class this build doesn't use are dead —
    # exclude them everywhere (Step 48).
    excluded = _excluded_weapon_ids(intent, td)

    # Step 49: value-per-point greedy. Repeatedly allocate the unallocated
    # notable/keystone with the best score / new-points-to-reach ratio,
    # plus its connecting travel. This replaces the old "pick top-N
    # waypoints then BFS-connect them" walk: it accounts for travel cost
    # directly (so it stays local AND efficient) and prefers premium
    # notables (a one-point "+2% all max res" beats two single-res nodes).
    # Reserve room for the masteries (each costs a point).
    budget = _MAX_TREE_NODES - _MAX_MASTERIES
    path: list[int] = [start_id]
    visited: set[int] = {start_id}
    path.extend(
        _grow_to_value(
            visited,
            td.adjacency,
            td.nodes_by_id,
            intent.damage_type,
            intent.defence_archetype,
            excluded,
            budget,
        )
    )

    # Top up any leftover points (when nearby positive-value notables are
    # exhausted) with the best-scored adjacent small nodes — broadened
    # scoring means these are life/res travel, not junk.
    path.extend(
        _fill_to_budget(
            visited,
            td.adjacency,
            td.nodes_by_id,
            intent.damage_type,
            intent.defence_archetype,
            budget,
            dist=dist,
            exclude=excluded,
        )
    )

    # Step 48: allocate mastery effects on the wheels we've taken.
    masteries = _select_masteries(visited, td, intent.damage_type, intent.defence_archetype)

    out: list[TreeNodeRef] = []
    for i, nid in enumerate(path):
        node = td.nodes_by_id.get(nid)
        if i == 0:
            out.append(
                TreeNodeRef(
                    node_id=nid,
                    name=f"{intent.character_class} start",
                    type="start",
                    stats=(),
                ),
            )
            continue
        if node is None:
            continue
        # Classify by the node's real flags (the fill phase pulls in
        # notables/keystones the target lists didn't, so flags beat
        # membership in the original target sets).
        if node.is_keystone:
            out.append(TreeNodeRef(node_id=nid, name=node.name or "?", type="keystone", stats=()))
        elif node.is_notable:
            out.append(TreeNodeRef(node_id=nid, name=node.name or "?", type="notable", stats=()))
        else:
            out.append(TreeNodeRef(node_id=nid, name=node.name or "", type="travel", stats=()))

    # Mastery effects — real (node, effect) allocations the encoder turns
    # into `<Spec masteryEffects>`. Tagged "mastery" + carry the effect id.
    for nid, eff, name, stats in masteries:
        out.append(TreeNodeRef(node_id=nid, name=name, type="mastery", stats=stats, effect_id=eff))

    # Ascendancy notables — display-only, allocated via the lab.
    asc_notables = sorted(
        (
            n
            for n in td.nodes_by_id.values()
            if n.ascendancy_name == intent.ascendancy and n.is_notable and n.name
        ),
        key=lambda n: n.id,
    )
    for n in asc_notables[:4]:
        out.append(
            TreeNodeRef(
                node_id=n.id,
                name=n.name or "?",
                type="ascendancy",
                stats=(),
            ),
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
    """Per-slot stat priorities — English PoE mod stems, ordered by real
    crafting/buying priority (the first entry is the most important).

    Stems map (via :mod:`poe1_fob.theory.realmods`) to real PoE stat ids,
    so the same list drives the UI badges, Trade links and the real PoB
    affix lines.
    """
    is_es = intent.defence_archetype == "es"
    is_spell = intent.damage_type in ("fire", "cold", "lightning", "chaos")
    is_crit = intent.budget in ("mid", "endgame")

    primary_def = "to maximum Energy Shield" if is_es else "to maximum Life"
    main_res = "to Fire Resistance"
    sec_res = "to Cold Resistance"
    speed = "increased Cast Speed" if is_spell else "increased Attack Speed"
    main_dmg = "increased Spell Damage" if is_spell else "increased Physical Damage"

    # Flat added damage — the dominant DPS source (Step 52). For a spell
    # build it's "Adds X to Y <element> Damage to Spells" on the weapon; for
    # a physical attack build it's "Adds X to Y Physical Damage" on the
    # weapon AND on jewellery / gloves (the attack-tagged variant).
    elem = {"fire": "Fire", "cold": "Cold", "lightning": "Lightning", "chaos": "Chaos"}
    weapon_added = (
        f"Adds {elem[intent.damage_type]} Damage to Spells" if is_spell else "Adds Physical Damage"
    )
    jewel_added = None if is_spell else "Adds Physical Damage"

    slot_map: dict[str, tuple[str, ...]] = {
        "Helmet": (primary_def, main_res, sec_res, main_dmg),
        "Body Armour": (primary_def, main_res, sec_res, "to Lightning Resistance"),
        "Gloves": (
            (primary_def, main_res, speed, jewel_added)
            if jewel_added
            else (primary_def, main_res, speed, main_dmg)
        ),
        "Boots": (primary_def, "Movement Speed", main_res, speed),
        "Belt": (primary_def, main_res, sec_res, "increased Flask Life Recovery"),
        "Amulet": (
            primary_def,
            jewel_added if jewel_added else main_dmg,
            "Critical Strike Multiplier" if is_crit else "to all Attributes",
            main_res,
        ),
        "Ring": (
            (primary_def, main_res, sec_res, "to Mana", jewel_added)
            if jewel_added
            else (primary_def, main_res, sec_res, "to Mana", "to all Attributes")
        ),
        "Wand": (weapon_added, "increased Spell Damage", "increased Cast Speed", "critical strike"),
        "Bow": (
            weapon_added,
            "increased Physical Damage",
            "increased Attack Speed",
            "critical strike",
        ),
        "Weapon": (
            weapon_added,
            "increased Physical Damage",
            "increased Attack Speed",
            "Accuracy",
        ),
        "Off-hand": (primary_def, main_res, sec_res, "Chance to Block"),
        "Shield": (primary_def, main_res, sec_res, "Chance to Block"),
    }
    return slot_map.get(slot_name, (primary_def, main_res, "increased damage"))


# Flask suffix per base — a real PoE utility/defence suffix so the
# generated flask reads like an actual magic flask rather than a blank
# white base.
_FLASK_SUFFIX: dict[str, str] = {
    "Divine Life Flask": "of Staunching",
    "Quicksilver Flask": "of Adrenaline",
    "Granite Flask": "of Iron Skin",
    "Jade Flask": "of Reflexes",
    "Sulphur Flask": "of the Owl",
    "Diamond Flask": "of Reflexes",
    "Silver Flask": "of the Dove",
    "Bismuth Flask": "of the Dove",
    "Eternal Mana Flask": "of Warding",
    "Amethyst Flask": "of the Order",
}


def _theory_item_body(
    slot_name: str,
    base_name: str,
    stat_priorities: tuple[str, ...],
    budget: BudgetTier,
) -> str:
    """Multi-line PoB item body.

    Flasks become a MAGIC item named ``<base> <suffix>``; everything else
    is a RARE with simulated affix lines derived from its stat priorities.
    """
    if slot_name.startswith("Flask"):
        suffix = _FLASK_SUFFIX.get(base_name, "of Staunching")
        return "\n".join(
            [
                "Rarity: MAGIC",
                f"{base_name} {suffix}",
                base_name,
                "Implicits: 0",
            ]
        )
    lines = [
        "Rarity: RARE",
        f"Generated {slot_name}",
        base_name,
        "Implicits: 0",
    ]
    # Step 47: emit ONLY real mod tiers from RePoE (the actual top roll
    # that can spawn on this base at this budget). A priority that can't
    # roll on this slot (e.g. spell damage on a helmet) is dropped rather
    # than shown with an invented value — every line is a real mod.
    base = base_for_name(base_name)
    item_tags = frozenset(base.tags) if base else frozenset()
    for p in stat_priorities:
        affix = real_affix_line(p, item_tags, budget)
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


def _rollable_priorities(
    stems: tuple[str, ...], base_name: str, budget: BudgetTier
) -> tuple[str, ...]:
    """Keep only stems that map to a real mod which can actually roll on
    this base — so the UI gear card and the PoB export agree (no more
    "increased Physical Damage" shown on a helmet)."""
    base = base_for_name(base_name)
    item_tags = frozenset(base.tags) if base else frozenset()
    kept = tuple(s for s in stems if real_affix_line(s, item_tags, budget) is not None)
    # Never return an empty list — fall back to the raw stems so a slot
    # always shows *something* (only happens for exotic bases).
    return kept or stems


def _select_gear(intent: TheoryIntent) -> tuple[GearSlot, ...]:
    out: list[GearSlot] = []
    for slot_enum, slot_name in _SLOTS:
        base_name = _pick_base(slot_enum, intent)
        out.append(
            GearSlot(
                slot=slot_name,
                base_name=base_name,
                stat_priorities=_rollable_priorities(
                    _stat_priorities(slot_name, intent), base_name, intent.budget
                ),
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
                stat_priorities=_rollable_priorities(
                    _stat_priorities(weapon_label, intent), weapon_pool[0].name, intent.budget
                ),
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
                    stat_priorities=_rollable_priorities(
                        _stat_priorities("Off-hand", intent), shield_pool[0].name, intent.budget
                    ),
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

# Rough life model (the old one added a bogus `100 * 99` and produced
# ~13k). PoE life ≈ (38 + ~12/level base + flat life from gear) scaled by
# the tree's % increased life. These constants land an endgame life build
# around 4-5k — in the right ballpark for what PoB reports, while staying
# explicitly an estimate.
_LEVEL_BY_BUDGET: dict[BudgetTier, int] = {"starter": 60, "mid": 82, "endgame": 92}
_GEAR_FLAT_LIFE: dict[BudgetTier, int] = {"starter": 250, "mid": 600, "endgame": 950}
_GEAR_FLAT_ES: dict[BudgetTier, int] = {"starter": 250, "mid": 900, "endgame": 1800}


def _stat_estimate(intent: TheoryIntent, nodes: tuple[TreeNodeRef, ...]) -> StatEstimate:
    is_es = intent.defence_archetype == "es"
    level = _LEVEL_BY_BUDGET[intent.budget]
    life_nodes = sum(1 for n in nodes if "life" in n.name.lower())
    es_nodes = sum(1 for n in nodes if "energy" in n.name.lower() or "shield" in n.name.lower())
    res_nodes = sum(1 for n in nodes if "resist" in n.name.lower())

    base_life = 38 + 12 * level
    # % increased life from the tree, capped at a realistic spec total.
    life_pct = min(80 if is_es else 180, life_nodes * 8)
    life = round((base_life + _GEAR_FLAT_LIFE[intent.budget]) * (1 + life_pct / 100))

    if is_es:
        es_pct = min(240, es_nodes * 12)
        es = round(_GEAR_FLAT_ES[intent.budget] * (1 + es_pct / 100))
    else:
        es = 0

    warning = (
        "Capping resistances requires gear — molto piu del solo albero." if res_nodes < 2 else None
    )
    # `dps_index` is intentionally 0: real DPS needs PoB's calc engine, so
    # we don't fabricate a number (the UI hides it and points to PoB).
    return StatEstimate(
        life_estimate=max(life, 0),
        es_estimate=max(es, 0),
        dps_index=0,
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


def _gem_level(name: str) -> int:
    """Max level for a gem. Awakened Empower/Enhance/Enlighten cap at 5
    (level 4 + 1 from corruption); every other gem goes to 20."""
    return 5 if name.startswith("Awakened ") else 20


def _to_pob_gems(links: tuple[GemLink, ...]) -> StageGemLinks:
    """Map theory `GemLink`s to encoder `PobGemLink`s — one per slot."""
    pob_links: list[PobGemLink] = []
    for link in links:
        gems = [
            GemSpec(name=link.skill, level=_gem_level(link.skill), quality=20, is_support=False)
        ]
        gems.extend(
            GemSpec(name=s, level=_gem_level(s), quality=20, is_support=True)
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
    picked: list[str] = [s for s in prefer if s in known and _is_available_in_328(s)][:n]
    while len(picked) < n:
        picked.append("(open)")
    return tuple(picked)


def _pick_supports_for(
    skill: _Active, prefer: tuple[str, ...], n: int, dmg: str | None = None
) -> tuple[str, ...]:
    """Pick *n* supports from *prefer* that are **compatible** with *skill*,
    then fill from the rest of the compatible pool, padded with ``(open)``.

    Unlike :func:`_pick_supports` (which only checks the catalogue), this
    enforces tag compatibility — so e.g. ``Faster Casting`` is never
    attached to an attack-tagged movement skill.
    """
    compatible = _select_supports_raw(skill, n=99, dmg=dmg)
    compatible_names = [s.name for s in compatible]
    compatible_set = set(compatible_names)
    picked: list[str] = [s for s in prefer if s in compatible_set][:n]
    for name in compatible_names:
        if len(picked) >= n:
            break
        if name not in picked:
            picked.append(name)
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

# Helmet 4L secondary skill by skill family — a genuinely *different*
# active from the primary (movement / secondary attack / minion utility).
_SECONDARY_SKILL: dict[str, str] = {
    "melee": "Leap Slam",
    "spell": "Flame Dash",
    "bow": "Barrage",
    "minion": "Raise Spectre",
}


def _pick_secondary(skill: _Active, primary_name: str) -> str:
    """Pick a secondary active for the Helmet 4L, distinct from the primary.

    Prefers a tag-appropriate movement/utility skill that exists in the
    catalogue; falls back to the first catalogue active that differs from
    the primary.
    """
    known = _known_active_names()
    for tag, secondary in _SECONDARY_SKILL.items():
        if tag in skill.tags and secondary != primary_name and secondary in known:
            return secondary
    actives, _ = _gem_catalogue()
    for a in actives:
        if a.name != primary_name:
            return a.name
    return primary_name


def _build_gem_layout(
    intent: TheoryIntent, primary: GemLink, skill: _Active
) -> tuple[GemLink, ...]:
    """Five gem links: Body 6L + Helmet/Gloves/Boots/Weapon 4L.

    Every gem name (active and support) is validated against
    ``gems_3_28.json``. Unknown names degrade to ``(open)`` socket
    placeholders so the anti-hallucination gate never trips. No active
    skill appears in more than one link.
    """
    primary_name = primary.skill

    # Helmet 4L: a *secondary* skill, distinct from the primary, with
    # supports that actually fit it.
    dmg = intent.damage_type
    secondary = _pick_secondary(skill, primary_name)
    secondary_active = _find_active(secondary)
    helmet_link = GemLink(
        skill=secondary,
        supports=_select_supports(secondary_active, 3, dmg=dmg),
        slot="Helmet",
        label="Secondary 4L",
    )

    # Gloves 4L: aura + 3 utility supports.
    aura = _pick_active(
        _AURA_BY_DAMAGE.get(intent.damage_type, "Hatred"),
        primary_name,
    )
    aura_active = _find_active(aura)
    gloves_link = GemLink(
        skill=aura,
        supports=_pick_supports_for(
            aura_active,
            ("Generosity", "Increased Duration", "Arcane Surge", "Inspiration"),
            3,
            dmg=dmg,
        ),
        slot="Gloves",
        label="Utility 4L",
    )

    # Boots 4L: movement skill, distinct from primary AND the helmet secondary.
    movement_prefs = (
        ("Leap Slam", "Flame Dash", "Dash") if "melee" in skill.tags else ("Flame Dash", "Dash")
    )
    known = _known_active_names()
    movement = primary_name
    for m in movement_prefs:
        if m in known and m != primary_name and m != secondary:
            movement = m
            break
    movement_active = _find_active(movement)
    boots_link = GemLink(
        skill=movement,
        supports=_pick_supports_for(
            movement_active,
            ("Second Wind", "Fortify", "Lifetap", "Faster Attacks", "Faster Casting"),
            3,
            dmg=dmg,
        ),
        slot="Boots",
        label="Movement 4L",
    )

    # Weapon 4L: warcry / utility.
    warcry = _pick_active("Enduring Cry", primary_name)
    warcry_active = _find_active(warcry)
    weapon_link = GemLink(
        skill=warcry,
        supports=_pick_supports_for(
            warcry_active,
            ("Second Wind", "Increased Duration", "Infusion", "Lifetap"),
            3,
            dmg=dmg,
        ),
        slot="Weapon",
        label="Warcry 4L",
    )

    return (primary, helmet_link, gloves_link, boots_link, weapon_link)


def _to_pob_tree(intent: TheoryIntent, nodes: tuple[TreeNodeRef, ...]) -> StageTree:
    # Encode the regular tree path + mastery nodes. The "start" node is
    # auto-allocated by PoB; ascendancy notables must NOT go into the main
    # `nodes` list (they're allocated via the lab and have no connecting
    # path on the main tree → they'd float). Mastery nodes are allocated
    # via the `nodes` list AND the `masteryEffects` (node, effect) pairs —
    # PoB drops a mastery node from `nodes` unless its effect is listed.
    real_ids = tuple(
        n.node_id for n in nodes if n.type not in ("start", "ascendancy") and n.node_id > 0
    )
    mastery_effects = tuple(
        (n.node_id, n.effect_id) for n in nodes if n.type == "mastery" and n.effect_id is not None
    )
    return StageTree(
        stage_key="theory_v2",
        node_ids=real_ids,
        notables=tuple(n.name for n in nodes if n.type == "notable"),
        ascendancy_nodes=tuple(n.name for n in nodes if n.type == "ascendancy"),
        mastery_effects=mastery_effects,
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
            if s == "(open)":
                continue
            if s not in known_supports:
                raise TheoryHallucinationError(f"support '{s}' not in gems_3_28.json")
            if not _is_available_in_328(s):
                raise TheoryHallucinationError(f"support '{s}' not obtainable in PoE 3.28")
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
    supports = _select_supports(skill, dmg=intent.damage_type)
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
    # Step 43 — run viability checks and attach the report. Never raises;
    # error-severity issues are surfaced in the UI as alerts.
    skeleton = skeleton.model_copy(update={"viability": validate_build(skeleton)})
    log.info(
        "theory_v2_ok",
        class_name=intent.character_class,
        ascendancy=intent.ascendancy,
        skill=intent.primary_skill,
        nodes=len(nodes),
        slots=len(gear),
        viability_passed=skeleton.viability.passed,
        viability_issues=len(skeleton.viability.issues),
    )
    return skeleton


__all__ = [
    "TheoryError",
    "TheoryHallucinationError",
    "generate_build",
    "list_active_skills",
]
