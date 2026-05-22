"""Tests for the BFS tree-pathing in `theory.generator` (Step 44).

Two scopes:

* `bfs_path` unit tests — pure graph algorithm, no tree data.
* `_select_tree_nodes` integration tests — the path returned must be
  contiguous on the real `TreeData.adjacency`, which is the whole point
  of Step 44 (Step 40-43 produced disconnected node IDs).
"""

from __future__ import annotations

from poe1_fob.theory import TheoryIntent
from poe1_fob.theory.generator import _MAX_TREE_NODES, _select_tree_nodes, bfs_path
from poe1_fob.tree.tree_data import get_tree_data


def test_bfs_path_direct_neighbors() -> None:
    adj: dict[int, frozenset[int]] = {1: frozenset({2}), 2: frozenset({1})}
    assert bfs_path(adj, 1, 2) == [1, 2]


def test_bfs_path_three_steps() -> None:
    # 1 — 2 — 3 — 4, plus a shortcut 1 — 4 (so the BFS should still find
    # the short version, not the long one).
    adj: dict[int, frozenset[int]] = {
        1: frozenset({2, 4}),
        2: frozenset({1, 3}),
        3: frozenset({2, 4}),
        4: frozenset({1, 3}),
    }
    path = bfs_path(adj, 1, 3)
    assert path is not None
    # Two valid shortest paths: 1→2→3 or 1→4→3. Either is length 3.
    assert len(path) == 3
    assert path[0] == 1 and path[-1] == 3


def test_bfs_path_unreachable() -> None:
    # Two disconnected components.
    adj: dict[int, frozenset[int]] = {
        1: frozenset({2}),
        2: frozenset({1}),
        3: frozenset({4}),
        4: frozenset({3}),
    }
    assert bfs_path(adj, 1, 3) is None


def test_select_tree_nodes_connected() -> None:
    """The critical integration test: the allocation is one connected
    component. Every non-ascendancy node (after the class start) must be
    adjacent to **at least one earlier** node in the list.

    Step 45a: the fill phase appends boundary nodes that are adjacent to
    *some* already-visited node, not necessarily the immediately-previous
    one — so we check "adjacent to any earlier" rather than strict
    consecutive adjacency.
    """
    intent = TheoryIntent(
        character_class="Marauder",
        ascendancy="Juggernaut",
        primary_skill="Cyclone",
        damage_type="physical",
        defence_archetype="life",
        budget="mid",
        focus="mapping",
    )
    nodes = _select_tree_nodes(intent)
    # Ascendancy notables are appended at the end and are NOT part of
    # the connected tree allocation — split them off.
    path_nodes = [n for n in nodes if n.type != "ascendancy"]
    assert len(path_nodes) >= 2

    adj = get_tree_data().adjacency
    seen: set[int] = {path_nodes[0].node_id}
    for node in path_nodes[1:]:
        neighbours_seen = adj.get(node.node_id, frozenset()) & seen
        assert neighbours_seen, (
            f"node {node.node_id} ('{node.name}') is not adjacent to any "
            "earlier node — the allocation is disconnected"
        )
        seen.add(node.node_id)


def test_select_tree_nodes_budget() -> None:
    """Step 45a: a real intent now allocates a meaningful tree (≥ 60
    nodes), not the ~9-20 the pre-fill waypoint walk produced."""
    intent = TheoryIntent(
        character_class="Marauder",
        ascendancy="Juggernaut",
        primary_skill="Cyclone",
        damage_type="physical",
        defence_archetype="life",
        budget="mid",
        focus="mapping",
    )
    nodes = _select_tree_nodes(intent)
    path_nodes = [n for n in nodes if n.type != "ascendancy"]
    assert len(path_nodes) >= 60, f"only {len(path_nodes)} nodes allocated"
    assert len(path_nodes) <= _MAX_TREE_NODES


def test_fill_to_budget_unit() -> None:
    """`_fill_to_budget` on a hand-built graph: every added node is
    adjacent to a previously-visited node, and it stops on empty boundary."""
    from poe1_fob.theory.generator import _fill_to_budget
    from poe1_fob.tree.tree_data import TreeNode

    def _node(nid: int) -> TreeNode:
        return TreeNode(
            id=nid,
            name=f"n{nid}",
            is_keystone=False,
            is_notable=False,
            is_mastery=False,
            is_ascendancy_start=False,
            ascendancy_name=None,
            out=(),
            class_start_index=None,
            group=None,
            stats=(),
        )

    # A line graph 0—1—2—…—9 (10 nodes); start visited from the centre.
    adjacency: dict[int, frozenset[int]] = {}
    for i in range(10):
        nbrs = {i - 1, i + 1} & set(range(10))
        adjacency[i] = frozenset(nbrs)
    all_nodes = {i: _node(i) for i in range(10)}

    visited = {5}
    added = _fill_to_budget(visited, adjacency, all_nodes, "physical", "life", 8)
    # Budget 8: visited grows from 1 → 8, so 7 nodes added.
    assert len(added) == 7
    seen = {5}
    for nid in added:
        assert adjacency[nid] & seen, f"{nid} not adjacent to a visited node"
        seen.add(nid)

    # Empty-boundary stop: budget far above graph size halts gracefully.
    visited2 = {0}
    added2 = _fill_to_budget(visited2, adjacency, all_nodes, "physical", "life", 999)
    assert len(visited2) == 10  # whole graph reachable, then boundary empty
    assert len(added2) == 9


def test_select_tree_nodes_max_length() -> None:
    intent = TheoryIntent(
        character_class="Witch",
        ascendancy="Elementalist",
        primary_skill="Fireball",
        damage_type="fire",
        defence_archetype="life",
        budget="endgame",
        focus="allcontent",
    )
    nodes = _select_tree_nodes(intent)
    # Path portion (everything except the ascendancy tail) must respect
    # the cap. The ascendancy notables are a fixed ≤4 extra entries.
    path_nodes = [n for n in nodes if n.type != "ascendancy"]
    assert len(path_nodes) <= _MAX_TREE_NODES


def test_travel_nodes_have_type_travel() -> None:
    """Path connectors are tagged ``travel`` so the UI can hide them."""
    intent = TheoryIntent(
        character_class="Ranger",
        ascendancy="Deadeye",
        primary_skill="Lightning Arrow",
        damage_type="lightning",
        defence_archetype="life",
        budget="mid",
        focus="mapping",
    )
    nodes = _select_tree_nodes(intent)
    # The list must contain at least one travel node — BFS paths
    # through more nodes than just the keystones and notables.
    types = {n.type for n in nodes}
    assert "travel" in types
    # And no path node carries an unknown type.
    assert types.issubset({"keystone", "notable", "ascendancy", "start", "travel"})
