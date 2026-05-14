"""Step 16 — tests for dynamic tree progression derivation."""

from __future__ import annotations

from pathlib import Path

import pytest

from poe1_fob.pob import decode_export, parse_snapshot
from poe1_fob.tree.dynamic import (
    _bucket_regular_nodes,
    derive_tree_progression,
)
from poe1_fob.tree.tree_data import get_tree_data

# ---------------------------------------------------------------------------
# tree_data loader smoke
# ---------------------------------------------------------------------------


def test_tree_data_loads_with_expected_shape() -> None:
    td = get_tree_data()
    # Sanity: GGG's published tree has ~3300 regular nodes for PoE 1.
    assert len(td.nodes_by_id) > 3000
    # All seven base classes plus their ascendancies must be indexed.
    assert set(td.class_starts.keys()) == {0, 1, 2, 3, 4, 5, 6}
    assert "Juggernaut" in td.ascendancy_starts
    assert "Chieftain" in td.ascendancy_starts
    assert "Necromancer" in td.ascendancy_starts


def test_tree_data_adjacency_is_symmetric() -> None:
    """Every edge a→b must imply b→a (the tree is undirected)."""

    td = get_tree_data()
    sample = list(td.adjacency.items())[:200]  # spot-check, not full sweep
    for nid, neighbors in sample:
        for n in neighbors:
            assert nid in td.adjacency.get(n, frozenset()), f"asymmetric edge: {nid}->{n}"


def test_class_start_connects_to_ascendancy_start() -> None:
    """Class start nodes must have an edge to each of their ascendancy roots."""

    td = get_tree_data()
    # Marauder class index 1, Juggernaut ascendancy start.
    marauder_start = td.class_starts[1]
    jugg_start = td.ascendancy_starts["Juggernaut"]
    assert jugg_start in td.adjacency[marauder_start]


# ---------------------------------------------------------------------------
# _bucket_regular_nodes
# ---------------------------------------------------------------------------


def test_bucket_regular_nodes_monotone_supersets() -> None:
    """Each stage's set must be a superset of the previous stage's."""

    ids = list(range(100))  # 100 distinct fake ids
    buckets = _bucket_regular_nodes(ids)
    assert len(buckets) == 6
    for i in range(1, 6):
        assert buckets[i] >= buckets[i - 1], f"stage {i} is not a superset of stage {i - 1}"
    # Final stage must contain everything.
    assert buckets[-1] == set(ids)


def test_bucket_regular_nodes_coverage_fractions() -> None:
    """For 100 nodes, stages should land at roughly 10/25/50/70/85/100."""

    ids = list(range(100))
    buckets = _bucket_regular_nodes(ids)
    assert len(buckets[0]) == 10
    assert len(buckets[1]) == 25
    assert len(buckets[2]) == 50
    assert len(buckets[3]) == 70
    assert len(buckets[4]) == 85
    assert len(buckets[5]) == 100


def test_bucket_regular_nodes_handles_small_sets() -> None:
    """Tiny allocations (e.g. lvl 30 char) still produce 6 valid stages."""

    ids = list(range(7))  # only 7 nodes
    buckets = _bucket_regular_nodes(ids)
    # Each bucket is a valid subset of the next.
    for i in range(1, 6):
        assert buckets[i] >= buckets[i - 1]
    # Final stage = all 7.
    assert buckets[-1] == set(ids)


def test_bucket_regular_nodes_empty_input() -> None:
    """Zero nodes → 6 empty stages."""

    buckets = _bucket_regular_nodes([])
    assert all(b == set() for b in buckets)


# ---------------------------------------------------------------------------
# End-to-end on the real fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_snapshot() -> object:
    code = (Path(__file__).parent / "fixtures" / "pob_YNQeadFwNBmX.txt").read_text().strip()
    return parse_snapshot(decode_export(code), export_code=code)


def test_derive_tree_progression_six_stages(fixture_snapshot: object) -> None:
    prog = derive_tree_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    assert len(prog.stages) == 6
    assert [s.stage_key for s in prog.stages] == [
        "early_campaign",
        "mid_campaign",
        "end_campaign",
        "early_mapping",
        "end_mapping",
        "high_investment",
    ]


def test_derive_tree_progression_stages_monotone(fixture_snapshot: object) -> None:
    """Each stage's node_ids must be a superset of the previous stage's."""

    prog = derive_tree_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    prev: set[int] = set()
    for stage in prog.stages:
        cur = set(stage.node_ids)
        assert cur >= prev, f"stage {stage.stage_key} is not a superset of previous"
        prev = cur


def test_derive_tree_progression_final_matches_user_pob(fixture_snapshot: object) -> None:
    """The high_investment stage must equal the user's complete allocation."""

    snap = fixture_snapshot
    prog = derive_tree_progression(snap)  # type: ignore[arg-type]
    assert prog is not None
    final_ids = set(prog.stages[-1].node_ids)
    user_ids = set(snap.tree.node_ids)  # type: ignore[attr-defined]
    assert final_ids == user_ids


def test_derive_tree_progression_cluster_nodes_only_in_final(
    fixture_snapshot: object,
) -> None:
    """Cluster-jewel notables (ids >= 65536) must appear only at high_investment."""

    prog = derive_tree_progression(fixture_snapshot)  # type: ignore[arg-type]
    assert prog is not None
    for stage in prog.stages[:-1]:
        cluster_in_stage = [n for n in stage.node_ids if n >= 65536]
        assert not cluster_in_stage, (
            f"stage {stage.stage_key} contains cluster ids: {cluster_in_stage[:3]}"
        )
    # The final stage must include them.
    final_cluster = [n for n in prog.stages[-1].node_ids if n >= 65536]
    assert len(final_cluster) > 0


def test_derive_tree_progression_mastery_effects_propagated(
    fixture_snapshot: object,
) -> None:
    """Mastery effects must survive into the high_investment stage."""

    snap = fixture_snapshot
    prog = derive_tree_progression(snap)  # type: ignore[arg-type]
    assert prog is not None
    final_mastery = dict(prog.stages[-1].mastery_effects)
    user_mastery = dict(snap.tree.mastery_effects)  # type: ignore[attr-defined]
    # All user masteries on allocated nodes must be in the final stage.
    for nid, eid in user_mastery.items():
        assert final_mastery.get(nid) == eid


def test_derive_tree_progression_early_campaign_is_small(
    fixture_snapshot: object,
) -> None:
    """Early Campaign must have far fewer nodes than the user's total."""

    snap = fixture_snapshot
    prog = derive_tree_progression(snap)  # type: ignore[arg-type]
    assert prog is not None
    early = len(prog.stages[0].node_ids)
    total = len(snap.tree.node_ids)  # type: ignore[attr-defined]
    # Early Campaign coverage fraction is 10% (with class start), so a
    # 134-node build should yield roughly ~9-15 nodes.
    assert 1 <= early <= int(total * 0.20)


def test_derive_tree_progression_empty_node_set_returns_none(
    fixture_snapshot: object,
) -> None:
    empty = fixture_snapshot.model_copy(  # type: ignore[attr-defined]
        update={"tree": fixture_snapshot.tree.model_copy(update={"node_ids": ()})}  # type: ignore[attr-defined]
    )
    assert derive_tree_progression(empty) is None
