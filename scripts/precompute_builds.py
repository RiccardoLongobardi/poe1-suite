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
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
from optimize_build import (  # type: ignore[import-not-found]  # sibling script
    _TREE_POINT_BUDGET,
    _Encoder,
    _forbids_chest,
    _relocate_no_chest,
    fitness,
    optimize_anoint,
    optimize_auras,
    optimize_awakened,
    optimize_clusters,
    optimize_flasks,
    optimize_links,
    optimize_timeless,
    optimize_tree,
    optimize_uniques,
    optimize_weapon,
    trim_to_budget,
)
from pob_eval import PobEvaluator  # type: ignore[import-not-found]

from poe1_core.models.enums import ItemSlot
from poe1_fob.gear.uniques import unique_by_name
from poe1_fob.theory import TheoryIntent, generate_build, validate_build
from poe1_fob.theory import generator as gen
from poe1_fob.theory.models import BuildSkeleton, GearSlot, StatEstimate, TreeNodeRef
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
    # Step 71 — matrix expansion: more popular archetypes + a new class
    # (Shadow). Diverse playstyles: melee slam / projectile spell / chaos-
    # poison spell. (Physical Tornado Shot was trialled but the generator
    # optimises a physical *bow* poorly — ~15k DPS — so it's omitted until the
    # physical-bow handling improves; elemental bows like Ice Shot are fine.)
    ("Marauder", "Juggernaut", "Boneshatter", "physical", "life"),
    ("Templar", "Inquisitor", "Spark", "lightning", "life"),
    ("Shadow", "Assassin", "Blade Vortex", "chaos", "life"),
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

    # 1) supports, 2) weapon base, 3) uniques per slot, 4) tree, 5) timeless
    # jewel, 6) auras — each decided by PoB-exact fitness. Auras run LAST, on
    # the final tree + uniques + jewels, so the reservation efficiency they
    # see (and the reservation notables they may path in) reflect the real
    # mana pool — not a stale generic-gear estimate.
    best_links, _ = optimize_links(intent, ev, enc, visited0)
    # Upgrade the main 6L's damage supports to their Awakened versions (Step 73:
    # best-version gem quality, ~x1.5 on a caster 6L). Done early so the weapon
    # / uniques / tree passes optimise around the stronger gems.
    best_links = optimize_awakened(intent, ev, enc, visited0, best_links, enc._pob_gear)
    best_gear, _ = optimize_weapon(intent, ev, enc, visited0, best_links)
    base_pob = gen._to_pob_gear(best_gear)
    best_pob, _, chosen = optimize_uniques(intent, ev, enc, visited0, best_links, base_pob)
    # Unique flasks (Bottled Faith / Wise Oak / Taste of Hate / …) — a clean
    # DPS+EHP lever with no passive-point cost. Done after uniques so the later
    # tree / timeless / aura / cluster passes optimise on the flask-boosted gear.
    best_pob, _, flask_names = optimize_flasks(intent, ev, enc, visited0, best_links, best_pob)
    visited, _base_stats, best_stats = optimize_tree(
        intent, ev, links=best_links, pob_gear=best_pob, max_iters=tree_iters
    )
    # 5) timeless jewel — LUT god-seed search over the finalised tree.
    visited, jewels, _ = optimize_timeless(intent, ev, enc, visited, best_links, best_pob)
    # 6) auras — multi-aura group + Enlighten (+ pathed reservation nodes),
    # reservation-honest.
    best_links, visited, _ = optimize_auras(intent, ev, enc, visited, best_links, best_pob, jewels)
    # Amulet anoint (Step 79) — a free damage notable (no passive-point cost).
    # Run after auras so the unallocated-notable pool is final.
    best_pob, _, anoint_name = optimize_anoint(
        intent, ev, enc, visited, best_links, best_pob, jewels
    )
    # Step 70 relocation (links-only — a chest-forbidding helmet voids the body,
    # so the 6L is relocated to the helmet). Done before the trim/cluster evals.
    helmet_u = chosen.get(ItemSlot.HELMET)
    if helmet_u is not None and _forbids_chest(helmet_u):
        best_links = _relocate_no_chest(best_links)

    # 7) cluster jewel (Step 76) — the biggest tree lever. Two-pass: socket a
    # Large cluster at a reachable Large socket, read back the generated
    # sub-tree ids, encode with them allocated. A cluster costs ~14 points
    # (socket + path + ~8 sub-tree nodes), so it's only kept if the FINAL build
    # (trimmed to the 123-point budget) beats the same build WITHOUT the cluster
    # — otherwise adding it on top of an already-full tree is a net loss.
    visited_pre = set(visited)
    visited_c, clusters, _ = optimize_clusters(
        intent, ev, enc, visited, best_links, best_pob, jewels
    )
    cluster_pts = sum(len(ids) for _s, _b, ids in clusters)

    def _final(
        v: set[int], cl_param: tuple[tuple[int, str, tuple[int, ...]], ...]
    ) -> dict[str, float]:
        stats: dict[str, float] = ev.evaluate(
            enc.code(v, best_links, pob_gear=best_pob, jewels=jewels, clusters=cl_param)
        )
        return stats

    if clusters:
        cluster_path = frozenset(visited_c - visited_pre)  # path + socket — protect in trim
        v_with = trim_to_budget(
            intent,
            enc,
            visited_c,
            jewels,
            budget=_TREE_POINT_BUDGET - cluster_pts,
            protect_extra=cluster_path,
        )
        v_no = trim_to_budget(intent, enc, visited_pre, jewels)
        st_with, st_no = _final(v_with, clusters), _final(v_no, ())
        if fitness(st_no, intent.budget) >= fitness(st_with, intent.budget):
            clusters, visited, best_stats = (), v_no, st_no  # cluster not net-positive
            print(f"[opt] cluster dropped (net loss after trim): {len(v_no) - 1} nodes")
        else:
            visited, best_stats = v_with, st_with
            print(f"[opt] cluster kept: {len(v_with) - 1} regular + {cluster_pts} cluster")
    else:
        visited = trim_to_budget(intent, enc, visited_pre, jewels)
        best_stats = _final(visited, ())
        print(f"[opt] trim -> {len(visited) - 1} regular nodes (budget {_TREE_POINT_BUDGET})")

    pob_code = enc.code(visited, best_links, pob_gear=best_pob, jewels=jewels, clusters=clusters)
    # Cluster sub-tree nodes count toward the point budget — surface them in the
    # served tree so the budget invariant test sees the real total.
    cluster_refs = tuple(
        TreeNodeRef(node_id=nid, name="Cluster passive", type="travel")
        for _s, _b, ids in clusters
        for nid in ids
    )
    tree_nodes = (*enc._nodes(visited), *cluster_refs)
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
    # Reflect the chosen unique flasks into the display (the importable pob_code
    # already carries them via best_pob). Flask GearSlots are labelled
    # "Flask 1".."Flask 5" in order; flask_names maps the ordinal -> unique name.
    if flask_names:
        overlaid: list[GearSlot] = []
        flask_ord = 0
        for g in gear:
            if g.slot.startswith("Flask"):
                nm = flask_names.get(flask_ord)
                flask_ord += 1
                u = unique_by_name(nm) if nm else None
                if u is not None:
                    g = GearSlot(
                        slot=g.slot,
                        base_name=u.name,
                        stat_priorities=tuple(u.mods[:5]),
                        budget_tier=g.budget_tier,
                    )
            overlaid.append(g)
        gear = tuple(overlaid)
    # Reflect the amulet anoint into the display (Step 79).
    if anoint_name:
        gear = tuple(
            GearSlot(
                slot=g.slot,
                base_name=g.base_name,
                stat_priorities=(f"Anointed: {anoint_name}", *g.stat_priorities),
                budget_tier=g.budget_tier,
            )
            if g.slot == "Amulet"
            else g
            for g in gear
        )
    # Step 70: if the chosen helmet forbids a body armour (The Bringer of Rain),
    # drop the Body Armour from the displayed gear — it's unequippable, and the
    # primary 6L was relocated into the helmet.
    helmet_u = chosen.get(ItemSlot.HELMET)
    if helmet_u is not None and _forbids_chest(helmet_u):
        gear = tuple(g for g in gear if g.slot != "Body Armour")
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
    # Show each cluster jewel as a display slot (enchant + its notables).
    for _s, body, _ids in clusters:
        lines = body.split("\n")
        gear = (
            *gear,
            GearSlot(
                slot="Cluster Jewel",
                base_name="Large Cluster Jewel",
                stat_priorities=tuple(
                    ln
                    for ln in lines
                    if ln.startswith("Added Small") or ln.startswith("1 Added Passive")
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


def _proxy(full_dps: float, total_ehp: float, budget: str) -> float:
    """Run-comparable fitness proxy: DPS scaled by the same saturating EHP
    factor the optimiser uses (resistances/reservation are equal-by-construction
    for two viable served builds, so they cancel in the comparison)."""
    return float(fitness({"FullDPS": full_dps, "TotalEHP": total_ehp}, budget))


def main(argv: list[str]) -> int:
    tree_iters = 8 if "--quick" in argv else 18
    ev = PobEvaluator()
    # Ratchet: the greedy pipeline is non-deterministic across runs (string-hash
    # iteration order tips equal-fitness tie-breaks → a build can land on a worse
    # local optimum by chance, independent of any code change). So never regress
    # a served build: load the previously committed builds and keep, per
    # archetype, whichever of {new run, committed} has the higher fitness proxy.
    prev: dict[tuple[str, ...], dict[str, object]] = {}
    if _OUT.exists():
        for b in json.loads(_OUT.read_text(encoding="utf-8")).get("builds", []):
            it = b["intent"]
            key = (
                it["character_class"],
                it["ascendancy"],
                it["primary_skill"],
                it["damage_type"],
                it["defence_archetype"],
            )
            prev[key] = b
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
        new_dump = sk.model_dump(mode="json")
        new_fit = _proxy(sk.stats.full_dps, sk.stats.total_ehp, intent.budget)
        old = prev.get((cls, asc, skill, dmg, defence))
        if old is not None:
            os = cast(dict[str, float], old["stats"])
            old_fit = _proxy(float(os["full_dps"]), float(os["total_ehp"]), intent.budget)
            if old_fit > new_fit:
                print(
                    f"  -> kept COMMITTED (fit {old_fit:.0f} > new {new_fit:.0f}): "
                    f"FullDPS={os['full_dps']:.0f} EHP={os['total_ehp']}"
                )
                builds.append(old)
                continue
        print(
            f"  -> FullDPS={sk.stats.full_dps:.0f} EHP={sk.stats.total_ehp} "
            f"Life={sk.stats.life_estimate} ES={sk.stats.es_estimate} fit={new_fit:.0f}"
        )
        builds.append(new_dump)

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(
        json.dumps({"version": "3.28", "builds": builds}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {len(builds)} optimised builds to {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
