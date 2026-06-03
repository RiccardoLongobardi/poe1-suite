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
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pob_eval import PobEvaluator, decode_pob_code  # type: ignore[import-not-found]  # sibling

from poe1_core.models.enums import ItemSlot
from poe1_fob.gear import clusters as cl
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

# Encode the optimised build at a mirror-tier character level (the level a
# "best version" actually is), so the realistic passive-point budget below is
# the right yardstick and PoB's life/level scaling is honest.
_CHAR_LEVEL = 100
# Realistic regular-tree passive-point budget at level 100: 99 from levels +
# 22 quest points + 2 from killing all bandits = 123. Masteries and a jewel
# socket each cost one of these points; the class start is free. The
# optimiser's timeless + aura passes can push the allocation past this, so the
# final build is trimmed back to it (`_trim_to_budget`) — a build needing 144
# points is not playable, and "niente fittizio" forbids serving one.
_TREE_POINT_BUDGET = 123

# Fase 6 (CoC): the trigger 6L supports — Cast On Critical Strike (the
# mechanism) + the triggered spell's crit/cold scaling. The trigger attack
# (Cyclone) crits → CoC casts the spell; Increased Critical Strikes lifts the
# attack's crit (→ trigger rate), Hypothermia/Cold Penetration scale the spell.
_COC_SUPPORTS: tuple[str, ...] = (
    "Cast On Critical Strike",
    "Increased Critical Strikes",
    "Hypothermia",
    "Cold Penetration",
)

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

    def __init__(
        self, intent: TheoryIntent, td: TreeData, *, coc_trigger: str | None = None
    ) -> None:
        self.intent = intent
        self.td = td
        self.start = td.class_starts[gen._CLASS_ID[intent.character_class]]
        self.gear = gen._select_gear(intent)
        self.skill = gen._find_active(intent.primary_skill)
        self.coc_trigger = coc_trigger
        if coc_trigger is not None:
            # Fase 6: a Cast-on-Critical-Strike build — a trigger attack
            # (coc_trigger, e.g. Cyclone) casts the spell (intent.primary_skill,
            # e.g. Ice Nova) on crit. The triggered spell is the DPS; its
            # supports are CoC + the spell's crit/element scaling.
            primary = GemLink(
                skill=coc_trigger,
                extra_actives=(self.skill.name,),
                supports=_COC_SUPPORTS,
                slot="Body Armour",
                label="CoC 6L",
            )
        else:
            # Step 74: a best-version build runs a corrupted 21/23 main skill gem
            # (standard min-max — Vaal orb / +1 gear). Measured +13% on Vortex.
            primary = GemLink(
                skill=self.skill.name,
                supports=gen._select_supports(self.skill, dmg=intent.damage_type),
                slot="Body Armour",
                label="Primary 6L",
                skill_level=21,
                skill_quality=23,
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
        clusters: tuple[tuple[int, str, tuple[int, ...]], ...] = (),
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
            level=_CHAR_LEVEL,
            jewels=jewels,
            clusters=clusters,
        )

    def with_primary_supports(self, supports: tuple[str, ...]) -> tuple[GemLink, ...]:
        """The build's links with the body 6L's supports replaced (preserving
        the primary's 21/23 level/quality override)."""
        primary = self.base_links[0].model_copy(update={"supports": supports})
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


# ---------------------------------------------------------------------------
# Awakened support upgrade (Step 73) — endgame / best-version gem quality
# ---------------------------------------------------------------------------

# Empower/Enhance/Enlighten are utility (handled by the base layout / aura
# group); their Awakened forms aren't a damage upgrade to swap here.
_AWAKENED_SKIP = frozenset({"Empower", "Enhance", "Enlighten"})


