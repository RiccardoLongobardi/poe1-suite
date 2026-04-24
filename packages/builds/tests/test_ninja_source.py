"""Tests for :mod:`poe1_builds.sources.ninja`.

These exercise the adapter end-to-end against the httpx MockTransport
wired in ``conftest.py``. The fixtures were captured from the live
Mirage league on 2026-04-24 so the protobuf decoding path and the
index-state resolution are both covered with real payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from poe1_builds import BuildFilter, FullBuild, RemoteBuildRef
from poe1_builds.generated import ninja_builds_pb2 as pb
from poe1_builds.sources.ninja import (
    NinjaBuildsSource,
    NinjaBuildsSourceError,
    _BuildsIndex,
    _decode_refs,
    _parse_shortnum,
)
from poe1_shared.http import HttpClient

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# _parse_shortnum
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", 0),
        ("0", 0),
        ("123", 123),
        ("119k", 119_000),
        ("2.9M", 2_900_000),
        ("76M", 76_000_000),
        ("> 10M", 10_000_000),
        ("< 5k", 5_000),
        ("1.5B", 1_500_000_000),
        ("650k", 650_000),
        ("garbage", 0),
        ("1.2.3k", 0),
    ],
)
def test_parse_shortnum(raw: str, expected: int) -> None:
    assert _parse_shortnum(raw) == expected


# ---------------------------------------------------------------------------
# _BuildsIndex resolution
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def index() -> _BuildsIndex:
    raw: dict[str, Any] = json.loads((FIXTURES / "index_state.json").read_text(encoding="utf-8"))
    return _BuildsIndex.model_validate(raw)


def test_index_resolve_by_display_name(index: _BuildsIndex) -> None:
    assert index.resolve_league_url("Mirage") == "mirage"


def test_index_resolve_by_slug(index: _BuildsIndex) -> None:
    assert index.resolve_league_url("mirage") == "mirage"


def test_index_resolve_case_insensitive(index: _BuildsIndex) -> None:
    assert index.resolve_league_url("MIRAGE") == "mirage"
    assert index.resolve_league_url("miRAGE") == "mirage"


def test_index_resolve_ssf_variant(index: _BuildsIndex) -> None:
    # "SSF Mirage" resolves to its own slug, separate from Mirage.
    assert index.resolve_league_url("SSF Mirage") == "miragessf"


def test_index_resolve_standard(index: _BuildsIndex) -> None:
    assert index.resolve_league_url("Standard") == "standard"


def test_index_resolve_unknown_returns_none(index: _BuildsIndex) -> None:
    assert index.resolve_league_url("NotARealLeague-1234") is None


def test_index_version_for_mirage_exp(index: _BuildsIndex) -> None:
    snap = index.version_for("mirage", type_="exp")
    assert snap is not None
    assert snap.url == "mirage"
    assert snap.type == "exp"
    assert snap.version  # non-empty opaque token


def test_index_version_for_unknown_type_is_none(index: _BuildsIndex) -> None:
    assert index.version_for("mirage", type_="nonexistent") is None


def test_index_version_for_unknown_league_is_none(index: _BuildsIndex) -> None:
    assert index.version_for("absolutely-not-a-league", type_="exp") is None


# ---------------------------------------------------------------------------
# _decode_refs against real fixtures
# ---------------------------------------------------------------------------


def _load_search(name: str) -> Any:
    body = (FIXTURES / name).read_bytes()
    result: Any = pb.NinjaSearchResult()  # type: ignore[attr-defined]
    result.ParseFromString(body)
    return result.result


@pytest.mark.parametrize(
    "klass",
    ["Slayer", "Deadeye", "Chieftain", "Necromancer", "Hierophant"],
)
def test_decode_refs_per_class_fixture(klass: str) -> None:
    from datetime import UTC, datetime

    search = _load_search(f"search_mirage_{klass}.pb")
    refs = _decode_refs(
        search,
        league_url="mirage",
        league_name="Mirage",
        class_filter=klass,
        snapshot_version="0606-20260424-28035",
        fetched_at=datetime(2026, 4, 24, tzinfo=UTC),
    )
    assert len(refs) == 100, f"{klass} fixture should have 100 refs"
    assert all(r.class_name == klass for r in refs)
    assert all(1 <= r.level <= 100 for r in refs)
    assert all(r.account for r in refs)
    assert all(r.character for r in refs)
    assert all(r.source_id.startswith("ninja::mirage::") for r in refs)
    # ehp and dps are both short-form strings in the payload; at least
    # some rows should decode to non-zero.
    assert any(r.ehp > 0 for r in refs)
    assert any(r.dps > 0 for r in refs)


def test_decode_refs_no_class_leaves_class_blank() -> None:
    from datetime import UTC, datetime

    search = _load_search("search_mirage_all.pb")
    refs = _decode_refs(
        search,
        league_url="mirage",
        league_name="Mirage",
        class_filter=None,
        snapshot_version="0606-20260424-28035",
        fetched_at=datetime(2026, 4, 24, tzinfo=UTC),
    )
    assert len(refs) > 0
    # Without a class filter we can't resolve the column - left blank.
    assert all(r.class_name == "" for r in refs)


# ---------------------------------------------------------------------------
# NinjaBuildsSource — full adapter path
# ---------------------------------------------------------------------------


async def test_fetch_snapshot_per_class(ninja_source: NinjaBuildsSource) -> None:
    snap = await ninja_source.fetch_snapshot(BuildFilter(class_="Slayer"))
    assert snap.league == "Mirage"
    assert snap.snapshot_version  # propagated from index
    assert snap.total >= 100
    assert len(snap.refs) == 100
    assert all(r.class_name == "Slayer" for r in snap.refs)


async def test_fetch_snapshot_no_filter_uses_all_fixture(
    ninja_source: NinjaBuildsSource,
) -> None:
    snap = await ninja_source.fetch_snapshot(BuildFilter())
    assert snap.league == "Mirage"
    assert len(snap.refs) >= 1
    # No class filter → class_name left blank on each row.
    assert all(r.class_name == "" for r in snap.refs)


async def test_fetch_snapshot_top_n_cap(ninja_source: NinjaBuildsSource) -> None:
    snap = await ninja_source.fetch_snapshot(BuildFilter(class_="Deadeye", top_n_per_class=25))
    assert len(snap.refs) == 25


async def test_fetch_snapshot_level_range_filter(
    ninja_source: NinjaBuildsSource,
) -> None:
    snap = await ninja_source.fetch_snapshot(BuildFilter(class_="Chieftain", level_range=(95, 100)))
    assert all(95 <= r.level <= 100 for r in snap.refs)


async def test_fetch_snapshot_default_filter(ninja_source: NinjaBuildsSource) -> None:
    # Passing ``None`` should fall back to BuildFilter() internally.
    snap = await ninja_source.fetch_snapshot(None)
    assert snap.league == "Mirage"
    assert len(snap.refs) >= 1


async def test_league_api_name_resolves_after_fetch(
    ninja_source: NinjaBuildsSource,
) -> None:
    # Before any fetch, falls back to the label the source was built with.
    assert ninja_source.league_api_name == "Mirage"
    await ninja_source.fetch_snapshot(BuildFilter(class_="Slayer"))
    # After fetch → canonical display name from buildLeagues.
    assert ninja_source.league_api_name == "Mirage"


# ---------------------------------------------------------------------------
# NinjaBuildsSource — error cases
# ---------------------------------------------------------------------------


async def test_unknown_league_raises(http_client: HttpClient) -> None:
    src = NinjaBuildsSource(http_client, league="DefinitelyNotALeague-9999")
    with pytest.raises(NinjaBuildsSourceError):
        await src.refresh_index()


async def test_unknown_league_on_fetch_raises(http_client: HttpClient) -> None:
    src = NinjaBuildsSource(http_client, league="NopeNotReal")
    with pytest.raises(NinjaBuildsSourceError):
        await src.fetch_snapshot(BuildFilter(class_="Slayer"))


# ---------------------------------------------------------------------------
# NinjaBuildsSource.fetch_build_detail
# ---------------------------------------------------------------------------


async def test_fetch_build_detail(ninja_source: NinjaBuildsSource) -> None:
    # Build a ref pointing at the character fixture: account=Brainwar-1546,
    # name=Brain\u318d. The MockTransport serves the captured JSON.
    from datetime import UTC, datetime

    # First trigger index resolution so league_name matches what the
    # adapter injects into the payload.
    await ninja_source.fetch_snapshot(BuildFilter(class_="Chieftain"))

    ref = RemoteBuildRef.model_validate(
        {
            "source_id": "ninja::mirage::Brainwar-1546::Brain\u318d",
            "account": "Brainwar-1546",
            "character": "Brain\u318d",
            "class": "Chieftain",
            "level": 100,
            "life": 5433,
            "energy_shield": 109,
            "ehp": 180_000,
            "dps": 1_200_000,
            "main_skill": None,
            "league": "Mirage",
            "snapshot_version": "0606-20260424-28035",
            "fetched_at": datetime(2026, 4, 24, tzinfo=UTC),
        }
    )
    build = await ninja_source.fetch_build_detail(ref)
    assert isinstance(build, FullBuild)
    assert build.account == "Brainwar-1546"
    assert build.name == "Brain\u318d"
    assert build.league == "Mirage"
    # Bookkeeping fields injected by the adapter.
    assert build.source_id == ref.source_id
    assert build.snapshot_version  # non-empty
    assert build.fetched_at  # non-empty
    assert build.path_of_building_export  # non-empty
    assert len(build.skills) > 0
    assert len(build.items) > 0


async def test_fetch_build_detail_404_propagates(
    ninja_source: NinjaBuildsSource,
) -> None:
    from datetime import UTC, datetime

    from poe1_shared.http import HttpError

    await ninja_source.fetch_snapshot(BuildFilter(class_="Chieftain"))

    # An account/name combo that the MockTransport will respond 404 for.
    ref = RemoteBuildRef.model_validate(
        {
            "source_id": "ninja::mirage::nobody#0::Ghost",
            "account": "nobody#0",
            "character": "Ghost",
            "class": "Chieftain",
            "level": 1,
            "life": 0,
            "energy_shield": 0,
            "ehp": 0,
            "dps": 0,
            "main_skill": None,
            "league": "Mirage",
            "snapshot_version": "0606-20260424-28035",
            "fetched_at": datetime(2026, 4, 24, tzinfo=UTC),
        }
    )
    with pytest.raises((HttpError, httpx.HTTPStatusError, Exception)):
        await ninja_source.fetch_build_detail(ref)
