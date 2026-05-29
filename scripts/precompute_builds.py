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
    optimize_auras,
    optimize_links,
    optimize_timeless,
    optimize_tree,
    optimize_uniques,
    optimize_weapon,
)
from pob_eval import PobEvaluator  # type: ignore[import-not-found]

from poe1_core.models.enums import ItemSlot
from poe1_fob.theory import TheoryIntent, generate_build, validate_build
from poe1_fob.theory import generator as gen
from poe1_fob.theory.models import BuildSkeleton, GearSlot, StatEstimate
from poe1_fob.tree.tree_data import get_tree_data

# Theory gear-slot label → ItemSlot, to reflect chosen uniques back into the
# skeleton's display gear_slots.
_LABEL_TO_SLOT: dict[str, ItemSlot] = {
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

    # 1) supports, 2) auras, 3) weapon base, 4) uniques per slot, 5) tree,
    # 6) timeless jewel — each decided by PoB-exact fitness. Auras come early
    # so every later pass evaluates with the aura buffs + reservation applied.
    best_links, _ = optimize_links(intent, ev, enc, visited0)
    best_links, _ = optimize_auras(intent, ev, enc, visited0, best_links, enc._pob_gear)
    best_gear, _ = optimize_weapon(intent, ev, enc, visited0, best_links)
    base_pob = gen._to_pob_gear(best_gear)
    best_pob, _, chosen = optimize_uniques(intent, ev, enc, visited0, best_links, base_pob)
    visited, _base_stats, best_stats = optimize_tree(
        intent, ev, links=best_links, pob_gear=best_pob, max_iters=tree_iters
    )
    # 5) timeless jewel — LUT god-seed search over the finalised tree.
    visited, jewels, _ = optimize_timeless(intent, ev, enc, visited, best_links, best_pob)
    if jewels:
        best_stats = ev.evaluate(enc.code(visited, best_links, pob_gear=best_pob, jewels=jewels))

    pob_code = enc.code(visited, best_links, pob_gear=best_pob, jewels=jewels)
    tree_nodes = enc._nodes(visited)
    links = best_links

    # Display gear: the rare/weapon theory slots, with chosen uniques overlaid
    # (name + their mod lines as priorities) so the UI shows the real items.
    def _overlay(g: GearSlot) -> GearSlot:
        slot_enum = _LABEL_TO_SLOT.get(g.slot)
        u = chosen.get(slot_enum) if slot_enum is not None else None
        if u is None:
            return g
        return GearSlot(
            slot=g.slot,
            base_name=u.name,
            stat_priorities=tuple(u.mods[:6]),
            budget_tier=g.budget_tier,
        )

    gear = tuple(_overlay(g) for g in best_gear)
    # Show the timeless jewel as a display slot (name + its seed/conqueror line).
    if jewels:
        body_lines = jewels[0][1].split("\n")
        gear = (
            *gear,
            GearSlot(
                slot="Timeless Jewel",
                base_name=body_lines[1] if len(body_lines) > 1 else "Lethal Pride",
                stat_priorities=tuple(
                    ln
                    for ln in body_lines
                    if ln.startswith("Commanded") or ln.startswith("Passives")
                ),
                budget_tier=intent.budget,
            ),
        )

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