def optimize_awakened(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    pob_gear: StageGearSet,
    jewels: tuple[tuple[int, str], ...] = (),
) -> tuple[GemLink, ...]:
    """Upgrade the primary 6L's damage supports to their Awakened versions
    where they raise PoB-exact fitness.

    An Awakened damage support is strictly stronger (higher gem level + an
    extra effect, e.g. Awakened Elemental Focus adds penetration), so this is
    a near-monotonic ~+10-15% per gem (measured ~x1.5 across a Vortex 6L). The
    encoder maps "Awakened X" -> "SupportXPlus" (PoB's convention). Best-
    version only (the live generator keeps the current-league gem allowlist).
    """
    _, supports_cat = gen._gem_catalogue()
    known = {s.name for s in supports_cat}
    primary = links[0]
    cur = list(primary.supports)

    def _fit(supports: list[str]) -> float:
        lk = (primary.model_copy(update={"supports": tuple(supports)}), *links[1:])
        return fitness(
            ev.evaluate(enc.code(visited, lk, pob_gear=pob_gear, jewels=jewels)), intent.budget
        )

    cur_fit = _fit(cur)
    for i, s in enumerate(cur):
        if s == "(open)" or s in _AWAKENED_SKIP or s.startswith("Awakened "):
            continue
        aw = f"Awakened {s}"
        if aw not in known:
            continue
        trial = list(cur)
        trial[i] = aw
        try:
            f = _fit(trial)
        except Exception:
            continue
        if f > cur_fit:  # strictly better — Awakened never hurts
            cur, cur_fit = trial, f
    if cur != list(primary.supports):
        print(
            f"[opt] awakened: {[s for s in cur if s.startswith('Awakened ')]} | fit={cur_fit:.0f}"
        )
    return (primary.model_copy(update={"supports": tuple(cur)}), *links[1:])


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


# ---------------------------------------------------------------------------
# Chest-forbidding helmet (The Bringer of Rain) — re-socket the 6L (Step 70)
# ---------------------------------------------------------------------------


def _forbids_chest(u: UniqueItem) -> bool:
    """True if the helmet unique forbids a body armour (The Bringer of Rain's
    "Can't use Chest armour"). PoB then voids the equipped body, so socketing
    the main 6L there is fictional — it must go in the helmet itself."""
    return any("Can't use Chest armour" in m for m in u.mods)


def _relocate_no_chest(links: tuple[GemLink, ...]) -> tuple[GemLink, ...]:
    """Re-socket for a chest-forbidding helmet: the primary 6L moves into the
    Helmet (the only legal socketing — a body the helmet forbids was
    fictional). In the Helmet it picks up the unique's built-in "Socketed
    Gems are Supported by …" supports (e.g. The Bringer of Rain's free
    level-30 Melee Physical Damage / Faster Attacks). Every other group keeps
    its slot (changing them would only perturb the greedy passes; the one
    fictional thing was the primary in a non-existent body)."""
    return (links[0].model_copy(update={"slot": "Helmet"}), *links[1:])


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
    the final call. Returns (best StageGearSet, best fitness, chosen uniques).

    Note: a chest-forbidding helmet (The Bringer of Rain) is evaluated here
    with the body still present (the greedy per-slot stage undervalues it
    otherwise — dropping the body's defences before the build is built up
    looks bad). The honest re-socketing (6L → helmet) is applied as a final
    pass on the *complete* build (`relocate_no_chest_build` in the pipeline).
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


