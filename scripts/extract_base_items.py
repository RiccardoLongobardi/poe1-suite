"""Fetch + slim PoE 1 item-base definitions from repoe-fork.

Source: ``https://raw.githubusercontent.com/repoe-fork/repoe-fork.github.io/
master/data/base_items.json`` (~7.3 MB, 5052 entries — most are currencies,
maps, fragments, and gems we don't need).

Filters to **released gear bases only** (the ~1030 entries that map to a
PoB slot — body armours, helmets, gloves, boots, belts, amulets, rings,
weapons, shields, flasks, jewels) and strips every field that doesn't
contribute to Step 17's tier classification + substitution lookup.

Writes ``packages/fob/data/items/base_items.json`` (~360 KB minified).

Re-run after every PoE league:

    uv run python scripts/extract_base_items.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://raw.githubusercontent.com/repoe-fork/repoe-fork.github.io/master/data/base_items.json"
)
OUT_PATH = Path("packages/fob/data/items/base_items.json")

# ``item_class`` values that map to a real PoB gear slot. Everything else
# (StackableCurrency, Map, DivinationCard, Active/Support Skill Gem, …)
# is irrelevant for the gear progression and gets dropped.
GEAR_CLASSES: frozenset[str] = frozenset(
    {
        "Body Armour",
        "Shield",
        "Helmet",
        "Boots",
        "Gloves",
        "Amulet",
        "Ring",
        "Belt",
        "Quiver",
        # Weapons
        "One Hand Sword",
        "Two Hand Sword",
        "Thrusting One Hand Sword",
        "One Hand Axe",
        "Two Hand Axe",
        "One Hand Mace",
        "Two Hand Mace",
        "Sceptre",
        "Staff",
        "Warstaff",
        "Bow",
        "Wand",
        "Claw",
        "Dagger",
        "Rune Dagger",
        # Flasks
        "LifeFlask",
        "ManaFlask",
        "HybridFlask",
        "UtilityFlask",
        # Jewels (regular + alternates)
        "Jewel",
        "AbyssJewel",
        "HighlanderJewel",
        "KaruiJewel",
        "EternalJewel",
        "MarakethJewel",
        "TemplarJewel",
        "VaalJewel",
    }
)


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {URL} ...")
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "poe1-suite/0.1 (contact: ric.longobardi@outlook.it)",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw_text = resp.read().decode("utf-8")
    print(f"  {len(raw_text):,} bytes")

    data = json.loads(raw_text)
    if not isinstance(data, dict):
        print("ERROR: expected top-level dict in upstream JSON", file=sys.stderr)
        return 1

    total = len(data)
    gear = {
        path: v
        for path, v in data.items()
        if isinstance(v, dict) and v.get("item_class") in GEAR_CLASSES
    }
    released = {path: v for path, v in gear.items() if v.get("release_state") == "released"}
    print(f"  total entries:     {total:,}")
    print(f"  gear-only:         {len(gear):,}")
    print(f"  released gear:     {len(released):,}")

    # Slim schema: keep only fields the tier classifier + substitution
    # picker need. Note: ``requirements`` is not present on every entry
    # (some bases have it on a parent ``inherits_from``); we keep the
    # raw value when present and let the consumer side coalesce.
    slim: dict[str, dict[str, object]] = {}
    for path, v in released.items():
        slim[path] = {
            "name": v.get("name"),
            "item_class": v.get("item_class"),
            "drop_level": v.get("drop_level"),
            "tags": v.get("tags", []),
            "implicits": v.get("implicits", []),
            "inherits_from": v.get("inherits_from"),
            "requirements": v.get("requirements"),
        }

    # Minified output (separators removes the default ", " / ": " spaces).
    # Sorted keys make diffs reviewable when refreshing.
    out_text = json.dumps(
        slim, indent=None, separators=(",", ":"), ensure_ascii=False, sort_keys=True
    )
    OUT_PATH.write_text(out_text, encoding="utf-8")
    sz = OUT_PATH.stat().st_size
    print(f"Saved: {OUT_PATH} ({sz:,} bytes, {sz // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
