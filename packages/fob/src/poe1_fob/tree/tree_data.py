"""PoE 1 passive tree data loader.

Vendored snapshot of GGG's official ``passiveSkillTreeData`` JSON,
extracted from https://www.pathofexile.com/passive-skill-tree by
:mod:`scripts.extract_tree_data`. Re-run that script after a league
change to refresh.

Loaded lazily on first call to :func:`get_tree_data`. The JSON is
~5 MB on disk; loading takes ~50-100 ms once per process.

Public surface:

* :class:`TreeNode` — pruned per-node record (id, name, type flags,
  adjacency, ascendancy/group membership).
* :class:`TreeData` — full loaded tree: nodes by id, class starts by
  class index, ascendancy starts by ascendancy name.
* :func:`get_tree_data` — cached accessor.

The raw GGG JSON has lots of fields we don't need (sprites,
positions, mastery effect images, …); the loader keeps only what the
BFS algorithm in :mod:`poe1_fob.tree.dynamic` consumes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# The vendored JSON lives next to this module's package. Keep the path
# stable so the script that refreshes it doesn't drift.
_TREE_JSON_PATH = Path(__file__).parent.parent.parent.parent / "data" / "tree" / "3_28.json"


@dataclass(frozen=True, slots=True)
class TreeNode:
    """Pruned passive-tree node record."""

    id: int
    name: str | None
    is_keystone: bool
    is_notable: bool
    is_mastery: bool
    is_ascendancy_start: bool
    ascendancy_name: str | None  # e.g. "Juggernaut" — None for regular tree
    out: tuple[int, ...]  # outgoing adjacency (the tree is undirected, but GGG stores
    # both ``in`` and ``out``; ``out`` alone covers all edges from this node).
    class_start_index: int | None  # 0..6 when this is a class start, else None
    group: int | None  # cluster id for spatial layout, irrelevant for BFS
    stats: tuple[str, ...]  # human-readable mod lines from the raw tree JSON
    # For mastery nodes: the selectable effects, each (effect_id, stat lines).
    # Empty for every non-mastery node.
    mastery_effects: tuple[tuple[int, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class TreeData:
    """Full loaded tree, indexed for fast lookups."""

    nodes_by_id: dict[int, TreeNode]
    # class_index (PoB enum: 0=Scion .. 6=Shadow) -> class start node id
    class_starts: dict[int, int]
    # ascendancy name (e.g. "Juggernaut") -> ascendancy start node id
    ascendancy_starts: dict[str, int]
    raw_version: str | None  # GGG's embedded tree version label, if any
    # Mapping of class_index -> ascendancy_name list (3 per class)
    class_to_ascendancies: dict[int, tuple[str, ...]] = field(default_factory=dict)
    # Symmetric adjacency for undirected BFS: node_id -> frozenset of neighbors.
    # GGG stores ``in`` and ``out`` separately but the passive tree is
    # undirected; building this once at load time makes the BFS trivial.
    adjacency: dict[int, frozenset[int]] = field(default_factory=dict)


def _coerce_int(s: str | int) -> int | None:
    """GGG keys node ids as strings; the user's PoB has ints. Normalise."""
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _load_from_disk(path: Path) -> TreeData:
    raw_text = path.read_text(encoding="utf-8")
    data = json.loads(raw_text)

    raw_nodes: Mapping[str, Mapping[str, object]] = data["nodes"]
    nodes_by_id: dict[int, TreeNode] = {}
    class_starts: dict[int, int] = {}
    ascendancy_starts: dict[str, int] = {}
    class_to_ascendancies: dict[int, tuple[str, ...]] = {}

    for raw_id, raw_node in raw_nodes.items():
        nid = _coerce_int(raw_id)
        if nid is None:
            continue
        # Adjacency: GGG ``out`` is a list of string node ids.
        out_raw = raw_node.get("out")
        out_iter: tuple[int, ...] = ()
        if isinstance(out_raw, list):
            out_iter = tuple(
                n for n in (_coerce_int(x) for x in out_raw if isinstance(x, str)) if n is not None
            )
        csi_raw = raw_node.get("classStartIndex")
        csi = csi_raw if isinstance(csi_raw, int) else None
        group_raw = raw_node.get("group")
        group_val = group_raw if isinstance(group_raw, int) else None
        name_raw = raw_node.get("name")
        asc_raw = raw_node.get("ascendancyName")
        stats_raw = raw_node.get("stats")
        stats_iter: tuple[str, ...] = (
            tuple(s for s in stats_raw if isinstance(s, str)) if isinstance(stats_raw, list) else ()
        )
        me_raw = raw_node.get("masteryEffects")
        mastery_effects: tuple[tuple[int, tuple[str, ...]], ...] = ()
        if isinstance(me_raw, list):
            parsed_effects: list[tuple[int, tuple[str, ...]]] = []
            for eff in me_raw:
                if not isinstance(eff, dict):
                    continue
                raw_eff = eff.get("effect")
                eid = _coerce_int(raw_eff) if isinstance(raw_eff, str | int) else None
                if eid is None:
                    continue
                eff_stats_raw = eff.get("stats")
                eff_stats = (
                    tuple(s for s in eff_stats_raw if isinstance(s, str))
                    if isinstance(eff_stats_raw, list)
                    else ()
                )
                parsed_effects.append((eid, eff_stats))
            mastery_effects = tuple(parsed_effects)
        node = TreeNode(
            id=nid,
            name=name_raw if isinstance(name_raw, str) else None,
            is_keystone=bool(raw_node.get("isKeystone")),
            is_notable=bool(raw_node.get("isNotable")),
            is_mastery=bool(raw_node.get("isMastery")),
            is_ascendancy_start=bool(raw_node.get("isAscendancyStart")),
            ascendancy_name=asc_raw if isinstance(asc_raw, str) else None,
            out=out_iter,
            class_start_index=csi,
            group=group_val,
            stats=stats_iter,
            mastery_effects=mastery_effects,
        )
        nodes_by_id[nid] = node
        if node.class_start_index is not None:
            class_starts[node.class_start_index] = nid
        if node.is_ascendancy_start and node.ascendancy_name:
            ascendancy_starts[node.ascendancy_name] = nid

    # Build class -> ascendancies from the ``classes`` array
    for cls_idx, cls in enumerate(data.get("classes", [])):
        ascs = tuple(a["id"] for a in cls.get("ascendancies", []) if isinstance(a, dict))
        class_to_ascendancies[cls_idx] = ascs

    raw_version_obj = data.get("tree")
    raw_version = raw_version_obj if isinstance(raw_version_obj, str) else None

    # Build symmetric adjacency: edge a→b implies b→a for BFS purposes.
    # We also read the raw ``in`` field for nodes the loader otherwise
    # ignores, because some nodes (e.g. the Juggernaut ascendancy root)
    # have empty ``out`` lists but real incoming edges from the regular
    # tree.
    adj: dict[int, set[int]] = {nid: set(node.out) for nid, node in nodes_by_id.items()}
    for raw_id, raw_node in raw_nodes.items():
        nid = _coerce_int(raw_id)
        if nid is None:
            continue
        raw_in = raw_node.get("in")
        if not isinstance(raw_in, list):
            continue
        for raw_neighbor in raw_in:
            in_nid = _coerce_int(raw_neighbor) if isinstance(raw_neighbor, str) else None
            if in_nid is None:
                continue
            adj.setdefault(nid, set()).add(in_nid)
            adj.setdefault(in_nid, set()).add(nid)
    adjacency = {nid: frozenset(neighbors) for nid, neighbors in adj.items()}

    return TreeData(
        nodes_by_id=nodes_by_id,
        class_starts=class_starts,
        ascendancy_starts=ascendancy_starts,
        raw_version=raw_version,
        class_to_ascendancies=class_to_ascendancies,
        adjacency=adjacency,
    )


@lru_cache(maxsize=1)
def get_tree_data() -> TreeData:
    """Return the cached :class:`TreeData` for the bundled league snapshot."""

    if not _TREE_JSON_PATH.exists():
        raise FileNotFoundError(
            f"Passive tree JSON not found at {_TREE_JSON_PATH}. "
            "Run `python scripts/extract_tree_data.py` to fetch it."
        )
    return _load_from_disk(_TREE_JSON_PATH)


__all__ = ["TreeData", "TreeNode", "get_tree_data"]