def optimize_flasks(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    base_gear: StageGearSet,
    jewels: tuple[tuple[int, str], ...] = (),
    *,
    per_slot: int = 14,
) -> tuple[StageGearSet, float, dict[int, str]]:
    """Forward-select unique flasks for the flask slots, fitness-gated.

    A mirror build runs powerful unique flasks — Bottled Faith (consecrated
    ground → more damage + crit), The Wise Oak (elemental penetration), Taste
    of Hate (phys taken as cold + extra cold), Dying Sun (AoE/projectiles),
    Atziri's Promise (extra chaos + leech). The generated build only had plain
    utility flasks (Eternal Mana / Quicksilver), so PoB applied ~0 flask
    damage. Crucially flasks cost **no passive points**, so this never trades
    EHP (unlike the tree/cluster passes) — it's a clean DPS *and* defence lever.

    The first flask slot is kept (life/mana — sustain is non-negotiable); slots
    2-5 are forward-selected from the unique pool, each kept only if it raises
    PoB-exact fitness, never repeating a unique. Flask slots are already
    ``active="true"`` in the encode, so PoB applies their effects — the served
    DPS is the standard "flasks up" combat number every ladder build reports.
    """
    score_dmg = "minion" if "minion" in enc.skill.tags else intent.damage_type
    defence = intent.defence_archetype
    slots = list(base_gear.slots)
    flask_idx = [i for i, s in enumerate(slots) if s.slot == ItemSlot.FLASK]
    if len(flask_idx) < 2:
        return (
            base_gear,
            fitness(
                ev.evaluate(enc.code(visited, links, pob_gear=base_gear, jewels=jewels)),
                intent.budget,
            ),
            {},
        )
    cands = list(uniques_for_slot("flask"))
    cands.sort(key=lambda u: gen._score_text(" ".join(u.mods), score_dmg, defence), reverse=True)
    cur_fit = fitness(
        ev.evaluate(enc.code(visited, links, pob_gear=base_gear, jewels=jewels)), intent.budget
    )
    used: set[str] = set()
    chosen: dict[int, str] = {}  # flask ordinal (0-based) -> unique name, for display
    for ordinal, i in enumerate(flask_idx):
        if ordinal == 0:
            continue  # keep slot 1 (life/mana) for sustain
        best_fit, best_slot, best_name = cur_fit, None, None
        for u in cands[:per_slot]:
            if u.name in used:
                continue
            trial = list(slots)
            trial[i] = StageGearSlot(
                slot=ItemSlot.FLASK, item_name=unique_pob_body(u), kind="rare_craft", notes=u.name
            )
            try:
                stats = ev.evaluate(
                    enc.code(
                        visited,
                        links,
                        pob_gear=StageGearSet(stage_key="opt", slots=tuple(trial)),
                        jewels=jewels,
                    )
                )
            except Exception:
                continue
            fit = fitness(stats, intent.budget)
            if fit > best_fit * 1.001:
                best_fit, best_slot, best_name = fit, trial[i], u.name
        if best_slot is not None and best_name is not None:
            slots[i] = best_slot
            cur_fit = best_fit
            used.add(best_name)
            chosen[ordinal] = best_name
            print(f"[opt] flask: {best_name} | fit={cur_fit:.0f}")
    return StageGearSet(stage_key="opt", slots=tuple(slots)), cur_fit, chosen


_ANOINT_ELEMS = ("fire", "cold", "lightning")


def _anoint_score(stats: tuple[str, ...], dmg: str) -> int:
    """Score a notable as an *anoint* candidate by DAMAGE only (the anoint is a
    single free notable — make it carry damage, not the defensive notable a
    survival-weighted scorer would pick). DoT multiplier weighted highest.

    A notable that scales a *foreign* element (e.g. a Fire notable on a Lightning
    build) is rejected even if PoB finds it a marginal gain — it reads as a
    mistake to a real player. Build-element + element-agnostic multipliers
    (crit / DoT) only.
    """
    s = " ".join(stats).lower()
    elem = sum(3 for k in gen._DAMAGE_KEYWORDS.get(dmg, ()) if k in s)
    # Reject a notable that scales an element this build doesn't use.
    foreign = any(e in s for e in _ANOINT_ELEMS if e != dmg)
    if foreign and elem == 0:
        return 0
    v = elem
    if "damage over time multiplier" in s:
        v += 7
    if "critical strike multiplier" in s:
        v += 2
    if ("penetrat" in s or "exposure" in s) and elem > 0:
        v += 3
    return v


