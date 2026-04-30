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
from .rares import (
    MOD_PATTERNS,
    ExtractedMod,
    ModPattern,
    clean_mod_lines,
    clean_mods,
    extract_mods,
    valuable_stat_filters,
    valuable_stat_filters_from_mods,
)
from .uniques import unique_variant

__all__ = [
    "MOD_PATTERNS",
    "ExtractedMod",
    "ModPattern",
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
    "clean_mod_lines",
    "clean_mods",
    "decode_export",
    "extract_mods",
    "load_pob",
    "parse_snapshot",
    "snapshot_to_build",
    "unique_variant",
    "valuable_stat_filters",
    "valuable_stat_filters_from_mods",
]
