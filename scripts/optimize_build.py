"""Local PoB-exact tree optimiser for the Theorycrafter (Step 51).

Takes a generated build skeleton and improves its passive-tree allocation
by local search, scoring every candidate with PoB's real calc engine
(`scripts/pob_eval.py`). Gear / gems / ascendancy are held fixed here —
the tree is the biggest, highest-impact search space; co-optimising gear
and gems comes later.

Search: connectivity-preserving swaps. Each iteration proposes a handful
of "drop a low-value allocated node, take a high-value frontier node"
moves (ranked by the cheap keyword/survivability heuristic, decided by
the exact PoB fitness), keeps the best-improving one, and stops at a local
optimum. Fitness = real DPS scaled by a viability penalty (resistances
must cap, pool must clear a floor).

Local/offline tool only — needs the PoB runtime (`scripts/setup_pob.py`).

    uv run python scripts/optimize_build.py            # demo on a Marauder Cyclone
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pob_eval import PobEvaluator  # type: ignore[import-not-found]  # sibling script

from poe1_core.models.enums import ItemSlot
from poe1_fob.gear.base_items import base_for_name, get_base_catalogue
from poe1_fob.gear.models import StageGearSet, StageGearSlot
from poe1_fob.gear.uniques import UniqueItem, unique_pob_body, uniques_for_slot
from poe1_fob.pob.encode import encode_pob_code
from poe1_fob.theory import TheoryIntent, generate_build
from poe1_fob.theory import generator as gen
from poe1_fob.theory.models import GearSlot, GemLink, TreeNodeRef
from poe1_fob.tree.tree_data import TreeData, get_tree_data

# ItemSlot → our unique-catalogue slot string.
_UNIQUE_SLOT: dict[ItemSlot, str] = {
    ItemSlot.HELMET: "helmet",
    ItemSlot.BODY_ARMOUR: "body_armour",
    ItemSlot.GLOVES: "gloves",
    ItemSlot.BOOTS: "boots",
    ItemSlot.BELT: "belt",
    ItemSlot.AMULET: "amulet",
    ItemSlot.RING: "ring",
    ItemSlot.WEAPON_MAIN: "weapon",
    ItemSlot.WEAPON_OFFHAND: "weapon_offhand",
}

_EHP_FLOOR = {"starter": 2500, "mid": 4000, "endgame": 5000}
# Step 60: EHP we reward up to (TotalEHP, PoB-exact). Above this, the EHP
# bonus saturates so the optimiser stops trading DPS for more defence.
_EHP_TARGET = {"starter": 12000, "mid": 25000, "endgame": 40000}


# ---------------------------------------------------------------------------
# Fitness
# ---------------------------------------------------------------------------


def fitness(stats: dict[str, float], budget: str) -> float:
    """Real DPS scaled by a viability penalty and a layered-EHP reward.

    Rewards damage, but: (a) a build that can't cap resistances or clears
    no pool floor is heavily penalised, and (b) — Step 60 — a *layered*-EHP
    bonus rewards real TotalEHP (sublinear, saturating at ``_EHP_TARGET``)
    so the optimiser actually picks defensive uniques / nodes / CI instead
    of stopping at the bare pool floor. DPS still scales linearly, so it
    leads among similarly-tanky builds; a glass cannon is cut to ~0.4x.
    """
    dps = stats.get("FullDPS") or stats.get("CombinedDPS") or stats.get("TotalDPS") or 0.0
    pen = 1.0
    for key in ("FireResist", "ColdResist", "LightningResist"):
        v = stats.get(key, 0.0)
        if v < 75:
            pen *= max(0.05, 1.0 - (75 - v) * 0.04)
    pool = max(stats.get("Life", 0.0), stats.get("EnergyShield", 0.0))
    floor = _EHP_FLOOR.get(budget, 4000)
    if pool < floor:
        pen *= max(0.1, pool / floor)
    # Step 66/67: negative unreserved mana = the auras can't actually be
    # reserved. PoB applies the buffs anyway, so without this penalty the
    # optimiser would stack unrunnable auras for "free" DPS. A firm cliff makes
    # any over-reserved build score ~10x lower, so the aura forward-select only
    # keeps auras that genuinely fit. Step 67 tightened the threshold to a
    # strict 0 (was -10): a served build at e.g. -2 unreserved is unrunnable,
    # and the optimiser can always path a reservation-efficiency notable or
    # drop an aura to land non-negative. PoB's mana is integer-grained, so 0 is
    # the honest floor.
    if stats.get("ManaUnreserved", 0.0) < 0:
        pen *= 0.1
    ehp = max(stats.get("TotalEHP", 0.0), 1.0)
    target = _EHP_TARGET.get(budget, 25000)
    ehp_factor = 0.4 + 0.6 * min(ehp / target, 1.0) ** 0.5
    return float(dps * pen * ehp_factor)


# ---------------------------------------------------------------------------
# Candidate build encoding (tree varies; gear / gems fixed)
# ---------------------------------------------------------------------------


class _Encoder:
    """Encodes a candidate tree (a set of regular node ids) into a PoB code,
    reusing the build's fixed gear + gems + ascendancy."""

    def __init__(self, intent: TheoryIntent, td: TreeData) -> None:
        self.intent = intent
        self.td = td
        self.start = td.class_starts[gen._CLASS_ID[intent.character_class]]
        self.gear = gen._select_gear(intent)
        self.skill = gen._find_active(intent.primary_skill)
        primary = GemLink(
            skill=self.skill.name,
            supports=gen._select_supports(self.skill, dmg=intent.damage_type),
            slot="Body Armour",
            label="Primary 6L",
        )
        self.base_links = gen._build_gem_layout(intent, primary, self.skill)
        self._pob_gear = gen._to_pob_gear(self.gear)
        # Ascendancy notables (display-only, fixed).
        self._asc = tuple(
            TreeNodeRef(node_id=n.id, name=n.name or "?", type="ascendancy")
            for n in sorted(
                (
                    n
                    for n in td.nodes_by_id.values()
                    if n.ascendancy_name == intent.ascendancy and n.is_notable and n.name
                ),
                key=lambda n: n.id,
            )[:4]
        )

    def gear_with_weapon(self, base_name: str) -> tuple[GearSlot, ...]:
        """The build's gear with the weapon slot's base swapped to *base_name*
        (priorities re-filtered for the new base)."""
        out: list[GearSlot] = []
        for g in self.gear:
            if g.slot in ("Weapon", "Bow", "Wand"):
                out.append(
                    GearSlot(
                        slot=g.slot,
                        base_name=base_name,
                        stat_priorities=gen._rollable_priorities(
                            gen._stat_priorities(g.slot, self.intent, self.skill),
                            base_name,
                            self.intent.budget,
                        ),
                        budget_tier=g.budget_tier,
                    )
                )
            else:
                out.append(g)
        return tuple(out)

    def _nodes(self, visited: set[int]) -> tuple[TreeNodeRef, ...]:
        td, it = self.td, self.intent
        out: list[TreeNodeRef] = [
            TreeNodeRef(node_id=self.start, name=f"{it.character_class} start", type="start")
        ]
        for nid in visited:
            if nid == self.start:
                continue
            n = td.nodes_by_id.get(nid)
            if n is None:
                continue
            t = "keystone" if n.is_keystone else "notable" if n.is_notable else "travel"
            out.append(TreeNodeRef(node_id=nid, name=n.name or "", type=t))  # type: ignore[arg-type]
        for nid, eff, name, stats in gen._select_masteries(
            visited, td, it.damage_type, it.defence_archetype
        ):
            out.append(
                TreeNodeRef(node_id=nid, name=name, type="mastery", stats=stats, effect_id=eff)
            )
        out.extend(self._asc)
        return tuple(out)

    def code(
        self,
        visited: set[int],
        links: tuple[GemLink, ...] | None = None,
        gear: tuple[GearSlot, ...] | None = None,
        pob_gear: StageGearSet | None = None,
        jewels: tuple[tuple[int, str], ...] = (),
    ) -> str:
        tree = gen._to_pob_tree(self.intent, self._nodes(visited))
        if pob_gear is not None:
            g = pob_gear
        elif gear is not None:
            g = gen._to_pob_gear(gear)
        else:
            g = self._pob_gear
        return encode_pob_code(
            character_class=self.intent.character_class,
            ascendancy=self.intent.ascendancy,
            tree=tree,
            gear=g,
            gems=gen._to_pob_gems(links if links is not None else self.base_links),
            level=90,
            jewels=jewels,
        )

    def with_primary_supports(self, supports: tuple[str, ...]) -> tuple[GemLink, ...]:
        """The build's links with the body 6L's supports replaced."""
        primary = GemLink(
            skill=self.skill.name, supports=supports, slot="Body Armour", label="Primary 6L"
        )
        return (primary, *self.base_links[1:])


