"""Compare a generated build against a top poe.ninja ladder build (local).

Fetches the highest-DPS ladder build for an ascendancy + skill from
poe.ninja, evaluates its PoB export with the real PoB calc, and compares
it side-by-side with our precomputed/generated build for the same
archetype — so we can see exactly where the gap is (DPS, EHP, gear mods,
gem levels, jewels, tree). Needs the PoB runtime + network.

    uv run python scripts/compare_ladder.py Occultist Vortex
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pob_eval import PobEvaluator  # type: ignore[import-not-found]

from poe1_builds.models import BuildFilter
from poe1_builds.service import BuildsService
from poe1_fob.pob import decode_export, parse_snapshot
from poe1_fob.theory import TheoryIntent, generate_build, lookup_precomputed
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

_INTENTS: dict[tuple[str, str], dict[str, str]] = {
    ("Occultist", "Vortex"): {
        "character_class": "Witch",
        "ascendancy": "Occultist",
        "primary_skill": "Vortex",
        "damage_type": "cold",
        "defence_archetype": "es",
    },
    ("Juggernaut", "Cyclone"): {
        "character_class": "Marauder",
        "ascendancy": "Juggernaut",
        "primary_skill": "Cyclone",
        "damage_type": "physical",
        "defence_archetype": "life",
    },
    ("Inquisitor", "Arc"): {
        "character_class": "Templar",
        "ascendancy": "Inquisitor",
        "primary_skill": "Arc",
        "damage_type": "lightning",
        "defence_archetype": "life",
    },
    ("Inquisitor", "Spark"): {
        "character_class": "Templar",
        "ascendancy": "Inquisitor",
        "primary_skill": "Spark",
        "damage_type": "lightning",
        "defence_archetype": "life",
    },
    ("Deadeye", "Ice Shot"): {
        "character_class": "Ranger",
        "ascendancy": "Deadeye",
        "primary_skill": "Ice Shot",
        "damage_type": "cold",
        "defence_archetype": "life",
    },
    ("Gladiator", "Lacerate"): {
        "character_class": "Duelist",
        "ascendancy": "Gladiator",
        "primary_skill": "Lacerate",
        "damage_type": "physical",
        "defence_archetype": "life",
    },
}


async def _fetch_ladder_pob(asc: str, skill: str) -> tuple[str, int, int, int] | None:
    """Return (pob_code, dps, life, es) for the top ladder build, or None."""
    settings = Settings()
    async with HttpClient(settings) as http:
        svc = BuildsService(http=http, league=settings.poe_league)
        snap = await svc.fetch_refs(BuildFilter(class_=asc, main_skill=skill, top_n_per_class=60))
        refs = sorted(snap.refs, key=lambda r: r.dps, reverse=True)
        print(f"[ladder] {len(refs)} {asc}/{skill} builds on {snap.league}")
        for ref in refs[:6]:
            fb = await svc.get_detail(ref)
            if fb.path_of_building_export:
                return (fb.path_of_building_export, ref.dps, ref.life, ref.energy_shield)
    return None


def _dps(stats: dict[str, float]) -> float:
    """DoT-aware DPS: CombinedDPS captures damage-over-time, FullDPS doesn't."""
    return stats.get("CombinedDPS", 0.0) or stats.get("FullDPS", 0.0) or stats.get("TotalDPS", 0.0)


def _summarise(label: str, code: str, ev: PobEvaluator) -> dict[str, float]:
    stats: dict[str, float] = ev.evaluate(code)
    snap = parse_snapshot(decode_export(code), export_code=code)
    n_items = len(snap.items_by_slot)
    n_jewels = len(snap.jewels)
    n_nodes = len(snap.tree.node_ids) if snap.tree else 0
    uniques = sorted(
        {i.name for i in snap.items_by_slot.values() if i.rarity.upper() == "UNIQUE" and i.name}
    )
    main_idx = snap.main_skill_group_index
    main_gems: list[str] = []
    if snap.skills and 1 <= main_idx <= len(snap.skills):
        grp = snap.skills[main_idx - 1]
        main_gems = [f"{g.name} {g.level}/{g.quality}" for g in grp.gems]
    print(
        f"\n[{label}]\n"
        f"  DPS (DoT-aware) {_dps(stats):>12,.0f}   "
        f"(CombinedDPS={stats.get('CombinedDPS', 0):,.0f} FullDPS={stats.get('FullDPS', 0):,.0f})\n"
        f"  Life            {stats.get('Life', 0):>12,.0f}\n"
        f"  ES              {stats.get('EnergyShield', 0):>12,.0f}\n"
        f"  TotalEHP        {stats.get('TotalEHP', 0):>12,.0f}\n"
        f"  res F/C/L/Chaos {stats.get('FireResist', 0):.0f}/"
        f"{stats.get('ColdResist', 0):.0f}/{stats.get('LightningResist', 0):.0f}/"
        f"{stats.get('ChaosResist', 0):.0f}\n"
        f"  items={n_items} jewels={n_jewels} tree_nodes={n_nodes}\n"
        f"  main link: {main_gems}\n"
        f"  uniques: {uniques}"
    )
    return stats


def main(argv: list[str]) -> int:
    asc = argv[0] if argv else "Occultist"
    skill = argv[1] if len(argv) > 1 else "Vortex"
    key = (asc, skill)
    if key not in _INTENTS:
        print(f"no intent mapping for {key}; known: {list(_INTENTS)}")
        return 1
    fields = _INTENTS[key]

    ladder = asyncio.run(_fetch_ladder_pob(asc, skill))
    if ladder is None:
        print("no ladder build with a PoB export found")
        return 1
    ladder_code, ladder_dps, ladder_life, ladder_es = ladder

    intent = TheoryIntent(
        budget="endgame",
        focus="allcontent",
        **fields,  # type: ignore[arg-type]
    )
    mine = lookup_precomputed(intent) or generate_build(intent)

    ev = PobEvaluator()
    print(
        f"\n=== {asc} / {skill} — ladder reports DPS={ladder_dps:,} "
        f"Life={ladder_life:,} ES={ladder_es:,} ==="
    )
    ladder_stats = _summarise("LADDER (poe.ninja top)", ladder_code, ev)
    mine_stats = _summarise(
        f"MINE ({'precomputed' if mine.optimised else 'generated'})", mine.pob_code, ev
    )

    ld = _dps(ladder_stats) or 1.0
    md = _dps(mine_stats)
    le = ladder_stats.get("TotalEHP", 0.0) or 1.0
    me = mine_stats.get("TotalEHP", 0.0)
    print(
        f"\n=== GAP ===\n"
        f"  DPS: mine is {md / ld * 100:.0f}% of the ladder build ({md:,.0f} vs {ld:,.0f})\n"
        f"  EHP: mine is {me / le * 100:.0f}% of the ladder build ({me:,.0f} vs {le:,.0f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