def optimize_anoint(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    base_gear: StageGearSet,
    jewels: tuple[tuple[int, str], ...] = (),
    *,
    top_n: int = 12,
) -> tuple[StageGearSet, float, str | None]:
    """Anoint the amulet with the best damage notable, fitness-gated.

    Every mirror build anoints its amulet — a free tree notable (Blight oils)
    with **no passive-point cost**, so like flasks this never trades EHP. The
    candidate pool is the build's *unallocated* regular notables scored by
    damage (so a cold DoT build anoints e.g. Season of Ice, +DoT multiplier),
    emitted as an ``Allocates <Notable>`` line on the amulet that PoB applies.
    Returns (gear, fitness, chosen notable | None).
    """
    td = get_tree_data()
    dmg = "minion" if "minion" in enc.skill.tags else intent.damage_type
    slots = list(base_gear.slots)
    am_idx = next((i for i, s in enumerate(slots) if s.slot == ItemSlot.AMULET), None)
    base_fit = fitness(
        ev.evaluate(enc.code(visited, links, pob_gear=base_gear, jewels=jewels)), intent.budget
    )
    if am_idx is None:
        return base_gear, base_fit, None
    cands = sorted(
        (
            (_anoint_score(n.stats, dmg), n.name or "", n.id)
            for n in td.nodes_by_id.values()
            if n.is_notable
            and n.name
            and n.id < 65536
            and not n.ascendancy_name
            and not n.is_mastery
            and n.id not in visited
        ),
        key=lambda t: (-t[0], t[1]),
    )
    cands = [c for c in cands if c[0] > 0][:top_n]
    am = slots[am_idx]
    base_stats = ev.evaluate(enc.code(visited, links, pob_gear=base_gear, jewels=jewels))
    base_dps = base_stats.get("FullDPS") or base_stats.get("CombinedDPS") or 0.0
    # Evaluate every candidate; keep those that give a real DPS gain (>1.5%).
    # Among the passers, pick the highest-*scored* (most element-coherent) — so a
    # cold build anoints Season of Ice (cold), not a chaos notable that happens
    # to PoB-tie by a fraction. A damage anoint that does ~nothing (no good
    # unallocated notable of this build's element is left) -> no anoint (honest).
    passers: list[tuple[int, float, str, StageGearSlot]] = []
    for sc, name, _nid in cands:
        body = am.item_name.rstrip() + "\nAllocates " + name
        trial = list(slots)
        trial[am_idx] = StageGearSlot(
            slot=ItemSlot.AMULET, item_name=body, kind="rare_craft", notes=am.notes
        )
        try:
            stats = ev.evaluate(
                enc.code(
                    visited,
                    links,
                    pob_gear=StageGearSet(stage_key="opt", slots=tuple(trial)),
                    jewels=jewels,
                )
            )
        except Exception:
            continue
        dps = stats.get("FullDPS") or stats.get("CombinedDPS") or 0.0
        if dps > base_dps * 1.015:
            passers.append((sc, dps, name, trial[am_idx]))
    if passers:
        # DPS-primary, with a small element-coherence tiebreak: a tiny score
        # nudge (~2.6% max) breaks near-ties toward the element-matching notable
        # (Vortex -> Season of Ice over a chaos notable that PoB-ties) without
        # overriding a real DPS gap between two equally-sensible picks.
        _sc, dps, name, slot = max(passers, key=lambda p: p[1] * (1 + 0.002 * p[0]))
        slots[am_idx] = slot
        print(f"[opt] anoint: {name} | dps={dps:.0f}")
        return StageGearSet(stage_key="opt", slots=tuple(slots)), base_fit, name
    return base_gear, base_fit, None


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


# ---------------------------------------------------------------------------
# Cluster jewels (Step 76) — the biggest remaining tree lever. Two-pass: socket
# a Large cluster at a reachable Large socket, let PoB generate the sub-tree,
# read back the generated cluster node ids, then encode with them allocated.
# The serialization needs `clusterHashFormatVersion="2"` (handled by the
# encoder) so PoB doesn't crash on raw cluster ids. All fitness-gated.
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _large_socket_ids() -> frozenset[int]:
    """Regular-tree Large (size-2) cluster sockets, from the vendored tree."""
    path = (
        Path(__file__).resolve().parent.parent / "packages" / "fob" / "data" / "tree" / "3_28.json"
    )
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: set[int] = set()
    for nid, n in raw.get("nodes", {}).items():
        ej = n.get("expansionJewel") or {}
        if n.get("isJewelSocket") and ej.get("size") == 2 and nid.isdigit():
            out.add(int(nid))
    return frozenset(out)


# Build damage type -> ordered Large cluster theme tags to try (most specific
# first). Derived from PoB's theme list, not curated builds.
_CLUSTER_THEME_TAGS: dict[str, tuple[str, ...]] = {
    "cold": ("affliction_cold_damage", "affliction_elemental_damage", "affliction_spell_damage"),
    "fire": ("affliction_fire_damage", "affliction_elemental_damage", "affliction_spell_damage"),
    "lightning": (
        "affliction_lightning_damage",
        "affliction_elemental_damage",
        "affliction_spell_damage",
    ),
    "chaos": ("affliction_chaos_damage", "affliction_spell_damage"),
    "physical": ("affliction_physical_damage", "affliction_attack_damage"),
}


def _cluster_themes(intent: TheoryIntent, n: int = 2) -> list[cl.ClusterTheme]:
    """Build-relevant Large cluster themes (by damage type), spell/attack-aware."""
    is_attack = "attack" in gen._find_active(intent.primary_skill).tags
    tags = list(_CLUSTER_THEME_TAGS.get(intent.damage_type, ()))
    if is_attack:  # an elemental/phys attack scales attack damage, not spell damage
        tags = [t for t in tags if "spell" not in t]
        if "affliction_attack_damage" not in tags:
            tags.append("affliction_attack_damage")
    by_tag = {t.tag: t for t in cl.themes_for_size(cl.LARGE)}
    return [by_tag[t] for t in tags if t in by_tag][:n]