# ---------------------------------------------------------------------------
# Connectivity + move proposals
# ---------------------------------------------------------------------------


def _connected(visited: set[int], start: int, adjacency: dict[int, frozenset[int]]) -> bool:
    seen: set[int] = set()
    stack = [start]
    while stack:
        x = stack.pop()
        if x in seen:
            continue
        seen.add(x)
        for nb in adjacency.get(x, frozenset()):
            if nb in visited and nb not in seen:
                stack.append(nb)
    return len(seen) == len(visited)


def _frontier(visited: set[int], td: TreeData, excluded: frozenset[int]) -> set[int]:
    out: set[int] = set()
    for v in visited:
        for nb in td.adjacency.get(v, frozenset()):
            if nb in visited or nb in excluded:
                continue
            if gen._is_fillable(td.nodes_by_id.get(nb), nb):
                out.add(nb)
    return out


def _propose_swaps(
    visited: set[int],
    td: TreeData,
    excluded: frozenset[int],
    dmg: str,
    defence: str,
    start: int,
    k: int,
) -> list[tuple[int, int]]:
    """Up to *k* (drop, add) swaps: worst-scored allocated node out, best
    frontier node in, keeping the allocation connected."""

    def score(nid: int) -> int:
        n = td.nodes_by_id.get(nid)
        return gen._score_node(n, dmg, defence) if n else 0

    removable = sorted((n for n in visited if n != start), key=score)[:8]
    frontier = sorted(_frontier(visited, td, excluded), key=score, reverse=True)[:8]
    swaps: list[tuple[int, int]] = []
    for r in removable:
        for a in frontier:
            cand = (visited - {r}) | {a}
            if a in cand and _connected(cand, start, td.adjacency):
                swaps.append((r, a))
                if len(swaps) >= k:
                    return swaps
    return swaps


