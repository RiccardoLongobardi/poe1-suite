"""Integration tests for the /fob router mounted on the server."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from poe1_server.main import create_app
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "packages"
    / "fob"
    / "tests"
    / "fixtures"
    / "pob_YNQeadFwNBmX.txt"
)
REAL_POB = FIXTURE.read_text().strip()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # http_cache_ttl_seconds=0 prevents cross-test cache contamination.
    return Settings(cache_dir=tmp_path / "cache", http_cache_ttl_seconds=0)


def test_health_and_version_endpoints(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        v = client.get("/version").json()
        assert "fob" in v


def test_analyze_pob_rejects_missing_input(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        # Empty body -> pydantic rejects with 422.
        r = client.post("/fob/analyze-pob", json={"input": ""})
        assert r.status_code == 422


def test_analyze_pob_rejects_garbage_input(settings: Settings) -> None:
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post("/fob/analyze-pob", json={"input": "not a PoB"})
        assert r.status_code == 400
        assert "not recognised" in r.json()["detail"].lower()


def test_analyze_pob_with_raw_code(settings: Settings) -> None:
    """Happy path: raw code in, Build + snapshot out."""

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post("/fob/analyze-pob", json={"input": REAL_POB})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "build" in body
        assert "snapshot" in body
        b = body["build"]
        assert b["character_class"] == "marauder"
        assert b["ascendancy"] == "chieftain"
        assert b["main_skill"] == "Raise Spectre"
        assert b["source_type"] == "pob"
        # Same code twice must produce the same source_id.
        r2 = client.post("/fob/analyze-pob", json={"input": REAL_POB})
        assert r2.json()["build"]["source_id"] == b["source_id"]


def test_analyze_pob_with_pobb_in_url(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    """URL path: ingest fetches the /raw endpoint through our HTTP client."""

    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Only serve the raw endpoint for this share id.
        if str(request.url) == "https://pobb.in/YNQeadFwNBmX/raw":
            return httpx.Response(200, text=REAL_POB)
        return httpx.Response(404)

    original_aenter = HttpClient.__aenter__

    async def patched_aenter(self: HttpClient) -> HttpClient:
        client = await original_aenter(self)
        # Replace the real httpx client with one backed by our mock.
        await self._client.aclose()  # type: ignore[union-attr]
        self._client = httpx.AsyncClient(
            transport=httpx.MockTransport(mock_handler),
            timeout=self._settings.http_timeout_seconds,
            headers={"User-Agent": self._settings.user_agent},
            follow_redirects=True,
        )
        return client

    monkeypatch.setattr(HttpClient, "__aenter__", patched_aenter)

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/analyze-pob",
            json={"input": "https://pobb.in/YNQeadFwNBmX"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["build"]["origin_url"] == "https://pobb.in/YNQeadFwNBmX"
        assert body["snapshot"]["origin_url"] == "https://pobb.in/YNQeadFwNBmX"
