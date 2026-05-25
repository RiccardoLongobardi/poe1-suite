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

import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Fitness
# ---------------------------------------------------------------------------


def fitness(stats: dict[str, float], budget: str) -> float:
    """Real DPS scaled by a viability penalty.

    Rewards damage, but a build that can't cap resistances or clears no
    EHP floor is heavily penalised — so the optimum is *viable* DPS, not a
    glass cannon.
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
    return dps * pen


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