# ---------------------------------------------------------------------------
# Optimiser
# ---------------------------------------------------------------------------


def optimize_links(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    *,
    pool_size: int = 12,
) -> tuple[tuple[GemLink, ...], float]:
    """Forward-select the body 6L's 5 supports from the top compatible pool
    to maximise PoB-exact fitness. Returns (best links, best fitness)."""
    pool = [
        s.name for s in gen._select_supports_raw(enc.skill, n=pool_size, dmg=intent.damage_type)
    ]
    chosen: list[str] = []
    cur_fit = -1.0
    while len(chosen) < 5 and pool:
        best_s, best_fit = None, cur_fit
        for cand in pool:
            if cand in chosen:
                continue
            trial = tuple([*chosen, cand] + ["(open)"] * (5 - len(chosen) - 1))
            try:
                stats = ev.evaluate(enc.code(visited, enc.with_primary_supports(trial)))
            except Exception:
                continue
            fit = fitness(stats, intent.budget)
            if fit > best_fit:
                best_fit, best_s = fit, cand
        if best_s is None:
            break
        chosen.append(best_s)
        cur_fit = best_fit
    supports = tuple(chosen + ["(open)"] * (5 - len(chosen)))
    print(f"[opt] best 6L supports: {chosen} | fit={cur_fit:.0f}")
    return enc.with_primary_supports(supports), cur_fit


# ---------------------------------------------------------------------------
# Auras (Step 66) — forward-select reservation skills, PoB-gated
# ---------------------------------------------------------------------------

_DMG_AURA: dict[str, str] = {
    "fire": "Anger",
    "cold": "Hatred",
    "lightning": "Wrath",
    "chaos": "Malevolence",
    "physical": "Pride",
}
_HERALD: dict[str, str] = {
    "fire": "Herald of Ash",
    "cold": "Herald of Ice",
    "lightning": "Herald of Thunder",
    "physical": "Herald of Purity",
}


def _aura_candidates(intent: TheoryIntent, skill: gen._Active) -> list[str]:
    """Build-relevant auras/heralds to try, best-first. PoB's mana-reservation
    is the real constraint — the forward-select keeps adding only while real
    fitness rises, so an over-reserved combo is simply not taken."""
    dmg = intent.damage_type
    is_attack = "attack" in skill.tags
    is_dot = "damageovertime" in skill.tags or "chillingarea" in skill.tags
    is_es = intent.defence_archetype == "es"
    out: list[str] = []
    # Primary damage aura.
    da = _DMG_AURA.get(dmg) if (dmg != "physical" or is_attack) else None
    if da:
        out.append(da)
    if is_dot and "Malevolence" not in out:
        out.append("Malevolence")
    # A spell-crit / generic second offensive aura.
    if not is_attack:
        out.append("Zealotry")
    # Herald (extra hit/clear damage).
    h = _HERALD.get(dmg)
    if h:
        out.append(h)
    # Defensive reservation.
    out.append("Discipline" if is_es else "Determination")
    out.append("Grace")
    known = _known_active_names()
    deduped: list[str] = []
    for a in out:
        if a in known and a not in deduped:
            deduped.append(a)
    return deduped


def _known_active_names() -> set[str]:
    actives, _ = gen._gem_catalogue()
    return {a.name for a in actives}


# Generic reservation-efficiency notables (apply to all skills, so any aura
# benefits). Pathed into the tree on demand when an extra aura would
# otherwise over-reserve — PoB only applies a node's stats when it's
# *connected* to the tree, so a disconnected notable does nothing.
#   6799  Charisma            16% increased Mana Reservation Efficiency
#   32932 Sovereignty         12% + 10% increased effect of Non-Curse Auras
#   33718 Champion of the Cause 8% + 12% aura AoE
#   58851 Leader of the Pack  12% + 20% aura AoE
_RES_EFF_NODES: tuple[int, ...] = (6799, 32932, 33718, 58851)

# Labels of the base-layout single-aura group(s) we replace with one proper
# multi-aura group (so the auras actually buff the player, not the wasteful
# Generosity'd ally-only aura the base layout ships).
_BASE_AURA_LABELS = frozenset({"Utility 4L", "Aura", "Auras"})


