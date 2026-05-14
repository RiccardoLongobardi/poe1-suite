"""Extract the official PoE 1 passive tree data from GGG's website.

GGG's https://www.pathofexile.com/passive-skill-tree page embeds the
complete tree definition inline as a JavaScript variable
``passiveSkillTreeData = {...}``. This is the authoritative source —
the same JSON PoB and other community tools consume after re-formatting.

Run once per league:

    python scripts/extract_tree_data.py

Writes ``packages/fob/data/tree/<version>.json`` and a manifest record.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

URL = "https://www.pathofexile.com/passive-skill-tree"
OUT_DIR = Path("packages/fob/data/tree")


def find_json_span(html: str, start_idx: int) -> tuple[int, int]:
    """Return the (start, end) char span of the first {…} object after start_idx."""

    depth = 0
    in_str = False
    escape = False
    for i, c in enumerate(html[start_idx:], start=start_idx):
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == "{":
            if depth == 0:
                obj_start = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return obj_start, i + 1
    raise ValueError("unbalanced JSON braces in input")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {URL} ...")
    req = urllib.request.Request(
        URL, headers={"User-Agent": "poe1-suite/0.1 (contact: ric.longobardi@outlook.it)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    print(f"  {len(html):,} bytes")

    m = re.search(r"passiveSkillTreeData\s*=\s*", html)
    if not m:
        print("ERROR: passiveSkillTreeData not found in HTML", file=sys.stderr)
        return 1
    obj_start, obj_end = find_json_span(html, m.end())
    raw = html[obj_start:obj_end]
    print(f"  JSON span: {obj_start}..{obj_end} ({obj_end - obj_start:,} bytes)")

    # Sanity parse
    data = json.loads(raw)
    classes = data.get("classes", [])
    nodes = data.get("nodes", {})
    print(f"  classes:        {len(classes)}")
    print(f"  nodes:          {len(nodes):,}")
    print(f"  top-level keys: {sorted(data.keys())[:15]}")

    # Try to find a version label embedded in the data
    version = data.get("version") or "current"
    if isinstance(data.get("tree"), str):
        # GGG embeds a tree-version string here (e.g. "Default" or
        # "Atlas"). Use it only when nothing better is available.
        version = data["tree"] or version
    out = OUT_DIR / f"{version}.json"
    # Pretty-print so diffs are reviewable
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved: {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