def _cluster_notable_score(stats: str, kws: tuple[str, ...]) -> int:
    """Score a cluster notable by DAMAGE only — the cluster's notable slots are
    precious, so they should carry damage, not the defensive notables the
    general (survival-weighted) scorer would pick. A DoT multiplier is weighted
    highest (multiplicative, unlike additive 'increased damage')."""
    low = stats.lower()
    s = sum(3 for k in kws if k in low)
    if "damage over time multiplier" in low:
        s += 5
    elif "more damage" in low:
        s += 4
    elif "increased damage" in low or "increased spell damage" in low:
        s += 1
    if "penetrat" in low or "exposure" in low:
        s += 3
    if "critical strike multiplier" in low:
        s += 2
    return s


def _cluster_notables(theme_dmg: str, n: int = 6) -> list[str]:
    """Top-n cluster notables scored by the build's damage keywords (only)."""
    kws = tuple(gen._DAMAGE_KEYWORDS.get(theme_dmg, ()))
    scored = [
        (_cluster_notable_score(stats, kws), name) for name, stats in cl.get_notables().items()
    ]
    scored = [s for s in scored if s[0] > 0]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [name for _s, name in scored[:n]]


def _cluster_body(theme: cl.ClusterTheme, notables: list[str]) -> str:
    n_pass = cl.size_passive_count(cl.LARGE)
    return "\n".join(
        [
            "Rarity: RARE",
            "Generated Cluster",
            cl.LARGE,
            "Item Level: 84",
            "Implicits: 0",
            f"Adds {n_pass} Passive Skills",
            theme.enchant,
            *[f"1 Added Passive Skill is {nm}" for nm in notables],
        ]
    )


def _reachable_socket(
    visited: set[int], td: TreeData, sockets: frozenset[int], max_path: int
) -> tuple[int | None, list[int]]:
    """Multi-source BFS from the allocated tree to the nearest socket in
    *sockets*. Returns (socket, path-including-socket) or (None, []) if the
    nearest is farther than *max_path* fillable hops."""
    seen = set(visited)
    prev: dict[int, int] = {}
    q: deque[int] = deque(visited)
    while q:
        x = q.popleft()
        if x in sockets and x not in visited:
            path: list[int] = []
            c = x
            while c in prev:
                path.append(c)
                c = prev[c]
            return (x, path) if len(path) <= max_path else (None, [])
        for nb in td.adjacency.get(x, frozenset()):
            if nb not in seen and gen._is_fillable(td.nodes_by_id.get(nb), nb):
                seen.add(nb)
                prev[nb] = x
                q.append(nb)
    return None, []


_CLUSTER_IDS_CHUNK = r"""
local ok,err=pcall(function()
  local f=assert(io.open(os.getenv("POB_EVAL_XML"),"r"))
  local x=f:read("*a"); f:close(); loadBuildFromXML(x,"eval")
end)
if not ok then return "ERR:"..tostring(err) end
local spec=build.spec
for id,node in pairs(spec.nodes) do
  if type(id)=="number" and id>=65536 and node.type=="Notable" then spec:AllocNode(node) end
end
local ids={}
for id in pairs(spec.allocNodes) do
  if type(id)=="number" and id>=65536 then ids[#ids+1]=tostring(id) end
end
return table.concat(ids,",")
"""


def _pass1_cluster_ids(ev: PobEvaluator, code: str) -> tuple[int, ...]:
    """Load a build (cluster socketed, no cluster ids), allocate the cluster
    notables in PoB, and return the generated cluster node ids (socket-
    dependent, so they must be read back per socket)."""
    ev._tmp_xml.write_text(decode_pob_code(code), encoding="utf-8")
    out = ev._run_chunk(_CLUSTER_IDS_CHUNK).strip()
    if out.startswith("ERR"):
        return ()
    return tuple(int(x) for x in out.split(",") if x.strip().isdigit())