def _aura_group_link(auras: list[str]) -> GemLink:
    """One socket group: the auras as active gems + Enlighten linked to all
    of them (so PoB applies Enlighten's reservation efficiency to every
    aura). Enlighten is only added when there are >= 2 auras (it does nothing
    for a single gem and wastes a socket otherwise)."""
    supports = ("Enlighten",) if len(auras) >= 2 else ()
    return GemLink(
        skill=auras[0],
        extra_actives=tuple(auras[1:]),
        supports=supports,
        slot="Helmet",
        label="Auras",
    )


def _path_node_in(visited: set[int], node: int, td: TreeData) -> tuple[set[int], int]:
    """Connect *node* to *visited* over the regular tree, returning
    (new_visited, added_point_count). Returns (visited, -1) when no all-
    fillable path exists. The connection is required because PoB ignores the
    stats of a disconnected allocated node."""
    if node in visited:
        return visited, 0
    for start in visited:
        p = gen.bfs_path(td.adjacency, start, node)
        if p is not None and all(
            n in visited or gen._is_fillable(td.nodes_by_id.get(n), n) for n in p
        ):
            v2 = visited | set(p)
            return v2, len(v2) - len(visited)
    return visited, -1


def optimize_auras(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    pob_gear: StageGearSet,
    jewels: tuple[tuple[int, str], ...] = (),
    *,
    max_auras: int = 4,
    max_res_points: int = 12,
) -> tuple[tuple[GemLink, ...], set[int], float]:
    """Build one multi-aura group (auras + Enlighten) and forward-select the
    auras that genuinely raise PoB-exact fitness.

    Reservation is enforced by PoB + the fitness gate (over-reserving ->
    ``ManaUnreserved`` negative -> 0.1x penalty), so an aura that doesn't fit
    is never kept. When an aura *would* fit but for reservation, the search
    tries pathing in a generic reservation-efficiency notable (bounded by
    ``max_res_points`` to keep the point budget sane). Runs on the *final*
    build (tree + uniques + jewels), so it sees the real mana pool.

    Returns (links, visited, fitness): ``links`` has the base single-aura
    group replaced by the multi-aura group; ``visited`` carries any pathed
    reservation notables.
    """
    td = get_tree_data()
    core = tuple(link for link in links if link.label not in _BASE_AURA_LABELS)
    pool = _aura_candidates(intent, enc.skill)

    def _code(auras: list[str], v: set[int]) -> str:
        lk = core if not auras else (*core, _aura_group_link(auras))
        return enc.code(v, lk, pob_gear=pob_gear, jewels=jewels)

    chosen: list[str] = []
    best_visited = set(visited)
    cur_fit = fitness(ev.evaluate(_code(chosen, best_visited)), intent.budget)

    while len(chosen) < max_auras and pool:
        best_a, best_fit, best_v = None, cur_fit, best_visited
        for cand in pool:
            if cand in chosen:
                continue
            trial = [*chosen, cand]
            try:
                stats = ev.evaluate(_code(trial, best_visited))
            except Exception:
                continue
            fit = fitness(stats, intent.budget)
            tv = best_visited
            # Over-reserved? Try pathing a reservation-efficiency notable so
            # the aura can fit honestly (bounded point cost).
            if stats.get("ManaUnreserved", 0.0) < -10:
                for rn in _RES_EFF_NODES:
                    if rn in best_visited:
                        continue
                    v2, cost = _path_node_in(best_visited, rn, td)
                    if cost < 0 or (len(v2) - len(visited)) > max_res_points:
                        continue
                    try:
                        st2 = ev.evaluate(_code(trial, v2))
                    except Exception:
                        continue
                    f2 = fitness(st2, intent.budget)
                    if f2 > fit:
                        fit, tv = f2, v2
            if fit > best_fit * 1.001:
                best_fit, best_a, best_v = fit, cand, tv
        if best_a is None:
            break
        chosen.append(best_a)
        best_visited = best_v
        cur_fit = best_fit
    final_links = core if not chosen else (*core, _aura_group_link(chosen))
    if chosen:
        extra = len(best_visited) - len(visited)
        print(f"[opt] auras: {chosen} (+{extra} res pts) | fit={cur_fit:.0f}")
    return final_links, best_visited, cur_fit


def _weapon_candidates(intent: TheoryIntent, enc: _Encoder, n: int) -> list[str]:
    """Top-*n* weapon bases of the build's resolved weapon class.

    Mirrors `_select_gear`'s weapon-class choice (bow / melee 2H sword /
    wand), then returns the highest-drop-level bases of that class within
    the budget cap — the generator picks #1; the optimiser tries the rest.
    """
    skill = enc.skill
    if "bow" in skill.tags or gen._is_bow_skill(skill):
        weapon_class = "Bow"
    elif "melee" in skill.tags or ("attack" in skill.tags and "wandattack" not in skill.tags):
        weapon_class = "Two Hand Sword"
    else:
        weapon_class = "Wand"
    cap = gen._BUDGET_DROP_CAP[intent.budget]
    pool = [
        b
        for b in get_base_catalogue()
        if b.slot in (ItemSlot.WEAPON_MAIN,)
        and b.item_class == weapon_class
        and (b.drop_level or 0) <= cap
    ]
    pool.sort(key=lambda b: (b.drop_level or 0, b.name), reverse=True)
    return [b.name for b in pool[:n]]


