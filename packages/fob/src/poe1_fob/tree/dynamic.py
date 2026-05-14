"""Step 16 — Dynamic passive tree progression derived from the user's PoB.

Replaces the hand-curated :data:`PROGRESSION_REGISTRY` for any build
where we have an actual :class:`PobSnapshot` to read from. The registry
stays as a fallback for the no-PoB case.

Algorithm:

1. **BFS the user's allocated subgraph** starting from the class's
   start node. The user's ``snapshot.tree.node_ids`` is a connected
   subgraph (PoE only lets you allocate nodes adjacent to an already-
   allocated one), modulo cluster-jewel notables which live in
   separate sub-trees (ids >= 65536).

2. **Bucket regular tree nodes by BFS distance** into 6 stages with
   natural campaign-to-endgame weighting:

   - Stage 1 (Early Campaign):  first 10% (≈ ~13 nodes for a lvl-100)
   - Stage 2 (Mid Campaign):    first 25%
   - Stage 3 (End Campaign):    first 50%
   - Stage 4 (Early Mapping):   first 70%
   - Stage 5 (End Mapping):     first 85%
   - Stage 6 (High Investment): all 100%

   Each subsequent stage is a strict superset of the previous one
   (the :class:`TreeProgression` validator enforces this), matching
   the natural "you don't unallocate as you level" reality.

3. **Ascendancy nodes** bucket by lab order (Normal → Cruel →
   Merciless → Uber). BFS from the ascendancy start, sort by distance,
   slice into groups of 2 — each PoE lab grants 2 ascendancy points.

4. **Mastery nodes** join the bucket from Stage 4 onward only — most
   builds respec masteries near endgame once the build identity is
   stable.

5. **Cluster-jewel notables** (ids >= 65536) live in PoB-generated
   subgraphs we can't BFS into; bucket them all into Stage 6
   (high-investment cluster jewel acquisitions).
"""

from __future__ import annotations

from collections import deque
from typing import Final

from ..pob.models import PobSnapshot
from .models import StageTree, TreeProgression
from .tree_data import TreeData, get_tree_data

_STAGE_KEYS: Final[tuple[str, ...]] = (
    "early_campaign",
    "mid_campaign",
    "end_campaign",
    "early_mapping",
    "end_mapping",
    "high_investment",
)

# Cumulative-coverage fractions per stage. Each entry is the fraction
# of the user's regular-tree nodes available *by the end of* that
# stage. The strict-superset property of TreeProgression makes the
# values monotone-increasing.
_STAGE_COVERAGE: Final[tuple[float, float, float, float, float, float]] = (
    0.10,
    0.25,
    0.50,
    0.70,
    0.85,
    1.00,
)

# Cluster-jewel notable node IDs start at 65536. PoB encodes them in a
# separate URL section; they're not in the official GGG tree data, and
# our BFS can't reach them via the regular adjacency graph.
_CLUSTER_ID_THRESHOLD: Final[int] = 65536


def _bfs_distances(
    start_id: int,
    allocated: frozenset[int],
    adjacency: dict[int, frozenset[int]],
) -> dict[int, int]:
    """Return ``{node_id: bfs_distance}`` for every reachable allocated node.

    Walks the user's allocated subgraph only — neighbors that aren't in
    ``allocated`` are skipped. The start node is included at distance 0
    (whether or not it's in ``allocated``).
    """

    distances: dict[int, int] = {start_id: 0}
    queue: deque[int] = deque([start_id])
    while queue:
        current = queue.popleft()
        cur_dist = distances[current]
        for neighbor in adjacency.get(current, frozenset()):
            if neighbor in distances:
                continue
            if neighbor not in allocated:
                continue
            distances[neighbor] = cur_dist + 1
            queue.append(neighbor)
    return distances


