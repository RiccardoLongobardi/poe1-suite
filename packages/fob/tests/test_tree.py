"""Tests for the Step 14 T1 tree progression skeleton."""

from __future__ import annotations

import pytest

from poe1_fob.tree import StageTree, TreeProgression, encode_pob_tree_url

# ---------------------------------------------------------------------------
# StageTree
# ---------------------------------------------------------------------------


def test_stage_tree_dedupes_and_sorts_node_ids() -> None:
    s = StageTree(stage_key="early_campaign", node_ids=(50459, 12345, 12345, 7777))
    assert s.node_ids == (7777, 12345, 50459)


def test_stage_tree_is_frozen() -> None:
    s = StageTree(stage_key="early_campaign", node_ids=(1,))
    with pytest.raises((ValueError, TypeError)):
        s.stage_key = "mid_campaign"


# ---------------------------------------------------------------------------
# TreeProgression
# ---------------------------------------------------------------------------


def test_progression_monotone_pass() -> None:
    p = TreeProgression(
        target_name="rf_pohx",
        stages=(
            StageTree(stage_key="early_campaign", node_ids=(1, 2)),
            StageTree(stage_key="mid_campaign", node_ids=(1, 2, 3)),
            StageTree(stage_key="end_campaign", node_ids=(1, 2, 3, 4)),
        ),
    )
    assert len(p.stages) == 3
    mid = p.for_stage("mid_campaign")
    assert mid is not None and 3 in mid.node_ids


def test_progression_rejects_non_monotone() -> None:
    """A stage cannot un-allocate nodes from a previous stage."""

    with pytest.raises(ValueError, match="non-monotone"):
        TreeProgression(
            target_name="bad",
            stages=(
                StageTree(stage_key="early_campaign", node_ids=(1, 2, 3)),
                StageTree(stage_key="mid_campaign", node_ids=(1, 2)),  # dropped 3
            ),
        )


def test_progression_rejects_duplicate_stage_keys() -> None:
    with pytest.raises(ValueError, match="duplicate stage_key"):
        TreeProgression(
            target_name="bad",
            stages=(
                StageTree(stage_key="early_campaign", node_ids=(1,)),
                StageTree(stage_key="early_campaign", node_ids=(1, 2)),
            ),
        )


def test_progression_for_stage_returns_none_for_missing() -> None:
    p = TreeProgression(
        target_name="x",
        stages=(StageTree(stage_key="early_campaign", node_ids=(1,)),),
    )
    assert p.for_stage("high_investment") is None


# ---------------------------------------------------------------------------
# encode_pob_tree_url
# ---------------------------------------------------------------------------


def test_encode_pob_tree_url_returns_full_url() -> None:
    url = encode_pob_tree_url(node_ids=[50459, 12345], character_class="Marauder")
    assert url.startswith("https://www.pathofexile.com/passive-skill-tree/")
    # Encoded part is non-empty and url-safe-base64.
    encoded = url.removeprefix("https://www.pathofexile.com/passive-skill-tree/")
    assert encoded
    # url-safe-base64 alphabet: A-Z a-z 0-9 - _
    assert all(c.isalnum() or c in "-_" for c in encoded), encoded


def test_encode_pob_tree_url_deterministic_on_node_set() -> None:
    """Same nodes (order-independent) → same URL."""

    a = encode_pob_tree_url(node_ids=[1, 2, 3], character_class="Marauder")
    b = encode_pob_tree_url(node_ids=[3, 2, 1, 2], character_class="Marauder")
    assert a == b


def test_encode_pob_tree_url_changes_with_class() -> None:
    """Different starting class yields a different URL."""

    a = encode_pob_tree_url(node_ids=[1, 2], character_class="Marauder")
    b = encode_pob_tree_url(node_ids=[1, 2], character_class="Witch")
    assert a != b


def test_encode_pob_tree_url_changes_with_ascendancy() -> None:
    a = encode_pob_tree_url(node_ids=[1], character_class="Marauder", ascendancy="Juggernaut")
    b = encode_pob_tree_url(node_ids=[1], character_class="Marauder", ascendancy="Chieftain")
    assert a != b


def test_encode_pob_tree_url_handles_empty_nodes() -> None:
    url = encode_pob_tree_url(node_ids=[], character_class="Marauder")
    # Empty allocation is a valid edge case — a fresh character.
    assert url.startswith("https://www.pathofexile.com/passive-skill-tree/")
