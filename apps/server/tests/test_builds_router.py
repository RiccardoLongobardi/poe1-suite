"""Integration tests for the /builds router mounted on the server.

Mirrors the pricing router test pattern: we reuse the fixture set from
``packages/builds/tests/fixtures/`` (captured from live Mirage on
2026-04-24) and swap in an ``httpx.MockTransport`` on
:meth:`HttpClient.__aenter__` so the full request → service → source
path is exercised with zero network I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from poe1_server.main import create_app
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

FIXTURE_DIR = (
    Path(__file__).parent.parent.parent.parent / "packages" / "builds" / "tests" / "fixtures"
)


def _load_json(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _load_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def _ninja_handler(request: httpx.Request) -> httpx.Response:
    """Serve poe.ninja builds fixtures based on the request path."""

    path = request.url.path
    params = request.url.params

    if path.endswith("/data/index-state"):
        return httpx.Response(200, json=_load_json("index_state.json"))

    if "/builds/" in path and path.endswith("/search"):
        overview = params.get("overview", "")
        klass = params.get("class")
        if overview != "mirage":
            return httpx.Response(
                400, json={"error": f"mock only serves mirage (got {overview!r})"}
            )
        if klass:
            fixture = FIXTURE_DIR / f"search_mirage_{klass}.pb"
            if not fixture.exists():
                fixture = FIXTURE_DIR / "search_mirage_all.pb"
            body = fixture.read_bytes()
        else:
            body = _load_bytes("search_mirage_all.pb")
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "application/x-protobuf"},
        )

    if "/builds/" in path and path.endswith("/character"):
        account = params.get("account", "")
        name = params.get("name", "")
        if account == "Brainwar-1546" and name == "Brain\u318d":
            return httpx.Response(200, json=_load_json("character_brainwar_brain.json"))
        return httpx.Response(404, json={"error": "no fixture"})

    return httpx.Response(404, text=f"no mock for {path}")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        cache_dir=tmp_path / "cache",
        http_cache_ttl_seconds=0,
        poe_league="Mirage",
    )


@pytest.fixture
def patched_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the real httpx client for a MockTransport-backed one."""

    original_aenter = HttpClient.__aenter__

    async def patched_aenter(self: HttpClient) -> HttpClient:
        client = await original_aenter(self)
        await self._client.aclose()  # type: ignore[union-attr]
        self._client = httpx.AsyncClient(
            transport=httpx.MockTransport(_ninja_handler),
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": self._settings.user_agent},
            follow_redirects=True,
        )
        return client

    monkeypatch.setattr(HttpClient, "__aenter__", patched_aenter)


# ---------------------------------------------------------------------------
# /version
# ---------------------------------------------------------------------------


def test_version_includes_builds(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        v = client.get("/version").json()
        assert "builds" in v
        assert v["builds"]  # version string is non-empty


# ---------------------------------------------------------------------------
# /builds/list
# ---------------------------------------------------------------------------


def test_list_per_class(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/builds/list", params={"class": "Slayer"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["league"] == "Mirage"
        assert body["count"] == 100
        assert body["total"] >= 100
        assert body["snapshot_version"]
        first = body["refs"][0]
        # The Pydantic model is frozen with class_name aliased to
        # "class"; model_dump(by_alias=True) surfaces the alias.
        assert first["class"] == "Slayer"
        assert 1 <= first["level"] <= 100
        assert first["account"]
        assert first["character"]


def test_list_top_n_cap(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/builds/list", params={"class": "Deadeye", "top_n_per_class": 10})
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 10


def test_list_level_range(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/builds/list",
            params={"class": "Chieftain", "level_min": 97, "level_max": 100},
        )
        assert r.status_code == 200, r.text
        refs = r.json()["refs"]
        assert all(97 <= ref["level"] <= 100 for ref in refs)


def test_list_level_range_requires_both(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/builds/list", params={"level_min": 95})
        assert r.status_code == 422
        assert "together" in r.json()["detail"]


def test_list_level_range_inverted_rejected(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/builds/list", params={"level_min": 95, "level_max": 85})
        assert r.status_code == 422


def test_list_unknown_league_is_404(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/builds/list", params={"league": "NotARealLeague"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# /builds/detail
# ---------------------------------------------------------------------------


def test_detail_for_known_character(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/builds/detail",
            params={"account": "Brainwar-1546", "name": "Brain\u318d"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["league"] == "Mirage"
        build = body["build"]
        assert build["account"] == "Brainwar-1546"
        assert build["name"] == "Brain\u318d"
        # Bookkeeping fields injected by the adapter (no alias → snake_case).
        assert build["source_id"]
        assert build["snapshot_version"]
        # PoB export is present for downstream FOB usage — the field has
        # a camelCase alias so it surfaces as ``pathOfBuildingExport`` in
        # the serialized JSON.
        assert build["pathOfBuildingExport"]


def test_detail_missing_name_is_422(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/builds/detail", params={"account": "Someone-1"})
        assert r.status_code == 422


def test_detail_unknown_character_is_upstream_error(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/builds/detail",
            params={"account": "Ghost-0", "name": "NotARealChar"},
        )
        # The MockTransport returns 404 for unknown characters; the
        # router maps that to a 404 (or 502 if the text parsing differs).
        assert r.status_code in (404, 502)
