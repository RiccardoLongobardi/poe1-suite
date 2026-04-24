"""Tests for the PoB ingest layer: raw-code detection + URL resolution."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from poe1_fob.pob import PobInputError, load_pob
from poe1_fob.pob.ingest import _looks_like_raw_code, _raw_url_for
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

FIXTURE_DIR = Path(__file__).parent / "fixtures"
REAL_POB = (FIXTURE_DIR / "pob_YNQeadFwNBmX.txt").read_text().strip()


# ---------------------------------------------------------------------------
# URL normalisation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "share_url, raw_url",
    [
        ("https://pobb.in/YNQeadFwNBmX", "https://pobb.in/YNQeadFwNBmX/raw"),
        ("https://pobb.in/YNQeadFwNBmX/", "https://pobb.in/YNQeadFwNBmX/raw"),
        ("https://pobb.in/pob/YNQeadFwNBmX", "https://pobb.in/pob/YNQeadFwNBmX/raw"),
        ("https://pastebin.com/abc123", "https://pastebin.com/raw/abc123"),
        ("https://pastebin.com/raw/abc123", "https://pastebin.com/raw/abc123"),
        ("https://www.pastebin.com/abc123", "https://pastebin.com/raw/abc123"),
    ],
)
def test_raw_url_mapping(share_url: str, raw_url: str) -> None:
    assert _raw_url_for(share_url) == raw_url


@pytest.mark.parametrize(
    "bad_url",
    [
        "https://example.com/foo",  # unsupported host
        "ftp://pobb.in/abc",  # wrong scheme
        "https://pobb.in/",  # no share id
        "https://pastebin.com/",  # no share id
    ],
)
def test_raw_url_rejects_bad_inputs(bad_url: str) -> None:
    with pytest.raises(PobInputError):
        _raw_url_for(bad_url)


# ---------------------------------------------------------------------------
# Raw-code heuristic
# ---------------------------------------------------------------------------


def test_real_pob_matches_raw_code_heuristic() -> None:
    assert _looks_like_raw_code(REAL_POB)


def test_short_string_not_a_raw_code() -> None:
    assert not _looks_like_raw_code("abc")
    assert not _looks_like_raw_code("x" * 499)


def test_bad_alphabet_not_a_raw_code() -> None:
    assert not _looks_like_raw_code("x" * 600 + "$$$")


# ---------------------------------------------------------------------------
# load_pob dispatch
# ---------------------------------------------------------------------------


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(cache_dir=tmp_path / "cache", http_cache_ttl_seconds=0)


async def test_load_pob_raw_code_passthrough(settings: Settings) -> None:
    async with HttpClient(settings) as http:
        code, origin = await load_pob(REAL_POB, http=http)
    assert code == REAL_POB
    assert origin is None


async def test_load_pob_empty_rejected(settings: Settings) -> None:
    async with HttpClient(settings) as http:
        with pytest.raises(PobInputError):
            await load_pob("   ", http=http)


async def test_load_pob_unrecognised_rejected(settings: Settings) -> None:
    async with HttpClient(settings) as http:
        with pytest.raises(PobInputError):
            await load_pob("not a pob", http=http)


async def test_load_pob_fetches_pobb_in_url(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """Simulate the pobb.in/<id>/raw endpoint with httpx MockTransport."""

    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, text=REAL_POB + "\n")

    transport = httpx.MockTransport(handler)

    async with HttpClient(settings) as http:
        # Replace the internal client with one wired to our mock transport.
        await http._client.aclose()  # type: ignore[union-attr]
        http._client = httpx.AsyncClient(
            transport=transport,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
        code, origin = await load_pob("https://pobb.in/YNQeadFwNBmX", http=http)

    assert code == REAL_POB
    assert origin == "https://pobb.in/YNQeadFwNBmX"
    assert captured["url"] == "https://pobb.in/YNQeadFwNBmX/raw"


async def test_load_pob_rejects_non_pob_response(settings: Settings) -> None:
    """If pobb.in returns an HTML error page, we must not treat it as a code."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>404</html>")

    transport = httpx.MockTransport(handler)
    async with HttpClient(settings) as http:
        await http._client.aclose()  # type: ignore[union-attr]
        http._client = httpx.AsyncClient(
            transport=transport,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
        with pytest.raises(PobInputError):
            await load_pob("https://pobb.in/BADID", http=http)
