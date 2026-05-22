"""Fetch + slim real PoE 1 explicit gear mods from repoe-fork.

The Theorycrafter recommends an ordered set of affixes per gear slot (life,
resistances, attack/cast/spell damage, crit, attributes, …). Before this
script those affix *values* were invented (`_AFFIX_VALUES`). This vendors
the **real** mod pool so the generator can emit real tiers with real value
ranges that can actually roll on the slot in question.

Sources (repoe-fork.github.io, ~33 MB + ~12 MB — we keep only the slice we
recommend, so the output is tiny):

* ``mods.json`` — every mod with domain/generation_type/required_level/
  stats(id+min+max)/spawn_weights.
* ``stat_translations.json`` — stat id → human text template.

We keep only **item-domain prefix/suffix mods with a single stat** whose
stat id is one of the ~18 we actually recommend (``TARGET_STATS``). Output
``packages/fob/data/mods/mods_3_28.json``:

    {
      "render": { "base_maximum_life": {"string": "{0} to maximum Life", "plus": true}, ... },
      "tiers":  { "base_maximum_life": [ {name, affix, ilvl, min, max, weights}, ... ], ... }
    }

Re-run after every PoE league:

    uv run python scripts/extract_mods.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

BASE = "https://raw.githubusercontent.com/repoe-fork/repoe-fork.github.io/master/data/"
OUT_PATH = Path("packages/fob/data/mods/mods_3_28.json")

# Real PoE stat ids behind every affix the generator recommends
# (resolved from stat_translations — see scripts probe 2026-05-22).
TARGET_STATS: frozenset[str] = frozenset(
    {
        "base_maximum_life",
        "base_maximum_energy_shield",
        "base_maximum_mana",
        "base_fire_damage_resistance_%",
        "base_cold_damage_resistance_%",
        "base_lightning_damage_resistance_%",
        "base_chaos_damage_resistance_%",
        "additional_all_attributes",
        "base_cast_speed_+%",
        "attack_speed_+%",
        "spell_damage_+%",
        "local_physical_damage_+%",
        "base_critical_strike_multiplier_+",
        "local_critical_strike_chance_+%",
        "accuracy_rating",
        "base_movement_velocity_+%",
        "local_additional_block_chance_%",
        "flask_life_recovery_rate_+%",
    }
)


def _get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "poe1-suite/0.1"})
    with urllib.request.urlopen(req, timeout=240) as resp:
        return json.loads(resp.read())


def _build_render(translations: list[dict[str, Any]]) -> dict[str, dict[str, object]]:
    """For each target stat id, capture its text template + whether the
    value is shown with a leading ``+``."""
    render: dict[str, dict[str, object]] = {}
    for entry in translations:
        ids = entry.get("ids", [])
        if not isinstance(ids, list) or len(ids) != 1:
            continue
        sid = ids[0]
        if sid not in TARGET_STATS or sid in render:
            continue
        english = entry.get("English", [])
        if not isinstance(english, list) or not english:
            continue
        first = english[0]
        string = first.get("string")
        fmt = first.get("format", [])
        if not isinstance(string, str):
            continue
        plus = bool(fmt and isinstance(fmt[0], str) and fmt[0].startswith("+"))
        render[sid] = {"string": string, "plus": plus}
    return render


def _build_tiers(mods: dict[str, Any]) -> dict[str, list[dict[str, object]]]:
    tiers: dict[str, list[dict[str, object]]] = {}
    for v in mods.values():
        if v.get("domain") != "item":
            continue
        gen = v.get("generation_type")
        if gen not in ("prefix", "suffix"):
            continue
        stats = v.get("stats", [])
        if not isinstance(stats, list) or len(stats) != 1:
            continue
        stat = stats[0]
        sid = stat.get("id")
        if sid not in TARGET_STATS:
            continue
        weights = [
            [w.get("tag"), w.get("weight", 0)]
            for w in v.get("spawn_weights", [])
            if isinstance(w, dict)
        ]
        tiers.setdefault(sid, []).append(
            {
                "name": v.get("name"),
                "affix": gen,
                "ilvl": int(v.get("required_level", 1)),
                "min": stat.get("min"),
                "max": stat.get("max"),
                "weights": weights,
            }
        )
    # Sort each stat's tiers by required level then max value, ascending.
    for lst in tiers.values():
        lst.sort(key=lambda t: (t["ilvl"], t["max"] if t["max"] is not None else 0))
    return tiers


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Fetching {BASE}mods.json + stat_translations.json ...")
    mods = _get(BASE + "mods.json")
    translations = _get(BASE + "stat_translations.json")
    if not isinstance(mods, dict) or not isinstance(translations, list):
        sys.stderr.write("extract_mods: unexpected upstream shape\n")
        return 1

    render = _build_render(translations)
    tiers = _build_tiers(mods)

    missing = TARGET_STATS - set(tiers)
    if missing:
        sys.stderr.write(f"extract_mods: WARN no tiers for {sorted(missing)}\n")
    no_render = set(tiers) - set(render)
    if no_render:
        sys.stderr.write(f"extract_mods: WARN no render template for {sorted(no_render)}\n")

    total_tiers = sum(len(v) for v in tiers.values())
    print(f"  stats with tiers: {len(tiers)} / {len(TARGET_STATS)}  ({total_tiers} tiers)")
    if total_tiers < 80:
        sys.stderr.write(f"extract_mods: FAIL — only {total_tiers} tiers parsed. Honest stop.\n")
        return 1

    payload = {"render": render, "tiers": tiers}
    OUT_PATH.write_text(
        json.dumps(payload, indent=None, separators=(",", ":"), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    sz = OUT_PATH.stat().st_size
    print(f"Saved: {OUT_PATH} ({sz:,} bytes, {sz // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
