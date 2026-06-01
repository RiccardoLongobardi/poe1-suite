"""Loader for the vendored cluster-jewel catalogue (Step 76, Fase 2).

Reads ``packages/fob/data/cluster/cluster_3_28.json`` (produced by
``scripts/extract_cluster_jewels.py`` from PoB's own loaded data) and exposes
the themes (per size, with the exact "Added Small Passive Skills grant: …"
enchant) + the cluster notable pool (name → stat text).

The mirror-tier optimiser uses these to build Large/Medium cluster jewels from
scratch: pick a build-relevant theme, score candidate notables by the build's
damage keywords, socket the jewel at a reachable Large socket, and let PoB's
real calc decide (fitness-gated).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "cluster" / "cluster_3_28.json"

LARGE = "Large Cluster Jewel"
MEDIUM = "Medium Cluster Jewel"
SMALL = "Small Cluster Jewel"


class ClusterTheme(NamedTuple):
    """One cluster-jewel damage theme (the "Added Small Passive Skills grant"
    enchant) for a given size."""

    size: str
    tag: str
    name: str
    enchant: str


@lru_cache(maxsize=1)
def _load() -> dict[str, object]:
    if not _DATA_PATH.exists():  # pragma: no cover - deployment guard
        return {}
    data: dict[str, object] = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    return data


@lru_cache(maxsize=1)
def get_themes() -> dict[str, tuple[ClusterTheme, ...]]:
    """All themes keyed by size."""
    raw = _load().get("themes", {})
    out: dict[str, tuple[ClusterTheme, ...]] = {}
    if isinstance(raw, dict):
        for size, lst in raw.items():
            out[size] = tuple(
                ClusterTheme(size=size, tag=t["tag"], name=t["name"], enchant=t["enchant"])
                for t in lst
            )
    return out


@lru_cache(maxsize=1)
def get_notables() -> dict[str, str]:
    """Cluster notable name → its stat text (for relevance scoring)."""
    raw = _load().get("notables", {})
    return dict(raw) if isinstance(raw, dict) else {}


def themes_for_size(size: str) -> tuple[ClusterTheme, ...]:
    return get_themes().get(size, ())


def size_passive_count(size: str) -> int:
    """The max "Adds N Passive Skills" for a size (Large 12, Medium 6, Small 3)."""
    sizes = _load().get("sizes", {})
    if isinstance(sizes, dict):
        info = sizes.get(size)
        if isinstance(info, dict) and isinstance(info.get("max"), int):
            return int(info["max"])
    return {LARGE: 12, MEDIUM: 6, SMALL: 3}.get(size, 3)


__all__ = [
    "LARGE",
    "MEDIUM",
    "SMALL",
    "ClusterTheme",
    "get_notables",
    "get_themes",
    "size_passive_count",
    "themes_for_size",
]
