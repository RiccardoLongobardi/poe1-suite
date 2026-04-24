"""Shared test plumbing for poe1-builds.

Goal: drive the full ``NinjaBuildsSource`` / ``BuildsService`` pipeline
without touching the network but with realistic payloads. The
fixtures in ``tests/fixtures/`` were captured from the live Mirage
league on 2026-04-24 and are replayed via :class:`httpx.MockTransport`.

The builds API has two body types the pricing pipeline doesn't:

* Protobuf (``application/x-protobuf``) for ``/builds/{v}/search``.
* Large JSON for ``/builds/{v}/character``.

Both are served here off disk.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio

from poe1_builds import BuildsService, NinjaBuildsSource
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load_json(name: str) -> dict[str, Any]:
    with (FIXTURE_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _load_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def _ninja_builds_handler(request: httpx.Request) -> httpx.Response:
    """httpx MockTransport handler that serves fixtures as poe.ninja builds."""

    path = request.url.path
    params = request.url.params

    # /poe1/api/data/index-state
    if path.endswith("/data/index-state"):
        return httpx.Response(200, json=_load_json("index_state.json"))

    # /poe1/api/builds/{version}/search
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
                # Default to all.pb — many ascendancies share the same shape.
                fixture = FIXTURE_DIR / "search_mirage_all.pb"
            body = fixture.read_bytes()
        else:
            body = _load_bytes("search_mirage_all.pb")
        return httpx.Response(
            200,
            content=body,
            headers={"content-type": "application/x-protobuf"},
        )

    # /poe1/api/builds/{version}/character
    if "/builds/" in path and path.endswith("/character"):
        account = params.get("account", "")
        name = params.get("name", "")
        if account == "Brainwar-1546" and name == "Brain\u318d":
            return httpx.Response(200, json=_load_json("character_brainwar_brain.json"))
        return httpx.Response(
            404,
            json={"error": f"no fixture for account={account!r} name={name!r}"},
        )

    return httpx.Response(404, text=f"no mock for {path}")


@pytest.fixture
def ninja_builds_transport() -> httpx.MockTransport:
    return httpx.MockTransport(_ninja_builds_handler)


@pytest_asyncio.fixture
async def http_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ninja_builds_transport: httpx.MockTransport,
) -> AsyncIterator[HttpClient]:
    """Real :class:`HttpClient` wired to the MockTransport.

    Per-test ``tmp_path`` cache dir prevents disk cache leakage.
    """

    settings = Settings(cache_dir=tmp_path / ".cache_http", http_cache_ttl_seconds=0)
    original_enter = HttpClient.__aenter__

    async def patched_enter(self: HttpClient) -> HttpClient:
        result = await original_enter(self)
        await result._client.aclose()  # type: ignore[union-attr]
        result._client = httpx.AsyncClient(
            transport=ninja_builds_transport,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
        return result

    monkeypatch.setattr(HttpClient, "__aenter__", patched_enter)

    async with HttpClient(settings) as client:
        yield client


@pytest_asyncio.fixture
async def ninja_source(http_client: HttpClient) -> NinjaBuildsSource:
    return NinjaBuildsSource(http_client, league="Mirage")


@pytest_asyncio.fixture
async def builds_service(http_client: HttpClient) -> BuildsService:
    # Shrink ascendancies to the five we have per-class fixtures for so
    # multi-class fan-out tests are deterministic and fast.
    return BuildsService(
        http=http_client,
        league="Mirage",
        ascendancies=("Slayer", "Deadeye", "Chieftain", "Necromancer", "Hierophant"),
    )
