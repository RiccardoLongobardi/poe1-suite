"""PoB-exact QA sweep across archetypes (local tool).

Generates a build for a representative matrix of class / ascendancy /
skill / damage / defence, evaluates each with PoB's real calc, and reports
where the engine is weak — eval errors, near-zero DPS, non-viable
defences, missing skills, or wrong-weapon classification. Data-driven
prioritisation for the next fixes.

Needs the PoB runtime (`scripts/setup_pob.py`).

    uv run python scripts/qa_sweep.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pob_eval import PobEvalError, PobEvaluator  # type: ignore[import-not-found]

from poe1_fob.theory import TheoryIntent, generate_build
from poe1_fob.theory import generator as gen

# (class, ascendancy, skill, damage_type, defence) — representative of the
# main playstyles. Damage type follows our convention (fire/cold/lightning/
# chaos => "spell" path in the generator; physical => "attack" path).
_MATRIX: tuple[tuple[str, str, str, str, str], ...] = (
    # Physical melee attacks
    ("Marauder", "Juggernaut", "Cyclone", "physical", "life"),
    ("Marauder", "Berserker", "Earthquake", "physical", "life"),
    ("Marauder", "Chieftain", "Boneshatter", "physical", "life"),
    ("Duelist", "Slayer", "Cyclone", "physical", "life"),
    ("Duelist", "Gladiator", "Lacerate", "physical", "life"),
    ("Duelist", "Champion", "Sunder", "physical", "life"),
    # Elemental melee attacks (the suspected wrong-weapon cases)
    ("Ranger", "Raider", "Lightning Strike", "lightning", "life"),
    ("Duelist", "Champion", "Molten Strike", "fire", "life"),
    ("Shadow", "Raider", "Frost Blades", "cold", "life"),
    # Bow attacks
    ("Ranger", "Deadeye", "Tornado Shot", "physical", "life"),
    ("Ranger", "Deadeye", "Ice Shot", "cold", "life"),
    ("Ranger", "Pathfinder", "Caustic Arrow", "chaos", "life"),
    # Elemental spells
    ("Witch", "Elementalist", "Fireball", "fire", "es"),
    ("Witch", "Occultist", "Vortex", "cold", "es"),
    ("Templar", "Inquisitor", "Arc", "lightning", "life"),
    ("Templar", "Inquisitor", "Spark", "lightning", "life"),
    ("Witch", "Elementalist", "Frostbolt", "cold", "es"),
    # Chaos / DoT
    ("Witch", "Occultist", "Bane", "chaos", "es"),
    ("Shadow", "Trickster", "Essence Drain", "chaos", "es"),
    ("Shadow", "Trickster", "Soulrend", "chaos", "es"),
    # Minions
    ("Witch", "Necromancer", "Raise Spectre", "physical", "es"),
    ("Witch", "Necromancer", "Summon Skeletons", "physical", "es"),
    # Totem / brand / trap / mine
    ("Templar", "Hierophant", "Storm Brand", "lightning", "life"),
    ("Templar", "Hierophant", "Holy Flame Totem", "fire", "life"),
    ("Shadow", "Saboteur", "Lightning Trap", "lightning", "es"),
    ("Shadow", "Saboteur", "Pyroclast Mine", "fire", "es"),
    # Scion
    ("Scion", "Ascendant", "Spectral Throw", "physical", "life"),
)

_DPS_FLOOR = 1500.0
_POOL_FLOOR = {"life": 3500.0, "es": 3500.0, "ward": 2000.0, "hybrid_life_es": 3500.0}


def _verdict(skill: gen._Active, dmg: str, defence: str, stats: dict[str, float]) -> str:
    dps = stats.get("FullDPS", 0.0)
    pool = max(stats.get("Life", 0.0), stats.get("EnergyShield", 0.0))
    min_res = min(
        stats.get("FireResist", 0.0),
        stats.get("ColdResist", 0.0),
        stats.get("LightningResist", 0.0),
    )
    if "attack" in skill.tags and dmg in ("fire", "cold", "lightning"):
        return "WRONG_WEAPON"  # elemental attack treated as spell -> wand
    if dps < _DPS_FLOOR:
        return "LOW_DPS"
    if min_res < 70:
        return "LOW_RES"
    if pool < _POOL_FLOOR.get(defence, 3500.0):
        return "LOW_POOL"
    return "OK"


def main() -> int:
    ev = PobEvaluator()
    rows: list[tuple[str, str, str, float, float, float]] = []
    counts: dict[str, int] = {}
    print(f"{'archetype':42} {'weapon':18} {'FullDPS':>9} {'pool':>6} {'res':>4}  verdict")
    print("-" * 92)
    for cls, asc, name, dmg, defence in _MATRIX:
        skill = gen._find_active(name)
        label = f"{cls}/{asc}/{name}"
        if skill.name != name:
            counts["SKILL_MISSING"] = counts.get("SKILL_MISSING", 0) + 1
            print(f"{label:42} {'-':18} {'-':>9} {'-':>6} {'-':>4}  SKILL_MISSING")
            continue
        intent = TheoryIntent(
            character_class=cls,
            ascendancy=asc,
            primary_skill=name,
            damage_type=dmg,  # type: ignore[arg-type]
            defence_archetype=defence,  # type: ignore[arg-type]
            budget="endgame",
            focus="allcontent",
        )
        sk = generate_build(intent)
        weapon = next(
            (g.base_name for g in sk.gear_slots if g.slot in ("Weapon", "Wand", "Bow")), "-"
        )
        try:
            stats = ev.evaluate(sk.pob_code)
        except PobEvalError as exc:
            counts["EVAL_ERROR"] = counts.get("EVAL_ERROR", 0) + 1
            print(f"{label:42} {weapon[:18]:18} {'ERR':>9}  {str(exc)[:30]}")
            continue
        v = _verdict(skill, dmg, defence, stats)
        counts[v] = counts.get(v, 0) + 1
        dps = stats.get("FullDPS", 0.0)
        pool = max(stats.get("Life", 0.0), stats.get("EnergyShield", 0.0))
        min_res = min(
            stats.get("FireResist", 0.0),
            stats.get("ColdResist", 0.0),
            stats.get("LightningResist", 0.0),
        )
        rows.append((label, weapon, dmg, dps, pool, min_res))
        print(f"{label:42} {weapon[:18]:18} {dps:>9.0f} {pool:>6.0f} {min_res:>4.0f}  {v}")

    print("\n=== summary ===")
    for v, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {v:14} {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
