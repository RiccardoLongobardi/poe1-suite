"""Fetch + slim GGG's Trade stat database.

Source: ``https://www.pathofexile.com/api/trade/data/stats`` (~1.9 MB) —
every searchable stat on the official Trade site, grouped by domain
(explicit / implicit / enchant / crafted / pseudo / …).

Builds a ``{normalized_text: {domain: stat_id}}`` map so the
Trade-search dialog can resolve a PoB mod line to the GGG ``stat_id``
**of the right domain** — a corrupted implicit must search the
``implicit`` stat, not the same-text ``explicit`` one. The
normalisation is :func:`poe1_fob.trade_stats.normalize_mod_text` — kept
in the runtime module so the build-time and lookup-time keys match.

``pseudo`` / ``monster`` aggregate stats are skipped — they're not real
item mods.

Writes ``packages/fob/data/trade/stats.json`` (~0.5 MB minified).

Re-run after every PoE league:

    uv run python scripts/extract_trade_stats.py
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

from poe1_fob.trade_stats import normalize_mod_text

URL = "https://www.pathofexile.com/api/trade/data/stats"
OUT_PATH = Path("packages/fob/data/trade/stats.json")
USER_AGENT = "poe1-suite/1.0 (+https://github.com/RiccardoLongobardi/poe1-suite)"

# Domain priority — when two groups share a normalised text, the first
# one listed keeps the key. `pseudo` (aggregate) and `monster` are not
# item mods and are dropped entirely.
PRIORITY: tuple[str, ...] = (
    "explicit",
    "implicit",
    "fractured",
    "enchant",
    "rune",
    "crafted",
    "veiled",
    "crucible",
    "sanctum",
    "scourge",
    "delve",
    "ultimatum",
    "skill",
    "area",
)
SKIP = frozenset({"pseudo", "monster"})


def main() -> int:
    print(f"Fetching {URL} …")
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    groups = {g["id"]: g for g in payload.get("result", [])}
    # {normalized_text: {domain: stat_id}} — one id kept per domain.
    out: dict[str, dict[str, str]] = {}
    ordered = [*PRIORITY, *(gid for gid in groups if gid not in PRIORITY)]
    for gid in ordered:
        group = groups.get(gid)
        if group is None or gid in SKIP:
            continue
        for entry in group.get("entries", []):
            text = entry.get("text")
            stat_id = entry.get("id")
            if not text or not stat_id:
                continue
            key = normalize_mod_text(text)
            if not key:
                continue
            out.setdefault(key, {}).setdefault(gid, stat_id)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Wrote {len(out)} normalised stats to {OUT_PATH} ({size_kb:.0f} KB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
