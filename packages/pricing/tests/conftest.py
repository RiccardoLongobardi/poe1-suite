"""Shared test plumbing for poe1-pricing.

Goal: let tests drive the full ``NinjaSource`` / ``PricingService``
pipeline without touching the network, but *with* realistic payloads.
The fixtures in ``tests/fixtures/`` are actual poe.ninja responses
captured from the live Mirage league on 2026-04-23; we feed them back
through an :class:`httpx.MockTransport` so our parser is exercised
against real-world shape variability (missing fields, mutated mods,
low-confidence sparklines, etc).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio

from poe1_pricing import NinjaSource, PricingService
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any]:
    """Read a fixture JSON by filename (``index_state.json``, ``ninja_Currency.json`` …)."""

    with (FIXTURE_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)  # type: ignore[no-any-return]


def _fixture_category_name(type_param: str) -> str:
    """Map the ``type=`` query value to the on-disk fixture filename."""

    return f"ninja_{type_param}.json"


def _ninja_handler(request: httpx.Request) -> httpx.Response:
    """httpx MockTransport handler that serves fixtures as poe.ninja."""

    path = request.url.path
    params = request.url.params

    if path.endswith("/data/index-state"):
        return httpx.Response(200, json=_load("index_state.json"))

    # /economy/stash/{version}/{currency|item}/overview
    if "/economy/stash/" in path and path.endswith("/overview"):
        type_ = params.get("type", "")
        league = params.get("league", "")
        if not type_ or not league:
            return httpx.Response(
                400,
                json={
                    "title": "validation error",
                    "errors": {
                        "type": ["required"] if not type_ else [],
                        "league": ["required"] if not league else [],
                    },
                },
            )
        fixture_name = _fixture_category_name(type_)
        fixture_path = FIXTURE_DIR / fixture_name
        if not fixture_path.exists():
            # Return empty-shaped payload for categories without a fixture.
            return httpx.Response(200, json={"lines": []})
        return httpx.Response(200, json=_load(fixture_name))

    return httpx.Response(404, text=f"no mock for {path}")


@pytest.fixture()
def ninja_transport() -> httpx.MockTransport:
    """httpx transport that stands in for poe.ninja."""

    return httpx.MockTransport(_ninja_handler)


@pytest_asyncio.fixture()
async def http_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ninja_transport: httpx.MockTransport,
) -> AsyncIterator[HttpClient]:
    """Real :class:`HttpClient` wired to the MockTransport.

    Uses a per-test ``tmp_path`` cache dir so disk cache can't leak
    across tests.
    """

    settings = Settings(cache_dir=tmp_path / ".cache_http", http_cache_ttl_seconds=0)
    # Patch AsyncClient construction on enter so the mock transport is used.
    original_enter = HttpClient.__aenter__

    async def patched_enter(self: HttpClient) -> HttpClient:
        result = await original_enter(self)
        # Replace the underlying httpx client with one wired to the mock.
        await result._client.aclose()  # type: ignore[union-attr]
        result._client = httpx.AsyncClient(
            transport=ninja_transport,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
        return result

    monkeypatch.setattr(HttpClient, "__aenter__", patched_enter)

    async with HttpClient(settings) as client:
        yield client


@pytest_asyncio.fixture()
async def ninja_source(http_client: HttpClient) -> NinjaSource:
    src = NinjaSource(http_client, league="Mirage")
    return src


@pytest_asyncio.fixture()
async def pricing_service(http_client: HttpClient) -> PricingService:
    return PricingService(http=http_client, league="Mirage")
