"""Precompute PoB-exact-optimised builds for the Theorycrafter (Step 56).

Runs the local optimiser (`scripts/optimize_build.py`) over a curated
matrix of popular archetypes, captures the optimised supports + weapon +
tree and PoB's **real** calc output, and writes them to
``packages/fob/data/theory/precomputed_3_28.json``. The live app serves
that vendored file (`poe1_fob.theory.precomputed`) — Render never runs
PoB. Re-run locally per league or when the optimiser improves.

    uv run python scripts/precompute_builds.py
    uv run python scripts/precompute_builds.py --quick   # fewer tree iters

Needs the PoB runtime (`scripts/setup_pob.py`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_build import (  # type: ignore[import-not-found]  # sibling script
    _Encoder,
    fitness,
    optimize_links,
    optimize_tree,
    optimize_weapon,
)
from pob_eval import PobEvaluator  # type: ignore[import-not-found]

from poe1_fob.theory import TheoryIntent, generate_build, validate_build
from poe1_fob.theory.models import BuildSkeleton, StatEstimate
from poe1_fob.tree.tree_data import get_tree_data

# Absolute path anchored at the repo root — PobEvaluator chdir's into PoB's
# `src/` at construction (it uses relative `dofile`s), so a relative path
# here would resolve against `.pob_runtime/src/`, not the repo.
_OUT = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "fob"
    / "data"
    / "theory"
    / "precomputed_3_28.json"
)

# (class, ascendancy, skill, damage, defence) — popular, strong archetypes
# worth the offline optimisation. Budget/focus are fixed to endgame /
# allcontent (the values a "show me the best version" request implies).
_MATRIX: tuple[tuple[str, str, str, str, str], ...] = (
    ("Marauder", "Juggernaut", "Cyclone", "physical", "life"),
    ("Duelist", "Gladiator", "Lacerate", "physical", "life"),
    ("Witch", "Occultist", "Vortex", "cold", "es"),
    ("Templar", "Inquisitor", "Arc", "lightning", "life"),
    ("Ranger", "Deadeye", "Ice Shot", "cold", "life"),
)


def _optimised_skeleton(
    intent: TheoryIntent, ev: PobEvaluator, *, tree_iters: int
) -> BuildSkeleton:
    td = get_tree_data()
    enc = _Encoder(intent, td)
    base = generate_build(intent)
    visited0 = {enc.start} | {
        n.node_id for n in base.tree_nodes if n.type in ("keystone", "notable", "travel")
    }

    # 1) supports, 2) weapon base, 3) tree — each decided by PoB-exact fitness.
    best_links, _ = optimize_links(intent, ev, enc, visited0)
    best_gear, _ = optimize_weapon(intent, ev, enc, visited0, best_links)
    visited, _base_stats, best_stats = optimize_tree(
        intent, ev, links=best_links, gear=best_gear, max_iters=tree_iters
    )

    pob_code = enc.code(visited, best_links, best_gear)
    tree_nodes = enc._nodes(visited)
    # Map the optimiser's link/gear objects back to theory model types.
    links = best_links
    gear = best_gear

    stats = StatEstimate(
        life_estimate=int(best_stats.get("Life", 0)),
        es_estimate=int(best_stats.get("EnergyShield", 0)),
        dps_index=0,
        resistance_warning=None,
        estimated=False,
        full_dps=round(float(best_stats.get("FullDPS", 0.0)), 1),
        total_ehp=int(best_stats.get("TotalEHP", 0)),
    )
    skeleton = base.model_copy(
        update={
            "links": links,
            "tree_nodes": tree_nodes,
            "gear_slots": gear,
            "stats": stats,
            "pob_code": pob_code,
            "optimised": True,
        }
    )
    return skeleton.model_copy(update={"viability": validate_build(skeleton)})


def main(argv: list[str]) -> int:
    tree_iters = 8 if "--quick" in argv else 18
    ev = PobEvaluator()
    builds: list[dict[str, object]] = []
    for cls, asc, skill, dmg, defence in _MATRIX:
        intent = TheoryIntent(
            character_class=cls,
            ascendancy=asc,
            primary_skill=skill,
            damage_type=dmg,  # type: ignore[arg-type]
            defence_archetype=defence,  # type: ignore[arg-type]
            budget="endgame",
            focus="allcontent",
        )
        print(f"\n=== precomputing {cls}/{asc}/{skill} ===")
        sk = _optimised_skeleton(intent, ev, tree_iters=tree_iters)
        print(
            f"  -> FullDPS={sk.stats.full_dps:.0f} EHP={sk.stats.total_ehp} "
            f"Life={sk.stats.life_estimate} ES={sk.stats.es_estimate} "
            f"fit={fitness({'FullDPS': sk.stats.full_dps}, intent.budget):.0f}"
        )
        builds.append(sk.model_dump(mode="json"))

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(
        json.dumps({"version": "3.28", "builds": builds}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {len(builds)} optimised builds to {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
