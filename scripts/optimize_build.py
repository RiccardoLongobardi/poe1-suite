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

from poe1_fob.pob.encode import encode_pob_code
from poe1_fob.theory import TheoryIntent, generate_build
from poe1_fob.theory import generator as gen
from poe1_fob.theory.models import GemLink, TreeNodeRef
from poe1_fob.tree.tree_data import TreeData, get_tree_data

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
        gear = gen._select_gear(intent)
        self.skill = gen._find_active(intent.primary_skill)
        primary = GemLink(
            skill=self.skill.name,
            supports=gen._select_supports(self.skill, dmg=intent.damage_type),
            slot="Body Armour",
            label="Primary 6L",
        )
        self.base_links = gen._build_gem_layout(intent, primary, self.skill)
        self._pob_gear = gen._to_pob_gear(gear)
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

    def code(self, visited: set[int], links: tuple[GemLink, ...] | None = None) -> str:
        tree = gen._to_pob_tree(self.intent, self._nodes(visited))
        return encode_pob_code(
            character_class=self.intent.character_class,
            ascendancy=self.intent.ascendancy,
            tree=tree,
            gear=self._pob_gear,
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


def optimize_tree(
    intent: TheoryIntent,
    ev: PobEvaluator,
    *,
    links: tuple[GemLink, ...] | None = None,
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
    base_stats = ev.evaluate(enc.code(visited, links))
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
                stats = ev.evaluate(enc.code(cand, links))
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