def optimize_clusters(
    intent: TheoryIntent,
    ev: PobEvaluator,
    enc: _Encoder,
    visited: set[int],
    links: tuple[GemLink, ...],
    pob_gear: StageGearSet,
    jewels: tuple[tuple[int, str], ...] = (),
    *,
    max_path: int = 8,
) -> tuple[set[int], tuple[tuple[int, str, tuple[int, ...]], ...], float]:
    """Add a Large cluster jewel if it raises PoB-exact fitness.

    Two-pass: BFS-path to the nearest reachable Large socket, socket a build-
    relevant cluster (theme + top notables), read back the generated cluster
    ids (pass 1), then encode with them allocated (pass 2). Fitness-gated, so a
    cluster is kept only when it genuinely helps net of the points it costs.
    Returns (visited, clusters, fitness).
    """
    td = get_tree_data()
    theme_dmg = "minion" if "minion" in enc.skill.tags else intent.damage_type
    base_fit = fitness(
        ev.evaluate(enc.code(visited, links, pob_gear=pob_gear, jewels=jewels)), intent.budget
    )
    socket, path = _reachable_socket(visited, td, _large_socket_ids(), max_path)
    if socket is None:
        return visited, (), base_fit
    v2 = visited | set(path)

    best_clusters: tuple[tuple[int, str, tuple[int, ...]], ...] = ()
    best_fit = base_fit
    notables = _cluster_notables(theme_dmg)
    for theme in _cluster_themes(intent):
        if len(notables) < 2:
            break
        body = _cluster_body(theme, notables[:2])
        code1 = enc.code(
            v2, links, pob_gear=pob_gear, jewels=jewels, clusters=((socket, body, ()),)
        )
        ids = _pass1_cluster_ids(ev, code1)
        if not ids:
            continue
        clusters = ((socket, body, ids),)
        try:
            stats = ev.evaluate(
                enc.code(v2, links, pob_gear=pob_gear, jewels=jewels, clusters=clusters)
            )
        except Exception:
            continue
        fit = fitness(stats, intent.budget)
        if fit > best_fit * 1.001:
            best_clusters, best_fit = clusters, fit
    if best_clusters:
        print(
            f"[opt] cluster: {best_clusters[0][1].splitlines()[6]} "
            f"+ {notables[:2]} (+{len(path)} pts) | fit={best_fit:.0f}"
        )
        return v2, best_clusters, best_fit
    return visited, (), base_fit


# ---------------------------------------------------------------------------
# Honest point budget (Step 68) — trim the over-allocated tree to a realistic
# passive-point count so the served build is actually playable.
# ---------------------------------------------------------------------------


def _tree_points(visited: set[int], td: TreeData, dmg: str, defence: str) -> int:
    """Passive points the allocation spends: regular nodes (minus the free
    class start) + the masteries those nodes trigger. (Ascendancy is free via
    the lab; the jewel socket is a regular node already counted in ``visited``.)"""
    masteries = gen._select_masteries(visited, td, dmg, defence)
    return (len(visited) - 1) + len(masteries)


def trim_to_budget(
    intent: TheoryIntent,
    enc: _Encoder,
    visited: set[int],
    jewels: tuple[tuple[int, str], ...] = (),
    *,
    budget: int = _TREE_POINT_BUDGET,
    protect_extra: frozenset[int] = frozenset(),
) -> set[int]:
    """Drop the lowest-value removable leaves until the build fits a realistic
    passive-point budget.

    The timeless + aura + cluster passes can push the allocation past a
    level-100 point budget (a build needing 144 points is unplayable). This
    trims it back: connectivity-preserving (only nodes whose removal keeps the
    set connected to the class start are dropped — i.e. leaves), protecting the
    start, the jewel socket, any pathed reservation-efficiency notable
    (dropping one would break the auras' reservation), and ``protect_extra``
    (e.g. a cluster socket + its path — dropping one orphans the cluster).
    Lowest ``_score_node`` first, so the filler travel goes before any real
    notable. Pure graph work, no PoB eval.
    """
    td = get_tree_data()
    dmg = "minion" if "minion" in enc.skill.tags else intent.damage_type
    defence = intent.defence_archetype
    protect = (
        {enc.start} | (set(_RES_EFF_NODES) & visited) | {sock for sock, _ in jewels} | protect_extra
    )
    v = set(visited)

    def _node_score(nid: int) -> int:
        n = td.nodes_by_id.get(nid)
        return gen._score_node(n, dmg, defence) if n else 0

    while _tree_points(v, td, dmg, defence) > budget:
        cands = [n for n in v if n not in protect and _connected(v - {n}, enc.start, td.adjacency)]
        if not cands:
            break
        v.discard(min(cands, key=_node_score))
    return v


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
