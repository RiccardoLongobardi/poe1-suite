"""Integration tests for the /pricing router mounted on the server.

We reuse the same poe.ninja fixture set that lives in the pricing
package's tests and serve it through an ``httpx.MockTransport`` that is
swapped into :class:`HttpClient` on ``__aenter__``. This exercises the
full request → service → source → parse → response path with real
upstream payloads but no network.
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
    Path(__file__).parent.parent.parent.parent / "packages" / "pricing" / "tests" / "fixtures"
)


def _load(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _ninja_handler(request: httpx.Request) -> httpx.Response:
    """Serve poe.ninja fixture files based on the request path."""

    path = request.url.path
    params = request.url.params

    if path.endswith("/data/index-state"):
        return httpx.Response(200, json=_load("index_state.json"))

    if "/economy/stash/" in path and path.endswith("/overview"):
        type_ = params.get("type", "")
        league = params.get("league", "")
        if not type_ or not league:
            return httpx.Response(400, json={"title": "validation error"})
        fixture_name = f"ninja_{type_}.json"
        fixture_path = FIXTURE_DIR / fixture_name
        if not fixture_path.exists():
            return httpx.Response(200, json={"lines": []})
        return httpx.Response(200, json=_load(fixture_name))

    return httpx.Response(404, text=f"no mock for {path}")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Mirage is what the captured fixtures are for; disable HTTP cache so
    # state can't leak between tests.
    return Settings(
        cache_dir=tmp_path / "cache",
        http_cache_ttl_seconds=0,
        poe_league="Mirage",
    )


@pytest.fixture
def patched_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Swap the real httpx client for a MockTransport-backed one.

    We wrap :meth:`HttpClient.__aenter__` so that *every* per-request
    ``async with HttpClient(...)`` inside the router gets the mock.
    """

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


def test_version_includes_pricing(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        v = client.get("/version").json()
        assert "pricing" in v


def test_quote_divine_orb(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/pricing/quote", params={"name": "Divine Orb"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["league"] == "Mirage"
        assert body["quote"] is not None
        assert body["quote"]["name"] == "Divine Orb"
        assert body["quote"]["category"] == "Currency"
        assert body["quote"]["chaos_value"] > 0


def test_quote_case_insensitive_cross_category(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/pricing/quote", params={"name": "mirror of kalandra"})
        assert r.status_code == 200, r.text
        q = r.json()["quote"]
        assert q is not None
        assert q["name"] == "Mirror of Kalandra"


def test_quote_miss_returns_null(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/pricing/quote", params={"name": "Totally Made Up Item"})
        assert r.status_code == 200, r.text
        assert r.json()["quote"] is None


def test_quote_restricted_to_category(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/pricing/quote",
            params={"name": "Divine Orb", "category": "Currency"},
        )
        assert r.status_code == 200, r.text
        q = r.json()["quote"]
        assert q is not None
        assert q["category"] == "Currency"


def test_quote_unknown_league_is_404(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/pricing/quote",
            params={"name": "Divine Orb", "league": "BogusLeague"},
        )
        assert r.status_code == 404
        assert "bogusleague" in r.json()["detail"].lower()


def test_snapshot_currency(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/pricing/snapshot", params={"category": "Currency"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["league"] == "Mirage"
        assert body["category"] == "Currency"
        assert body["count"] == 74  # matches the saved fixture
        assert len(body["quotes"]) == body["count"]


def test_snapshot_cluster_jewel_has_variant(patched_http: None, settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/pricing/snapshot", params={"category": "ClusterJewel"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["category"] == "ClusterJewel"
        assert body["count"] > 0
        first = body["quotes"][0]
        assert first["variant"] is not None
        assert "passives" in first["variant"]


def test_snapshot_invalid_category_is_422(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get("/pricing/snapshot", params={"category": "NotAThing"})
        assert r.status_code == 422
