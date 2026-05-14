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
        health = client.get("/health").json()
        # Production hardening (Fase 1): /health is enriched with env,
        # league, version, uptime so monitors can probe meaningful state.
        assert health["status"] == "ok"
        assert health["environment"] == "development"
        assert health["league"] == settings.poe_league
        assert "version" in health
        assert health["uptime_seconds"] >= 0
        assert "timestamp" in health

        v = client.get("/version").json()
        assert "fob" in v


def test_cors_disabled_when_origins_empty(settings: Settings) -> None:
    """No CORS middleware when ``cors_allowed_origins`` is empty.

    Dev frontend uses Vite proxy so cross-origin headers aren't needed.
    Empty list = mw not mounted = no Access-Control-Allow-Origin in
    OPTIONS response.
    """

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.options(
            "/health",
            headers={"Origin": "https://malicious.example"},
        )
        assert "access-control-allow-origin" not in {k.lower() for k in r.headers}


def test_cors_enabled_when_origins_configured(tmp_path: Path) -> None:
    """CORS middleware is mounted and reflects the configured origins."""

    settings = Settings(
        cache_dir=tmp_path / "cache",
        http_cache_ttl_seconds=0,
        cors_allowed_origins=["https://fob.vercel.app"],
    )
    app = create_app(settings)
    with TestClient(app) as client:
        r = client.options(
            "/health",
            headers={
                "Origin": "https://fob.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.headers.get("access-control-allow-origin") == "https://fob.vercel.app"


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


# ---------------------------------------------------------------------------
# Stage export — GET (no-fallback) + POST (with user_pob_code fallback)
# ---------------------------------------------------------------------------


def test_stage_export_get_rf_pohx_returns_progression_code(settings: Settings) -> None:
    """GET /fob/stage-export with a real progression returns tree_source='progression'."""

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/fob/stage-export/rf_pohx/early_campaign",
            params={"character_class": "Marauder", "ascendancy": "Juggernaut"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["template_name"] == "rf_pohx"
        assert body["stage_key"] == "early_campaign"
        assert body["tree_source"] == "progression"
        assert body["code"] is not None
        assert len(body["code"]) > 100


def test_stage_export_get_unknown_template_returns_empty_tree(settings: Settings) -> None:
    """GET endpoint falls back to empty tree when no progression registered.

    Previously returned {"code": null} which made the import button
    unusable for 47/49 templates. Now always emits a valid code so PoB
    can still import it.
    """

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.get(
            "/fob/stage-export/vortex_occultist/early_campaign",
            params={"character_class": "Witch", "ascendancy": "Occultist"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tree_source"] == "empty"
        assert body["code"] is not None


def test_stage_export_post_with_user_pob_uses_dynamic_synthesis(
    settings: Settings,
) -> None:
    """POST with user_pob_code → Step 16 dynamic synthesis takes precedence.

    Previously this expected ``tree_source='user_pob'`` (the
    pass-through-verbatim fallback). After Step 16, the dynamic
    BFS-bucketed progression wins because it derives a per-stage
    plan from the same source PoB instead of just echoing it.
    """

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/stage-export",
            json={
                "template_name": "vortex_occultist",  # no curated progression
                "stage_key": "early_campaign",
                "character_class": "Marauder",
                "ascendancy": "Chieftain",
                "level": 90,
                "user_pob_code": REAL_POB,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tree_source"] == "dynamic"
        assert body["code"] is not None


def test_stage_export_post_without_user_pob_returns_empty_tree(
    settings: Settings,
) -> None:
    """POST without user_pob_code + no progression → tree_source='empty'."""

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/stage-export",
            json={
                "template_name": "vortex_occultist",
                "stage_key": "early_campaign",
                "character_class": "Witch",
                "ascendancy": "Occultist",
                "level": 90,
                "user_pob_code": None,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tree_source"] == "empty"
        assert body["code"] is not None


def test_stage_export_post_dynamic_wins_even_for_curated_template(
    settings: Settings,
) -> None:
    """Step 16 priority: dynamic > curated registry when a PoB is provided.

    Previously the curated rf_pohx registry won here. After Step 16
    the dynamic engine derives the tree from the user's actual PoB
    even when a curated template exists — the curated registry now
    serves only as the fallback for builds with no PoB.
    """

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/stage-export",
            json={
                "template_name": "rf_pohx",
                "stage_key": "end_mapping",
                "character_class": "Marauder",
                "ascendancy": "Juggernaut",
                "level": 90,
                "user_pob_code": REAL_POB,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tree_source"] == "dynamic"


def test_stage_export_post_curated_progression_used_without_pob(
    settings: Settings,
) -> None:
    """Without a user_pob_code, the curated rf_pohx registry kicks in."""

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/stage-export",
            json={
                "template_name": "rf_pohx",
                "stage_key": "end_mapping",
                "character_class": "Marauder",
                "ascendancy": "Juggernaut",
                "level": 90,
                "user_pob_code": None,
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tree_source"] == "progression"


def test_stage_export_post_garbage_user_pob_falls_back_to_empty(
    settings: Settings,
) -> None:
    """Invalid user_pob_code → graceful fallback to empty tree (no 500)."""

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/stage-export",
            json={
                "template_name": "vortex_occultist",
                "stage_key": "early_campaign",
                "character_class": "Witch",
                "ascendancy": "Occultist",
                "level": 90,
                "user_pob_code": "@@@not-a-real-pob-code@@@",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["tree_source"] == "empty"
        assert body["code"] is not None


# ---------------------------------------------------------------------------
# Trade URL — POST /fob/trade-url (cached GGG search-id resolver)
# ---------------------------------------------------------------------------


def test_trade_url_requires_name_or_type(settings: Settings) -> None:
    """Empty payload (no name and no type) → 422."""

    app = create_app(settings)
    with TestClient(app) as client:
        r = client.post(
            "/fob/trade-url",
            json={"item_name": None, "item_type": None, "mod_lines": []},
        )
        assert r.status_code == 422
        assert "requires" in r.json()["detail"].lower()


def test_trade_url_returns_cached_url_on_second_call(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """First call hits GGG (mocked), second call hits the in-memory cache.

    Asserts ``source='fresh'`` then ``source='cache'`` on identical
    payloads — proving the cache prevents repeat GGG hits on the same
    item name.
    """

    # Reset the module-level cache so previous tests don't leak in.
    from poe1_fob.router import _trade_url_cache

    _trade_url_cache.clear()

    call_count = {"n": 0}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "/api/trade/search/" in str(request.url):
            call_count["n"] += 1
            return httpx.Response(
                200,
                json={"id": "abc123def456", "complexity": 1, "total": 42, "result": []},
            )
        return httpx.Response(404)

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
        payload: dict[str, object] = {
            "item_name": "Mageblood",
            "item_type": None,
            "mod_lines": [],
        }

        # First call: fresh
        r1 = client.post("/fob/trade-url", json=payload)
        assert r1.status_code == 200, r1.text
        b1 = r1.json()
        assert b1["source"] == "fresh"
        assert "abc123def456" in b1["url"]
        assert call_count["n"] == 1

        # Second call: cache hit, no extra GGG call
        r2 = client.post("/fob/trade-url", json=payload)
        assert r2.status_code == 200, r2.text
        b2 = r2.json()
        assert b2["source"] == "cache"
        assert b2["url"] == b1["url"]
        assert call_count["n"] == 1, "Second call must not hit GGG"


def test_trade_url_returns_rate_limited_on_429(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """GGG 429 → source='rate_limited' (frontend handles fallback)."""

    from poe1_fob.router import _trade_url_cache

    _trade_url_cache.clear()

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if "/api/trade/search/" in str(request.url):
            return httpx.Response(
                429,
                headers={"X-Rate-Limit-Ip": "5:60:60", "Retry-After": "60"},
                json={"error": "rate limited"},
            )
        return httpx.Response(404)

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
        r = client.post(
            "/fob/trade-url",
            json={"item_name": "Rate Limited Item", "item_type": None, "mod_lines": []},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["source"] == "rate_limited"
        assert body["url"] is None