def _bucket_regular_nodes(
    sorted_ids: list[int],
) -> list[set[int]]:
    """Return six cumulative-superset sets matching :data:`_STAGE_COVERAGE`."""

    n = len(sorted_ids)
    buckets: list[set[int]] = []
    for fraction in _STAGE_COVERAGE:
        cutoff = round(n * fraction)
        buckets.append(set(sorted_ids[:cutoff]))
    # Edge case: rounding could leave the final stage missing tail
    # nodes when n * 1.0 floors below n. Ensure stage 6 == full set.
    buckets[-1] = set(sorted_ids)
    return buckets


def _bucket_ascendancy_nodes(
    asc_node_ids: list[int],
    asc_start_id: int | None,
    adjacency: dict[int, frozenset[int]],
) -> list[set[int]]:
    """Bucket ascendancy nodes into 6 stages by lab order.

    PoE grants 2 ascendancy points per lab over 4 labs (8 points typical).
    We distribute them as: stage 2 = lab 1 (Normal), stage 3 = lab 2
    (Cruel), stage 4 = lab 3 (Merciless), stage 5 = lab 4 (Uber).
    Stages 1 and 6 echo the cumulative set boundaries (no asc points
    in Early Campaign, all available by High Investment).

    When the ascendancy start node is known, BFS inside the ascendancy
    subgraph to order nodes by distance (= depth in the asc path).
    """

    if not asc_node_ids:
        return [set() for _ in range(6)]

    # BFS from the ascendancy start through ONLY the user's allocated
    # ascendancy nodes, so depth tracks "how far in did the user go".
    if asc_start_id is not None and asc_start_id in adjacency:
        asc_set = frozenset(asc_node_ids)
        distances = _bfs_distances(asc_start_id, asc_set, adjacency)
        ordered = sorted(asc_node_ids, key=lambda nid: distances.get(nid, 99))
    else:
        # No usable start — keep input order.
        ordered = list(asc_node_ids)

    # Distribute across 4 labs: first 2 → lab 1 (stage 2), next 2 →
    # lab 2 (stage 3), and so on. Surplus rolls into the last lab.
    lab_points = [ordered[i : i + 2] for i in range(0, len(ordered), 2)]

    # Map labs to stages: lab 1 -> stage 2, lab 2 -> stage 3, ...
    stage_to_asc: list[set[int]] = [set() for _ in range(6)]
    cumulative: set[int] = set()
    for stage_idx in range(6):
        if 2 <= stage_idx <= 5:
            lab_idx = stage_idx - 2  # stage 2 -> lab 0, ..., stage 5 -> lab 3
            if lab_idx < len(lab_points):
                cumulative.update(lab_points[lab_idx])
            else:
                # User has fewer than 4 labs done — keep the last
                # known set.
                pass
        elif stage_idx == 0:
            # Early Campaign: no ascendancy yet (you haven't done lab 1).
            pass
        else:  # stage_idx == 1 — Mid Campaign: still pre-lab-1 for most.
            pass
        stage_to_asc[stage_idx] = set(cumulative)
    # Force final stage to include everything the user has.
    stage_to_asc[5] = set(ordered)
    return stage_to_asc


def _bucket_mastery_nodes(
    mastery_node_ids: list[int],
    effective_dict: dict[int, int],
) -> list[set[int]]:
    """Mastery nodes appear from Stage 4 onward (early mapping)."""

    full = set(mastery_node_ids)
    return [set(), set(), set(), full, full, full]


