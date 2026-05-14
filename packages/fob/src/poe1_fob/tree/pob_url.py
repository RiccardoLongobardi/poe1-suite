"""Encode a passive node set into a PathOfExile tree-URL fragment.

PoE's official tree share format (used by `pathofexile.com/passive-skill-tree/<base64>`)
is documented loosely in the community wiki:

* 6-byte header: ``[ver:u32be][char_class:u8][ascendancy_class:u8]``
* 2-byte node-count (u16be) followed by ``count * 2`` bytes (u16be ids)
  for the regular passive nodes.
* (Newer formats also pack masteries and cluster jewel ids; we stick to
  the v6-compatible regular-node-only encoding for now — it covers the
  Pohx-style "here are the points to allocate" use case.)

The resulting bytes are url-safe-base64 encoded. The full URL is::

    https://www.pathofexile.com/passive-skill-tree/<encoded>

This module deliberately stays lightweight (no heavy dependencies). The
full PoB-desktop XML encoder for items + gems lives in a future
:mod:`poe1_fob.pob.encode` module (Step 14 T4).
"""

from __future__ import annotations

import base64
import struct
from collections.abc import Iterable

# PoE 1 character classes (in tree encoding order). The tree-URL encoder
# stamps a single byte for the starting class.
_CLASS_TO_BYTE: dict[str, int] = {
    "Scion": 0,
    "Marauder": 1,
    "Ranger": 2,
    "Witch": 3,
    "Duelist": 4,
    "Templar": 5,
    "Shadow": 6,
}

# Ascendancy → ascendancy byte. Order matches PoE's own enum;
# 0 = base class (no ascendancy chosen yet).
_ASCENDANCY_TO_BYTE: dict[str, int] = {
    # Marauder
    "Juggernaut": 1,
    "Berserker": 2,
    "Chieftain": 3,
    # Ranger
    "Raider": 1,
    "Deadeye": 2,
    "Pathfinder": 3,
    # Duelist
    "Slayer": 1,
    "Gladiator": 2,
    "Champion": 3,
    # Witch
    "Necromancer": 1,
    "Occultist": 2,
    "Elementalist": 3,
    # Templar
    "Inquisitor": 1,
    "Hierophant": 2,
    "Guardian": 3,
    # Shadow
    "Assassin": 1,
    "Saboteur": 2,
    "Trickster": 3,
    # Scion
    "Ascendant": 1,
}

_TREE_VERSION = 6  # PoE skill tree v6 encoding
_TREE_BASE_URL = "https://www.pathofexile.com/passive-skill-tree/"


def encode_pob_tree_url(
    *,
    node_ids: Iterable[int],
    character_class: str = "Marauder",
    ascendancy: str | None = None,
) -> str:
    """Encode a node set into a passive-skill-tree share URL.

    Returns the full URL ready to paste into a browser. The encoded
    bytes are url-safe-base64 (= replaced by underscore-friendly
    chars, padding stripped — matches PoE's own decoder).

    Note: this encodes ONLY the regular passive nodes. Masteries and
    cluster jewel notables aren't part of the v6 share format; they'll
    appear as missing in the in-game tree. For a complete share with
    masteries we'd need v7 — added once Step 14 T4 ships the full PoB
    XML encoder.
    """

    class_byte = _CLASS_TO_BYTE.get(character_class, 0)
    asc_byte = _ASCENDANCY_TO_BYTE.get(ascendancy or "", 0)

    sorted_unique = sorted({int(n) for n in node_ids})

    # 7-byte header layout (PoE tree v6, verified empirically against
    # real PoB Community 3.28 exports — see tests + the analysis in
    # packages/fob/tests/test_pob_url.py):
    #   0..3  version u32be
    #   4     class id
    #   5     ascendancy id
    #   6     reserved flag (0 for share URLs we generate)
    # Node ids start at byte 7, each u16be.
    header = struct.pack(">IBBB", _TREE_VERSION, class_byte, asc_byte, 0)
    # Node section: count is implicit in the byte length on PoE's side
    # for v4+; we pack each node as u16be.
    node_section = b"".join(struct.pack(">H", node) for node in sorted_unique)
    # Cluster jewel section (empty), mastery section (empty) — keep
    # placeholder zero counts so PoE's parser doesn't choke.
    trailing = struct.pack(">BBB", 0, 0, 0)

    payload = header + node_section + trailing
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=").decode("ascii")
    return f"{_TREE_BASE_URL}{encoded}"
