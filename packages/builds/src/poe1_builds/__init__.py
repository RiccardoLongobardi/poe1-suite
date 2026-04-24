"""Ladder build ingestion for PoE 1.

Public surface:

* :class:`RemoteBuildRef` — lightweight list entry from the columnar
  search response.
* :class:`FullBuild` — hydrated single-character detail, including the
  raw ``path_of_building_export`` string for the PoB pipeline.
* :class:`BuildsSnapshot` — one search fetch, wrapping a tuple of refs.
* :class:`BuildFilter` — server/post-fetch filter spec.
* :class:`poe1_builds.sources.ninja.NinjaBuildsSource` — poe.ninja adapter.
* :class:`poe1_builds.service.BuildsService` — high-level facade.
"""

from __future__ import annotations

from poe1_builds.models import (
    BuildFilter,
    BuildSortKey,
    BuildsSnapshot,
    BuildStatus,
    DefenseType,
    DefensiveStats,
    FullBuild,
    GemRef,
    ItemEntry,
    ItemProvidedGemGroup,
    KeystonePassive,
    MasteryChoice,
    RemoteBuildRef,
    SkillDps,
    SkillGroup,
)
from poe1_builds.service import DEFAULT_ASCENDANCIES, BuildsService
from poe1_builds.sources.ninja import NinjaBuildsSource, NinjaBuildsSourceError

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_ASCENDANCIES",
    "BuildFilter",
    "BuildSortKey",
    "BuildStatus",
    "BuildsService",
    "BuildsSnapshot",
    "DefenseType",
    "DefensiveStats",
    "FullBuild",
    "GemRef",
    "ItemEntry",
    "ItemProvidedGemGroup",
    "KeystonePassive",
    "MasteryChoice",
    "NinjaBuildsSource",
    "NinjaBuildsSourceError",
    "RemoteBuildRef",
    "SkillDps",
    "SkillGroup",
    "__version__",
]
