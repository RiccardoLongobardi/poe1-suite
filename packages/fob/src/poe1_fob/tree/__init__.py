"""Tree progression — per-stage skill tree allocations.

Step 14 T1 first slice. Each stage of a build template can carry a
:class:`StageTree` describing which passive nodes are allocated by
the end of that stage. Templates that don't ship a tree fall back
to ``None`` (the planner displays "tree non disponibile per questo
stage" in the UI).

Public surface:

* :class:`StageTree` — frozen dataclass: stage_key + node IDs +
  notable name list + optional pob_url.
* :class:`TreeProgression` — ordered tuple of StageTree, one per
  active stage of a build.
* :func:`encode_pob_tree_url` — turn a node-id set into a Path of
  Building tree URL the user can paste into the live PoB website
  (https://www.pathofexile.com/passive-skill-tree/<base64>).

Heavy lifting (full PoB encode of items + gems + tree) lives in
the future :mod:`poe1_fob.pob.encode` module — Step 14 T4.
"""

from __future__ import annotations

from .models import StageTree, TreeProgression
from .pob_url import encode_pob_tree_url
from .progressions import (
    PROGRESSION_REGISTRY,
    RF_POHX_PROGRESSION,
    SPECTRE_NECRO_PROGRESSION,
    progression_for,
)

__all__ = [
    "PROGRESSION_REGISTRY",
    "RF_POHX_PROGRESSION",
    "SPECTRE_NECRO_PROGRESSION",
    "StageTree",
    "TreeProgression",
    "encode_pob_tree_url",
    "progression_for",
]