def optimize_weapon(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    *,
    n_candidates: int = 4,
) -> tuple[tuple[GearSlot, ...], float]:
    """Pick the weapon base (among the top candidates of the right class)
    that maximises PoB-exact fitness. The weapon is the #1 DPS lever, so
    this is the highest-value gear co-optimisation. Returns (best gear
    tuple, best fitness)."""
    candidates = _weapon_candidates(intent, enc, n_candidates)
    best_gear = enc.gear
    best_fit = -1.0
    best_base = None
    for base in candidates:
        gear = enc.gear_with_weapon(base)
        try:
            stats = ev.evaluate(enc.code(visited, links, gear))
        except Exception:
            continue
        fit = fitness(stats, intent.budget)
        if fit > best_fit:
            best_fit, best_gear, best_base = fit, gear, base
    print(f"[opt] best weapon base: {best_base} | fit={best_fit:.0f}")
    return best_gear, best_fit


def _weapon_class_ok(intent: TheoryIntent, enc: _Encoder, u: UniqueItem) -> bool:
    """A weapon unique must match the build's resolved weapon class
    (don't put a 2H sword unique on a wand caster)."""
    want = _weapon_candidates(intent, enc, 1)
    if not want:
        return False
    target = base_for_name(want[0])
    cand = base_for_name(u.base_type)
    return bool(target and cand and cand.item_class == target.item_class)


def optimize_uniques(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    base_gear: StageGearSet,
    *,
    per_slot: int = 8,
) -> tuple[StageGearSet, float, dict[ItemSlot, UniqueItem]]:
    """Per slot, try the most build-relevant candidate uniques against the
    current (rare) item and keep whichever maximises PoB-exact fitness.

    Greedy + independent per slot (bounded eval budget): each accepted
    unique is locked in before the next slot is considered. Candidates are
    preselected by keyword relevance (`gen._score_text`) — PoB fitness makes
    the final call. Returns (best StageGearSet, best fitness).
    """
    dmg, defence = intent.damage_type, intent.defence_archetype
    skill = enc.skill
    score_dmg = "minion" if "minion" in skill.tags else dmg

    slots = list(base_gear.slots)
    chosen: dict[ItemSlot, UniqueItem] = {}
    cur_fit = fitness(ev.evaluate(enc.code(visited, links, pob_gear=base_gear)), intent.budget)

    for i, slot in enumerate(slots):
        uslot = _UNIQUE_SLOT.get(slot.slot)
        if uslot is None:
            continue
        cands = list(uniques_for_slot(uslot))
        if uslot == "weapon":
            cands = [u for u in cands if _weapon_class_ok(intent, enc, u)]
        # Preselect by relevance to the build's damage + defence.
        cands.sort(
            key=lambda u: gen._score_text(" ".join(u.mods), score_dmg, defence), reverse=True
        )
        best_slot_fit = cur_fit
        best_slot = slot
        best_u: UniqueItem | None = None
        for u in cands[:per_slot]:
            trial = list(slots)
            trial[i] = StageGearSlot(
                slot=slot.slot, item_name=unique_pob_body(u), kind="rare_craft", notes=u.name
            )
            try:
                stats = ev.evaluate(
                    enc.code(
                        visited, links, pob_gear=StageGearSet(stage_key="opt", slots=tuple(trial))
                    )
                )
            except Exception:
                continue
            fit = fitness(stats, intent.budget)
            if fit > best_slot_fit * 1.001:
                best_slot_fit, best_slot, best_u = fit, trial[i], u
        if best_u is not None:
            slots[i] = best_slot
            cur_fit = best_slot_fit
            chosen[slot.slot] = best_u
            print(f"[opt] {slot.slot.value}: unique {best_u.name} | fit={cur_fit:.0f}")
    return StageGearSet(stage_key="opt", slots=tuple(slots)), cur_fit, chosen