def derive_tree_progression(
    snapshot: PobSnapshot,
    *,
    target_name: str = "derived",
    tree_data: TreeData | None = None,
) -> TreeProgression | None:
    """Synthesise a 6-stage tree progression from a user PoB snapshot.

    Returns None when the snapshot's tree is empty or the class isn't
    recognisable (very unlikely for a real PoB export).
    """

    user_ids = list(snapshot.tree.node_ids)
    if not user_ids:
        return None
    user_set = set(user_ids)

    td = tree_data if tree_data is not None else get_tree_data()

    class_start_id = td.class_starts.get(snapshot.tree.class_id)
    if class_start_id is None:
        return None

    # Partition the user's nodes by type so the bucketers can handle
    # each category with its own rule.
    regular_user_ids: list[int] = []
    asc_user_ids: list[int] = []
    mastery_user_ids: list[int] = []
    cluster_user_ids: list[int] = []
    for nid in user_ids:
        if nid >= _CLUSTER_ID_THRESHOLD:
            cluster_user_ids.append(nid)
            continue
        node = td.nodes_by_id.get(nid)
        if node is None:
            # Unknown ids (legacy / removed nodes) — drop silently.
            continue
        if node.is_mastery:
            mastery_user_ids.append(nid)
        elif node.ascendancy_name:
            asc_user_ids.append(nid)
        else:
            regular_user_ids.append(nid)

    # BFS inside the user's regular-tree subgraph from the class start.
    distances = _bfs_distances(
        class_start_id,
        frozenset(regular_user_ids) | {class_start_id},
        td.adjacency,
    )
    # Sort regular nodes by BFS distance ascending; class start at
    # distance 0 always lands in Stage 1.
    sorted_regular = sorted(
        regular_user_ids,
        key=lambda nid: (distances.get(nid, 99), nid),
    )
    # The class start itself is auto-allocated by PoE — include it in
    # the stage set so the export matches the user's <Spec nodes>.
    if class_start_id in user_set and class_start_id not in sorted_regular:
        sorted_regular.insert(0, class_start_id)

    regular_buckets = _bucket_regular_nodes(sorted_regular)

    # Ascendancy: pick the user's chosen ascendancy's start node.
    asc_start_id: int | None = None
    if snapshot.ascendancy is not None:
        asc_name = snapshot.ascendancy.value.capitalize()
        asc_start_id = td.ascendancy_starts.get(asc_name)
    asc_buckets = _bucket_ascendancy_nodes(asc_user_ids, asc_start_id, td.adjacency)

    # Mastery nodes only from Stage 4 onward.
    mastery_buckets = _bucket_mastery_nodes(mastery_user_ids, snapshot.tree.mastery_effects)

    # Cluster-jewel notables: all in Stage 6.
    cluster_set = set(cluster_user_ids)

    # Build the StageTree per stage by unioning the partial sets.
    stages: list[StageTree] = []
    for idx, key in enumerate(_STAGE_KEYS):
        ids: set[int] = set()
        ids |= regular_buckets[idx]
        ids |= asc_buckets[idx]
        ids |= mastery_buckets[idx]
        if idx == 5:
            ids |= cluster_set

        # Collect notables + ascendancy node names for the StageTree's
        # informational fields (used by the UI rationale section).
        notables: list[str] = []
        ascendancy_nodes: list[str] = []
        for nid in ids:
            node = td.nodes_by_id.get(nid)
            if node is None:
                continue
            if node.is_notable and node.name and not node.ascendancy_name:
                notables.append(node.name)
            elif node.ascendancy_name and (node.is_notable or node.is_keystone):
                ascendancy_nodes.append(node.name or "")

        # Pass mastery effects only for stages that include them.
        stage_mastery: tuple[tuple[int, int], ...] = ()
        if idx >= 3 and mastery_user_ids:
            included_masteries = {nid for nid in mastery_user_ids if nid in ids}
            stage_mastery = tuple(
                (nid, eid)
                for nid, eid in snapshot.tree.mastery_effects.items()
                if nid in included_masteries
            )

        stages.append(
            StageTree(
                stage_key=key,
                node_ids=tuple(sorted(ids)),
                notables=tuple(sorted(set(notables)))[:8],
                ascendancy_nodes=tuple(sorted(set(ascendancy_nodes))),
                mastery_effects=stage_mastery,
            )
        )

    return TreeProgression(target_name=target_name, stages=tuple(stages))


__all__ = ["derive_tree_progression"]
