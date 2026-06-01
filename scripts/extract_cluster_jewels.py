"""Vendor cluster-jewel data from the PoB runtime (Step 76).

Dumps the cluster-jewel themes (per size, with the exact "Added Small Passive
Skills grant: …" enchant) + the cluster notable pool (name -> stat text) from
PoB's own loaded data (`data.clusterJewels` + `build.spec.tree.clusterNodeMap`)
into ``packages/fob/data/cluster/cluster_3_28.json``. The optimiser uses this
to build Large/Medium cluster jewels from scratch (Fase 2 of the real-builds
initiative).

Local/offline tool — needs the PoB runtime (`scripts/setup_pob.py`), like
`precompute_builds.py`. Re-run per league.

    uv run python scripts/extract_cluster_jewels.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pob_eval import PobEvaluator  # type: ignore[import-not-found]

_OUT = (
    Path(__file__).resolve().parent.parent
    / "packages"
    / "fob"
    / "data"
    / "cluster"
    / "cluster_3_28.json"
)

# Dumps themes (T|size|tag|name|enchant), sizes (S|size|min|max) and cluster
# notables (N|name|stat;stat;…). A "|" / newline split keeps it simple; the
# stat texts use no "|".
_DUMP = r"""
local cj = data.clusterJewels
local out = {}
for size, info in pairs(cj.jewels) do
  out[#out+1] = "S|" .. size .. "|" .. tostring(info.minNodes) .. "|" .. tostring(info.maxNodes)
  for tag, sk in pairs(info.skills) do
    local ench = sk.enchant and sk.enchant[1] or ""
    out[#out+1] = "T|" .. size .. "|" .. tag .. "|" .. (sk.name or "") .. "|" .. ench
  end
end
local tree = build.spec.tree
if tree and tree.clusterNodeMap then
  for name, node in pairs(tree.clusterNodeMap) do
    if node.sd then
      out[#out+1] = "N|" .. name .. "|" .. table.concat(node.sd, ";")
    end
  end
end
return table.concat(out, "\n")
"""


def main() -> int:
    ev = PobEvaluator()
    raw = ev._run_chunk(_DUMP)
    sizes: dict[str, dict[str, int]] = {}
    themes: dict[str, list[dict[str, str]]] = {}
    notables: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("S|"):
            _, size, mn, mx = line.split("|", 3)
            sizes[size] = {"min": int(mn), "max": int(mx)}
        elif line.startswith("T|"):
            _, size, tag, name, enchant = line.split("|", 4)
            themes.setdefault(size, []).append({"tag": tag, "name": name, "enchant": enchant})
        elif line.startswith("N|"):
            _, name, stats = line.split("|", 2)
            notables[name] = stats.replace(";", "\n")

    for lst in themes.values():
        lst.sort(key=lambda t: t["name"])

    n_themes = sum(len(v) for v in themes.values())
    print(f"  sizes: {len(sizes)}  themes: {n_themes}  notables: {len(notables)}")
    if len(sizes) < 3 or n_themes < 50 or len(notables) < 200:
        sys.stderr.write("extract_cluster_jewels: FAIL — too little data. Honest stop.\n")
        return 1

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": "3.28", "sizes": sizes, "themes": themes, "notables": notables}
    _OUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sz = _OUT.stat().st_size
    print(f"Saved: {_OUT} ({sz:,} bytes, {sz // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
