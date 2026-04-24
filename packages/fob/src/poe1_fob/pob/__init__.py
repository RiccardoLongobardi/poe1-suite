"""PoB (Path of Building) import pipeline.

Public entry points:

* :func:`load_pob` — resolve a raw export code, pobb.in URL, or
  pastebin URL into a tuple of ``(pob_code, origin_url)``.
* :func:`decode_export` — turn a PoB export code (url-safe base64 of
  zlib-compressed XML) into decoded UTF-8 bytes.
* :func:`parse_snapshot` — parse the decoded XML into a
  :class:`PobSnapshot`.
* :func:`snapshot_to_build` — reduce the rich snapshot to the lean
  cross-source :class:`poe1_core.Build` used by downstream modules.

Downstream callers (the FastAPI router, the Ranking engine) should
import from this package, never from the submodules directly.
"""

from __future__ import annotations

from .ingest import PobInputError, load_pob
from .mapper import snapshot_to_build
from .models import (
    PobConfigOption,
    PobGem,
    PobItem,
    PobJewel,
    PobPantheon,
    PobPassiveTree,
    PobSkillGroup,
    PobSnapshot,
)
from .parser import PobParseError, decode_export, parse_snapshot

__all__ = [
    "PobConfigOption",
    "PobGem",
    "PobInputError",
    "PobItem",
    "PobJewel",
    "PobPantheon",
    "PobParseError",
    "PobPassiveTree",
    "PobSkillGroup",
    "PobSnapshot",
    "decode_export",
    "load_pob",
    "parse_snapshot",
    "snapshot_to_build",
]