def optimize_tree(
    intent: TheoryIntent,
    ev: PobEvaluator,
    *,
    links: tuple[GemLink, ...] | None = None,
    gear: tuple[GearSlot, ...] | None = None,
    pob_gear: StageGearSet | None = None,
    max_iters: int = 25,
    swaps_per_iter: int = 8,
) -> tuple[set[int], dict[str, float], dict[str, float]]:
    """Returns (best_visited, base_stats, best_stats)."""
    td = get_tree_data()
    enc = _Encoder(intent, td)
    excluded = gen._excluded_weapon_ids(intent, td)
    start = enc.start

    base = generate_build(intent)
    visited: set[int] = {start} | {
        n.node_id for n in base.tree_nodes if n.type in ("keystone", "notable", "travel")
    }
    base_stats = ev.evaluate(enc.code(visited, links, gear, pob_gear))
    best_fit = fitness(base_stats, intent.budget)
    best_stats = base_stats
    print(
        f"[opt] start: {len(visited)} nodes | DPS={base_stats.get('FullDPS', 0):.0f} "
        f"EHP={base_stats.get('TotalEHP', 0):.0f} fit={best_fit:.0f}"
    )

    for it in range(max_iters):
        swaps = _propose_swaps(
            visited,
            td,
            excluded,
            intent.damage_type,
            intent.defence_archetype,
            start,
            swaps_per_iter,
        )
        improved = False
        for r, a in swaps:
            cand = (visited - {r}) | {a}
            try:
                stats = ev.evaluate(enc.code(cand, links, gear, pob_gear))
            except Exception:
                continue
            fit = fitness(stats, intent.budget)
            if fit > best_fit * 1.001:  # require a real (>0.1%) gain
                visited, best_fit, best_stats = cand, fit, stats
                improved = True
                print(
                    f"[opt] iter {it + 1}: swap {r}->{a} | DPS={stats.get('FullDPS', 0):.0f} "
                    f"EHP={stats.get('TotalEHP', 0):.0f} fit={fit:.0f}"
                )
                break
        if not improved:
            print(f"[opt] local optimum at iter {it + 1}")
            break

    return visited, base_stats, best_stats


# ---------------------------------------------------------------------------
# Timeless Jewel — LUT god-seed search (Step 63)
# ---------------------------------------------------------------------------


# Timeless jewels. The *additive* types (Lethal Pride / Brutal Restraint /
# Militant Faith / Heroic Tragedy) give an in-radius notable one `readLUT`
# addition; Glorious Vanity (type 1) instead REPLACES in-radius nodes with
# Vaal nodes (a `readLUT` value >= `timelessJewelAdditions` is a replacement
# id) and its conquerors grant build-defining keystones (Corrupted Soul /
# Divine Flesh / Immortal Ambition), so all three are tried in the eval.
# Each type has its own seed-bearing flavour line + radius-transform line
# (from PoB's data). Elegant Hubris (type 5) is omitted: its readLUT divides
# the seed by 20, a special case left for later.
class _JewelType(NamedTuple):
    name: str
    seed_min: int
    seed_max: int
    conquerors: tuple[str, ...]  # tried in the eval; first is the default
    seed_line: str  # "{seed}" + "{conq}" placeholders
    transform: str


_TIMELESS_TYPES: dict[int, _JewelType] = {
    1: _JewelType(
        "Glorious Vanity",
        100,
        8000,
        ("Doryani", "Xibaqua", "Ahuana"),
        "Bathed in the blood of {seed} sacrificed in the name of {conq}",
        "Passives in radius are Conquered by the Vaal",
    ),
    2: _JewelType(
        "Lethal Pride",
        10000,
        18000,
        ("Kaom",),
        "Commanded leadership over {seed} warriors under {conq}",
        "Passives in radius are Conquered by the Karui",
    ),
    3: _JewelType(
        "Brutal Restraint",
        500,
        8000,
        ("Asenath",),
        "Denoted service of {seed} dekhara in the akhara of {conq}",
        "Passives in radius are Conquered by the Maraketh",
    ),
    4: _JewelType(
        "Militant Faith",
        2000,
        10000,
        ("Avarius",),
        "Carved to glorify {seed} new faithful converted by High Templar {conq}",
        "Passives in radius are Conquered by the Templars",
    ),
    6: _JewelType(
        "Heroic Tragedy",
        100,
        8000,
        ("Vorana",),
        "Remembrancing {seed} songworthy deeds by the line of {conq}",
        "Passives in radius are Conquered by the Kalguur",
    ),
}


def _timeless_jewel_text(jtype: int, seed: int, conqueror: str) -> str:
    """PoB item body for a timeless jewel (type/seed/conqueror)."""
    t = _TIMELESS_TYPES[jtype]
    return "\n".join(
        [
            "Rarity: UNIQUE",
            t.name,
            "Timeless Jewel",
            "Radius: Large",
            "Implicits: 0",
            t.seed_line.format(seed=seed, conq=conqueror),
            t.transform,
            "Historic",
        ]
    )


