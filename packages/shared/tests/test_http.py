"""Tests for the async HTTP client.

We drive the client against a local :class:`httpx.MockTransport` so tests
do not hit the network. Retry and cache behaviour are verified by counting
how many upstream requests the transport actually receives.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from poe1_shared.config import Settings
from poe1_shared.http import HttpClient, HttpError


def _make_settings(tmp_path: Path, **overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "cache_dir": tmp_path / "cache",
        "http_max_retries": 2,
        "http_timeout_seconds": 5.0,
        "http_cache_ttl_seconds": 60,
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


async def _make_client(settings: Settings, transport: httpx.MockTransport) -> HttpClient:
    """Construct an HttpClient whose internal AsyncClient uses a mock transport."""

    client = HttpClient(settings)
    await client.__aenter__()
    # Swap the real httpx.AsyncClient for one with the mock transport,
    # preserving the user-agent/timeout config.
    assert client._client is not None
    await client._client.aclose()
    client._client = httpx.AsyncClient(
        transport=transport,
        timeout=settings.http_timeout_seconds,
        headers={"User-Agent": settings.user_agent},
    )
    return client


async def test_get_json_happy_path(tmp_path: Path) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"ok": True, "value": 42})

    settings = _make_settings(tmp_path)
    client = await _make_client(settings, httpx.MockTransport(handler))
    try:
        data = await client.get_json("https://example.test/x")
        assert data == {"ok": True, "value": 42}
        assert call_count == 1
    finally:
        await client.__aexit__(None, None, None)


async def test_cache_serves_repeat_calls(tmp_path: Path) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"n": call_count})

    settings = _make_settings(tmp_path)
    client = await _make_client(settings, httpx.MockTransport(handler))
    try:
        first = await client.get_json("https://example.test/x")
        second = await client.get_json("https://example.test/x")
        assert first == second
        assert call_count == 1  # second call served from cache
    finally:
        await client.__aexit__(None, None, None)


async def test_retry_on_5xx_then_success(tmp_path: Path) -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(503, text="busy")
        return httpx.Response(200, json={"ok": True})

    settings = _make_settings(tmp_path, http_max_retries=3)
    client = await _make_client(settings, httpx.MockTransport(handler))
    try:
        data = await client.get_json("https://example.test/y", use_cache=False)
        assert data == {"ok": True}
        assert call_count == 3
    finally:
        await client.__aexit__(None, None, None)


async def test_permanent_failure_raises(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="missing")

    settings = _make_settings(tmp_path, http_max_retries=1)
    client = await _make_client(settings, httpx.MockTransport(handler))
    try:
        with pytest.raises(HttpError) as exc_info:
            await client.get_json("https://example.test/z", use_cache=False)
        assert exc_info.value.status_code == 404
    finally:
        await client.__aexit__(None, None, None)


async def test_outside_context_manager_raises(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    client = HttpClient(settings)
    with pytest.raises(RuntimeError):
        await client.get_json("https://example.test/x")
