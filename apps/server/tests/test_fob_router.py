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


def test_plan_reverse_endpoint_is_registered(settings: Settings) -> None:
    """Step 13.C: smoke test that POST /fob/plan/reverse is wired up.

    Doesn't run pricing (poe.ninja calls are not mocked here), just
    checks the route exists and validates input shape. Empty body
    returns 422 (Pydantic rejection), same as /fob/plan.
    """

    app = create_app(settings)
    with TestClient(app) as client:
        # Empty body → 422 from PlanRequest validation.
        r = client.post("/fob/plan/reverse", json={"input": ""})
        assert r.status_code == 422

        # Garbage input → 400 (same dispatch as /fob/plan).
        r = client.post("/fob/plan/reverse", json={"input": "not a PoB"})
        assert r.status_code == 400
        assert "not recognised" in r.json()["detail"].lower()


def test_plan_reverse_e2e_with_real_pob(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """Step 13.C E2E: real PoB → reverse-mode plan with mocked HTTP.

    All outbound HTTP (poe.ninja stash, Trade API) is mocked to 404 so
    the planner produces an unpriced plan. The build still flows
    through the reverse-progression engine, and any KeyItem in the
    table surfaces ladder rationales tagged ``[target_name]`` in the
    corresponding stage's gem_changes.

    Asserts:
    - 200 response with a 6-stage plan
    - At least one stage carries a ``[X]`` ladder line OR plan is
      well-formed even with no recognised KeyItems (graceful fallback).
    """

    # Minimal index-state payload so PricingService.refresh_index() can
    # resolve "Standard" to a slug. Anything else returns 404 → the
    # planner treats as "no listing" and produces unpriced CoreItems.
    INDEX_STATE_STUB = {
        "economyLeagues": [
            {"name": "Standard", "url": "standard", "displayName": "Standard"},
        ],
        "oldEconomyLeagues": [],
        "snapshotVersions": [
            {
                "url": "standard",
                "type": "exp",
                "name": "Standard",
                "version": "v1",
                "snapshotName": "Standard",
                "overviewType": 1,
            },
        ],
    }

    def mock_handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/data/index-state"):
            return httpx.Response(200, json=INDEX_STATE_STUB)
        # Currency / item overviews → empty list. The pricing service
        # treats this as "no quotes" and returns None, which the planner
        # absorbs into unpriced CoreItems + heuristic divine rate.
        if "/economy/stash/" in path and "/overview" in path:
            return httpx.Response(200, json={"lines": []})
        # Trade API search/fetch → empty result. quote_trade_range
        # treats this as "no listings".
        if "/api/trade/search/" in path or "/api/trade/fetch/" in path:
            return httpx.Response(200, json={"id": "stub", "result": []})
        return httpx.Response(404, text="")

    original_aenter = HttpClient.__aenter__

    async def patched_aenter(self: HttpClient) -> HttpClient:
        client = await original_aenter(self)
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
        r = client.post("/fob/plan/reverse", json={"input": REAL_POB})
        assert r.status_code == 200, r.text
        body = r.json()

        # Plan shape: 6 stages, each with the standard fields.
        plan = body["plan"]
        assert len(plan["stages"]) == 6
        for stage in plan["stages"]:
            assert "label" in stage
            assert "core_items" in stage
            assert "gem_changes" in stage
            assert "tree_changes" in stage

        # Build still serialised correctly.
        build = body["build"]
        assert build["character_class"] == "marauder"
        assert build["main_skill"] == "Raise Spectre"

        # The fixture is a Spectre Necro Chieftain build. None of the
        # KeyItems happen to be in the reverse ladder table (it's a
        # mid-budget setup), so we expect no ``[X]`` ladder tags. Either
        # is fine — the test is about *the endpoint not crashing* and
        # producing a coherent plan, not about ladder coverage of this
        # specific fixture.
        # If any KeyItem matches the table, it would surface as
        # gem_changes entries starting with "[".
        all_gem_lines = [line for s in plan["stages"] for line in s["gem_changes"]]
        # Sanity: at least the GenericTemplate / RfPohx / matching
        # template should produce *some* gem advice for a real build.
        assert len(all_gem_lines) > 0