@lru_cache(maxsize=1)
def _jewel_socket_ids() -> frozenset[int]:
    """Regular-tree jewel-socket node ids (from the raw vendored tree)."""
    path = (
        Path(__file__).resolve().parent.parent / "packages" / "fob" / "data" / "tree" / "3_28.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: set[int] = set()
    for nid, n in raw.get("nodes", {}).items():
        if n.get("isJewelSocket") and nid.isdigit() and int(nid) < 65536:
            out.add(int(nid))
    return frozenset(out)


# Keyword sets for scoring the seed's notable additions (Lua-side, lowercased).
_DEF_KW = ("maximum life", "energy shield", "resist", "armour", "evasion", "leech", "regenerat")


def _search_seed(
    ev: PobEvaluator, socket: int, jtype: int, alloc_notables: set[int], keywords: tuple[str, ...]
) -> tuple[int, int]:
    """Scan a timeless jewel's LUT for the seed whose additions on the socket's
    in-radius *allocated* notables best match *keywords*. Returns (seed, score).
    Runs entirely in PoB's Lua state (fast — table lookups, no calc)."""
    t = _TIMELESS_TYPES[jtype]
    alloc = "".join(f"[{n}]=true," for n in alloc_notables)
    kw = ",".join(f'"{k}"' for k in keywords)
    chunk = _SEED_SEARCH_TMPL % {
        "socket": socket,
        "jtype": jtype,
        "alloc": alloc,
        "kw": kw,
        "smin": t.seed_min,
        "smax": t.seed_max,
    }
    out = ev._run_chunk(chunk).strip()
    if "=" not in out:
        return (t.seed_min, -1)
    seed_s, _, score_s = out.partition("=")
    try:
        return (int(seed_s), int(score_s))
    except ValueError:
        return (t.seed_min, -1)


_SEED_SEARCH_TMPL = r"""
local socketId, jewelType = %(socket)d, %(jtype)d
local allocNotables = {%(alloc)s}
local keywords = {%(kw)s}
local seedMin, seedMax = %(smin)d, %(smax)d
local tree = build.spec.tree
if not tree or not tree.legion or not tree.nodes[socketId] then return "" end
local rIdx
for i, r in pairs(data.jewelRadius) do if r.label == "Large" then rIdx = i end end
local socket = tree.nodes[socketId]
if not rIdx or not socket.nodesInRadius or not socket.nodesInRadius[rIdx] then return "" end
local add = tree.legion.additions
local nodeIDList = data.nodeIDList
local sizeNotable = nodeIDList["sizeNotable"]
local targets = {}
for nid in pairs(socket.nodesInRadius[rIdx]) do
  local nidn = tonumber(nid) or nid
  if allocNotables[nidn] and nodeIDList[nidn] and nodeIDList[nidn].index
     and nodeIDList[nidn].index <= sizeNotable then
    targets[#targets+1] = nidn
  end
end
if #targets == 0 then return "" end
local nodes = tree.legion.nodes
local NA = data.timelessJewelAdditions
local function scoreSd(sd)
  local s = 0
  for _, line in ipairs(sd) do
    local low = line:lower()
    for _, w in ipairs(keywords) do if low:find(w, 1, true) then s = s + 1 end end
  end
  return s
end
local bestSeed, bestScore = seedMin, -1
for seed = seedMin, seedMax do
  local sc = 0
  for _, nid in ipairs(targets) do
    local r = data.readLUT(seed, nid, jewelType)
    if r and r[1] then
      -- Glorious Vanity (and any value >= NA) REPLACES the node with a Vaal
      -- node; below NA it's an addition. Score whichever stat block applies.
      local sd
      if r[1] >= NA then
        local n = nodes[r[1] + 1 - NA]
        sd = n and n.sd
      else
        local a = add[r[1] + 1]
        sd = a and a.sd
      end
      if sd then sc = sc + scoreSd(sd) end
    end
  end
  if sc > bestScore then bestScore = sc; bestSeed = seed end
end
return tostring(bestSeed) .. "=" .. tostring(bestScore)
"""


_SOCKET_RANK_TMPL = r"""
local allocNotables = {%(alloc)s}
local sockets = {%(sockets)s}
local tree = build.spec.tree
if not tree or not tree.legion then return "" end
local rIdx
for i, r in pairs(data.jewelRadius) do if r.label == "Large" then rIdx = i end end
if not rIdx then return "" end
local nodeIDList = data.nodeIDList
local sizeNotable = nodeIDList["sizeNotable"]
local out = {}
for _, sid in ipairs(sockets) do
  local socket = tree.nodes[sid]
  local count = 0
  if socket and socket.nodesInRadius and socket.nodesInRadius[rIdx] then
    for nid in pairs(socket.nodesInRadius[rIdx]) do
      local nidn = tonumber(nid) or nid
      if allocNotables[nidn] and nodeIDList[nidn] and nodeIDList[nidn].index
         and nodeIDList[nidn].index <= sizeNotable then
        count = count + 1
      end
    end
  end
  if count > 0 then out[#out+1] = sid .. ":" .. count end
end
return table.concat(out, ",")
"""


def _rank_jewel_sockets(
    ev: PobEvaluator, alloc_notables: set[int], socket_ids: frozenset[int]
) -> list[tuple[int, int]]:
    """Return [(socket, in-radius allocated-notable count)] best-first."""
    alloc = "".join(f"[{n}]=true," for n in alloc_notables)
    sockets = ",".join(str(s) for s in sorted(socket_ids))
    out = ev._run_chunk(_SOCKET_RANK_TMPL % {"alloc": alloc, "sockets": sockets}).strip()
    ranked: list[tuple[int, int]] = []
    for pair in out.split(","):
        if ":" in pair:
            sid, _, cnt = pair.partition(":")
            try:
                ranked.append((int(sid), int(cnt)))
            except ValueError:
                continue
    ranked.sort(key=lambda x: -x[1])
    return ranked


def optimize_timeless(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    pob_gear: StageGearSet,
) -> tuple[set[int], tuple[tuple[int, str], ...], float]:
    """Add a Lethal Pride timeless jewel if it improves PoB-exact fitness.

    Ranks every jewel socket by how many *allocated* notables fall in its
    Large radius, paths to the best few (BFS over the regular tree), searches
    the LUT for the seed whose additions on those notables best match the
    build's keywords, then full-evals the top seed across conquerors. Keeps
    the best socket+seed+conqueror — fitness-gated, so a jewel is added only
    when it genuinely helps.

    Returns (visited, jewels, fitness). ``jewels`` is the (socket, item_text)
    tuple to pass to ``enc.code`` / ``encode_pob_code``.
    """
    td = get_tree_data()
    score_dmg = "minion" if "minion" in enc.skill.tags else intent.damage_type
    keywords = tuple(gen._DAMAGE_KEYWORDS.get(score_dmg, ())) + _DEF_KW

    # The seed search needs a build loaded (build.spec.tree). Load the base.
    base_code = enc.code(visited, links, pob_gear=pob_gear)
    cur_fit = fitness(ev.evaluate(base_code), intent.budget)

    alloc_notables = {n for n in visited if (nd := td.nodes_by_id.get(n)) and nd.is_notable}
    # Rank sockets by in-radius allocated-notable coverage; path to the best.
    ranked = _rank_jewel_sockets(ev, alloc_notables, _jewel_socket_ids())

    best_jewels: tuple[tuple[int, str], ...] = ()
    best_visited = visited
    best_label = ""
    for socket, _count in ranked[:3]:
        # Path to the socket over the regular tree (allocate the connecting
        # travel). bfs_path needs a connected start in `visited`.
        path = None
        for start in visited:
            p = gen.bfs_path(td.adjacency, start, socket)
            if p is not None and all(
                n in visited or gen._is_fillable(td.nodes_by_id.get(n), n) for n in p
            ):
                path = p
                break
        if path is None:
            continue
        v2 = visited | set(path)
        # Try every jewel type at this socket — search its best seed, full-eval
        # it across the type's conquerors, keep whichever maximises real
        # fitness. Glorious Vanity's conquerors are build-defining keystones,
        # so all three are tried; additive types try just their default.
        for jtype, t in _TIMELESS_TYPES.items():
            seed, score = _search_seed(ev, socket, jtype, alloc_notables, keywords)
            if score <= 0:
                continue
            for conq in t.conquerors:
                jewels = ((socket, _timeless_jewel_text(jtype, seed, conq)),)
                try:
                    stats = ev.evaluate(enc.code(v2, links, pob_gear=pob_gear, jewels=jewels))
                except Exception:
                    continue
                fit = fitness(stats, intent.budget)
                if fit > cur_fit * 1.001:
                    cur_fit, best_jewels, best_visited = fit, jewels, v2
                    best_label = f"{t.name} ({conq}, socket {socket}, seed {seed})"
    if best_jewels:
        print(f"[opt] timeless: {best_label} | fit={cur_fit:.0f}")
    return best_visited, best_jewels, cur_fit


def _demo() -> int:
    intent = TheoryIntent(
        character_class="Marauder",
        ascendancy="Juggernaut",
        primary_skill="Cyclone",
        damage_type="physical",
        defence_archetype="life",
        budget="endgame",
        focus="allcontent",
    )
    ev = PobEvaluator()
    td = get_tree_data()
    enc = _Encoder(intent, td)
    base = generate_build(intent)
    visited0 = {enc.start} | {
        n.node_id for n in base.tree_nodes if n.type in ("keystone", "notable", "travel")
    }
    base_stats = ev.evaluate(enc.code(visited0))
    _bd, _be = base_stats.get("FullDPS", 0), base_stats.get("TotalEHP", 0)
    print(f"[opt] base: DPS={_bd:.0f} EHP={_be:.0f}")

    print("[opt] --- optimising 6L supports ---")
    best_links, _ = optimize_links(intent, ev, enc, visited0)
    print("[opt] --- optimising tree ---")
    _, _, best_stats = optimize_tree(intent, ev, links=best_links)

    print("\n=== before -> after (PoB-exact) ===")
    keys = (
        "FullDPS",
        "TotalDPS",
        "TotalEHP",
        "Life",
        "FireResist",
        "ColdResist",
        "LightningResist",
    )
    for k in keys:
        print(f"  {k:16} {base_stats.get(k, 0):>12.0f}  ->  {best_stats.get(k, 0):>12.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_demo())
