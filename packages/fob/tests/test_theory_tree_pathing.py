"""Tests for the BFS tree-pathing in `theory.generator` (Step 44).

Two scopes:

* `bfs_path` unit tests — pure graph algorithm, no tree data.
* `_select_tree_nodes` integration tests — the path returned must be
  contiguous on the real `TreeData.adjacency`, which is the whole point
  of Step 44 (Step 40-43 produced disconnected node IDs).
"""

from __future__ import annotations

from itertools import pairwise

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
    """The critical integration test: consecutive non-ascendancy nodes
    must be adjacent in `TreeData.adjacency`."""
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
    # the connected BFS path — split them off before checking adjacency.
    path_nodes = [n for n in nodes if n.type != "ascendancy"]
    assert len(path_nodes) >= 2

    adj = get_tree_data().adjacency
    for prev, curr in pairwise(path_nodes):
        assert curr.node_id in adj.get(prev.node_id, frozenset()), (
            f"node {curr.node_id} ('{curr.name}') is not adjacent to "
            f"{prev.node_id} ('{prev.name}') — path is broken"
        )


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
