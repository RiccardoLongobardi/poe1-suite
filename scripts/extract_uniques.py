"""Extract the PoE unique-item catalogue from PathOfBuilding (Step 58, F1).

The mirror-tier initiative's biggest lever: real unique items. We parse
PoB's ``Data/Uniques/*.lua`` text blocks into a slimmed, vendored JSON
(``packages/fob/data/uniques/uniques_3_28.json``) carrying each unique's
name, base type, slot, drop level and its *current-variant* mod lines.
The optimiser will later try these in a build and keep the PoB-fitness
best; this script just produces the data.

No hand-authored fallback (workflow §4.7): if we can't parse a sane number
of uniques the script aborts.

Run from a checkout with the PoB runtime present (`scripts/setup_pob.py`):

    uv run python scripts/extract_uniques.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_POB = Path(".pob_runtime/src/Data/Uniques")
_OUT = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "fob"
    / "data"
    / "uniques"
    / "uniques_3_28.json"
)

MIN_UNIQUES = 800

# Uniques file stem → our slot vocabulary (mirrors poe1_core ItemSlot values).
# Weapons keep their class so the optimiser can match the build's weapon type.
_SLOT: dict[str, str] = {
    "helmet": "helmet",
    "body": "body_armour",
    "gloves": "gloves",
    "boots": "boots",
    "belt": "belt",
    "amulet": "amulet",
    "ring": "ring",
    "jewel": "jewel",
    "flask": "flask",
    "quiver": "quiver",
    "shield": "weapon_offhand",
    "axe": "weapon",
    "sword": "weapon",
    "mace": "weapon",
    "bow": "weapon",
    "wand": "weapon",
    "dagger": "weapon",
    "claw": "weapon",
    "staff": "weapon",
}
# Files we skip (not build gear or too niche for the generator).
_SKIP = {"fishing", "graft", "tincture", "race"}

# Line prefixes that are item *metadata*, not modifiers.
_META = (
    "variant:",
    "league:",
    "source:",
    "requires level",
    "implicits:",
    "limited to:",
    "radius:",
    "has alt variant",
    "levelreq:",
    "selected variant",
    "upgrade:",
    "crafted:",
    "prefix:",
    "suffix:",
    "evasion:",
    "armour:",
    "energy shield:",
    "ward:",
    "id:",
    "item level:",
    "quality:",
    "sockets:",
    "talisman tier",
)

_VARIANT_TAG = re.compile(r"^\{variant:([\d,]+)\}(.*)$")
_OTHER_TAG = re.compile(r"^\{[^}]*\}")  # {crafted}, {fractured}, {tags:...}, …
_REQ_LEVEL = re.compile(r"requires level\s+(\d+)", re.IGNORECASE)
_BLOCK = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)


def _parse_block(block: str, slot: str) -> dict[str, object] | None:
    lines = [ln.rstrip() for ln in block.strip("\n").split("\n")]
    lines = [ln for ln in lines if ln.strip()]
    if len(lines) < 2:
        return None
    name, base = lines[0].strip(), lines[1].strip()
    if not name or not base:
        return None

    # How many variants does this unique declare? The "current" one is the
    # last declared (highest index, 1-based).
    n_variants = sum(1 for ln in lines if ln.lower().startswith("variant:"))
    current = n_variants  # 0 when the item has no variants

    drop_level = 0
    mods: list[str] = []
    for ln in lines[2:]:
        low = ln.lower()
        m = _REQ_LEVEL.search(ln)
        if m:
            drop_level = int(m.group(1))
        if any(low.startswith(p) for p in _META):
            continue
        text = ln
        vm = _VARIANT_TAG.match(text)
        if vm:
            idxs = {int(x) for x in vm.group(1).split(",") if x}
            if current and current not in idxs:
                continue  # belongs to a different variant
            text = vm.group(2)
        # Strip any leading non-variant tag ({crafted}, {fractured}, …).
        text = _OTHER_TAG.sub("", text).strip()
        if text:
            mods.append(text)
    if not mods:
        return None
    return {
        "name": name,
        "base_type": base,
        "slot": slot,
        "drop_level": drop_level,
        "mods": mods,
    }


def main() -> int:
    if not _POB.exists():
        sys.stderr.write(f"extract_uniques: {_POB} missing — run scripts/setup_pob.py first\n")
        return 1
    uniques: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in sorted(_POB.glob("*.lua")):
        stem = path.stem
        if stem in _SKIP:
            continue
        slot = _SLOT.get(stem)
        if slot is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for block in _BLOCK.findall(text):
            entry = _parse_block(block, slot)
            if entry is None:
                continue
            key = str(entry["name"])
            if key in seen:
                continue
            seen.add(key)
            uniques.append(entry)

    uniques.sort(key=lambda e: str(e["name"]))
    sys.stderr.write(f"extract_uniques: parsed {len(uniques)} uniques\n")
    if len(uniques) < MIN_UNIQUES:
        sys.stderr.write(
            f"extract_uniques: FAIL — only {len(uniques)} (min {MIN_UNIQUES}). Honest stop.\n"
        )
        return 1

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(
        json.dumps(
            {"version": "3.28", "source": "PathOfBuildingCommunity", "uniques": uniques},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sys.stderr.write(f"extract_uniques: wrote {_OUT}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
