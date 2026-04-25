"""Unit tests for the GGG Trade API source.

Pure-function tests cover the parsers and the percentile pricing
helper. End-to-end tests stand up an :class:`httpx.MockTransport` that
replies to ``POST /search/<league>`` and ``GET /fetch/<ids>`` with
crafted bodies and rate-limit headers, so the search → fetch → quote
pipeline runs without touching the live API.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio

from poe1_pricing import (
    ItemCategory,
    RateLimitState,
    StatFilter,
    TradeListing,
    TradeQuery,
    TradeSource,
    percentile_price,
)
from poe1_pricing.sources.trade import (
    _parse_listing,
    _parse_rate_limit,
    _retry_after_seconds,
)
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


class TestRateLimitState:
    def test_parse_canonical_headers(self) -> None:
        state = RateLimitState.parse(
            "8:10:60,15:60:120,60:300:1800",
            "1:10:0,3:60:0,12:300:0",
        )
        assert len(state.windows) == 3
        assert state.windows[0].max_hits == 8
        assert state.windows[0].period_seconds == 10
        assert state.current == (1, 3, 12)

    def test_parse_tolerates_garbage(self) -> None:
        state = RateLimitState.parse("nonsense,8:10:60", "garbage,1:10:0")
        # The valid triple survives, the bad one is dropped.
        assert len(state.windows) == 1
        assert state.windows[0].max_hits == 8

    def test_needs_pause_returns_zero_when_idle(self) -> None:
        state = RateLimitState.parse("8:10:60", "1:10:0")
        assert state.needs_pause() == 0.0

    def test_needs_pause_when_close_to_max(self) -> None:
        # 7/8 = 87.5% > 80% headroom → must pause.
        state = RateLimitState.parse("8:10:60", "7:10:0")
        assert state.needs_pause() > 0

    def test_needs_pause_caps_at_period(self) -> None:
        # Way over the limit — sleep must not exceed the window period.
        state = RateLimitState.parse("8:10:60", "100:10:0")
        assert state.needs_pause() <= 10.0


class TestRateLimitHeaderParsing:
    def test_returns_none_without_rules(self) -> None:
        # No 'Ip' rule advertised → we don't touch the limiter.
        assert _parse_rate_limit({}) is None

    def test_extracts_when_rules_present(self) -> None:
        headers = {
            "x-rate-limit-rules": "Ip,Account",
            "x-rate-limit-ip": "8:10:60",
            "x-rate-limit-ip-state": "1:10:0",
        }
        state = _parse_rate_limit(headers)
        assert state is not None
        assert state.windows[0].max_hits == 8


class TestRetryAfter:
    def test_seconds_format(self) -> None:
        assert _retry_after_seconds({"retry-after": "30"}) == 30.0

    def test_missing(self) -> None:
        assert _retry_after_seconds({}) is None

    def test_garbage(self) -> None:
        # Date-format Retry-After (we don't support it); should return None.
        assert _retry_after_seconds({"retry-after": "Wed, 01 Jan 2099 00:00:00 GMT"}) is None


class TestTradeQueryPayload:
    def test_minimum_payload(self) -> None:
        q = TradeQuery(name="Mageblood", type="Heavy Belt")
        body = q.to_payload()
        assert body["query"]["name"] == "Mageblood"
        assert body["query"]["type"] == "Heavy Belt"
        assert body["query"]["status"]["option"] == "online"
        assert body["sort"] == {"price": "asc"}

    def test_stat_filters_are_anded(self) -> None:
        q = TradeQuery(
            type="Vaal Regalia",
            stats=(
                StatFilter("explicit.stat_3299347043", min=80),
                StatFilter("explicit.stat_3372524247", min=70),
            ),
        )
        body = q.to_payload()
        groups = body["query"]["stats"]
        assert len(groups) == 1
        assert groups[0]["type"] == "and"
        assert len(groups[0]["filters"]) == 2

    def test_empty_value_block_dropped(self) -> None:
        q = TradeQuery(stats=(StatFilter("explicit.x"),))
        f = q.to_payload()["query"]["stats"][0]["filters"][0]
        assert "value" not in f

    def test_extra_filters_are_passed_through(self) -> None:
        q = TradeQuery(extra_filters={"socket_filters": {"filters": {"links": {"min": 6}}}})
        body = q.to_payload()
        assert body["query"]["filters"]["socket_filters"]["filters"]["links"]["min"] == 6


# ---------------------------------------------------------------------------
# Listing parsing
# ---------------------------------------------------------------------------


class TestParseListing:
    def test_minimal_valid_entry(self) -> None:
        entry = {
            "id": "abc",
            "listing": {
                "account": {"name": "user1", "online": True},
                "price": {"type": "price", "amount": 5, "currency": "divine"},
            },
            "item": {"name": "Mageblood", "typeLine": "Heavy Belt"},
        }
        out = _parse_listing(entry)
        assert out is not None
        assert out.price_amount == 5.0
        assert out.price_currency == "divine"
        assert out.online is True
        assert out.item_name == "Mageblood"

    def test_missing_price_drops_entry(self) -> None:
        entry = {"id": "abc", "listing": {"account": {"name": "u"}}, "item": {}}
        assert _parse_listing(entry) is None

    def test_zero_price_drops_entry(self) -> None:
        entry = {
            "id": "abc",
            "listing": {"price": {"amount": 0, "currency": "chaos"}},
            "item": {},
        }
        assert _parse_listing(entry) is None

    def test_non_numeric_amount_drops_entry(self) -> None:
        entry = {
            "id": "abc",
            "listing": {"price": {"amount": "free", "currency": "chaos"}},
            "item": {},
        }
        assert _parse_listing(entry) is None


# ---------------------------------------------------------------------------
# Percentile pricing
# ---------------------------------------------------------------------------


def _l(amount: float, currency: str = "chaos") -> TradeListing:
    return TradeListing(
        listing_id="x",
        account="a",
        online=True,
        price_amount=amount,
        price_currency=currency,
        item_name=None,
        base_type=None,
        item_level=None,
    )


class TestPercentilePrice:
    def test_trims_outliers(self) -> None:
        # 20 listings, mostly 100c, with a 1c scam and a 10000c afk.
        listings = [_l(1.0)] + [_l(100.0)] * 18 + [_l(10_000.0)]
        result = percentile_price(listings, chaos_per_divine=200.0)
        assert result is not None
        median, kept = result
        assert median == 100.0  # outliers trimmed away
        # Trim 15% low + 25% high → ~3 + 5 trimmed from 20 → ~12 kept.
        assert kept >= 10

    def test_currency_conversion(self) -> None:
        # Two listings: 200 chaos + 1 divine (= 200c at the test rate).
        # After conversion both are 200c, median = 200c.
        listings = [_l(200.0, "chaos"), _l(1.0, "divine")]
        result = percentile_price(listings, chaos_per_divine=200.0)
        assert result is not None
        median, kept = result
        assert median == pytest.approx(200.0)
        assert kept == 2

    def test_unknown_currency_dropped(self) -> None:
        # mirror-shard listings can't be converted → dropped.
        listings = [_l(50.0, "chaos"), _l(1.0, "mirror-shard")]
        result = percentile_price(listings, chaos_per_divine=200.0)
        assert result is not None
        _, kept = result
        assert kept == 1

    def test_empty_returns_none(self) -> None:
        assert percentile_price([], chaos_per_divine=200.0) is None

    def test_all_unconvertible_returns_none(self) -> None:
        result = percentile_price([_l(1.0, "exotic-currency")], chaos_per_divine=200.0)
        assert result is None


# ---------------------------------------------------------------------------
# End-to-end with MockTransport
# ---------------------------------------------------------------------------


def _trade_handler(state: dict[str, Any]) -> Any:
    """Build an httpx MockTransport handler that replays canned bodies.

    ``state`` lets the caller observe what was requested (number of
    POSTs/GETs) and inject specific responses per scenario.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/search/" in path and request.method == "POST":
            state.setdefault("search_posts", 0)
            state["search_posts"] += 1
            body = state.get(
                "search_response",
                {
                    "id": "SEARCHID",
                    "total": 3,
                    "result": ["h1", "h2", "h3"],
                },
            )
            return httpx.Response(
                200,
                json=body,
                headers=state.get(
                    "search_headers",
                    {
                        "X-Rate-Limit-Rules": "Ip",
                        "X-Rate-Limit-Ip": "8:10:60",
                        "X-Rate-Limit-Ip-State": "1:10:0",
                    },
                ),
            )
        if "/fetch/" in path and request.method == "GET":
            state.setdefault("fetch_gets", 0)
            state["fetch_gets"] += 1
            body = state.get(
                "fetch_response",
                {
                    "result": [
                        {
                            "id": f"h{i}",
                            "listing": {
                                "account": {"name": f"seller{i}", "online": True},
                                "price": {"amount": amount, "currency": "chaos"},
                            },
                            "item": {"name": "Mageblood", "typeLine": "Heavy Belt"},
                        }
                        for i, amount in enumerate([1.0, 100.0, 100.0, 100.0, 10000.0])
                    ]
                },
            )
            return httpx.Response(
                200,
                json=body,
                headers=state.get(
                    "fetch_headers",
                    {
                        "X-Rate-Limit-Rules": "Ip",
                        "X-Rate-Limit-Ip": "8:10:60",
                        "X-Rate-Limit-Ip-State": "2:10:0",
                    },
                ),
            )
        return httpx.Response(404, text=f"no mock for {request.method} {path}")

    return handler


@pytest_asyncio.fixture()
async def trade_http(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AsyncIterator[tuple[HttpClient, dict[str, Any]]]:
    """An HttpClient wired to a per-test trade mock transport.

    The dict yielded alongside the client lets the test inspect how
    many requests were issued and inject custom responses per scenario.
    """

    state: dict[str, Any] = {}
    transport = httpx.MockTransport(_trade_handler(state))

    settings = Settings(cache_dir=tmp_path / ".cache_http", http_cache_ttl_seconds=0)
    original_enter = HttpClient.__aenter__

    async def patched_enter(self: HttpClient) -> HttpClient:
        result = await original_enter(self)
        await result._client.aclose()  # type: ignore[union-attr]
        result._client = httpx.AsyncClient(
            transport=transport,
            timeout=settings.http_timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        )
        return result

    monkeypatch.setattr(HttpClient, "__aenter__", patched_enter)

    async with HttpClient(settings) as client:
        yield client, state


async def _no_sleep(_: float) -> None:
    return None


class TestTradeSourceFlow:
    async def test_search_returns_id_and_hashes(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, state = trade_http
        src = TradeSource(client, league="Mirage", sleep=_no_sleep)
        search_id, hashes, total = await src.search(TradeQuery(name="Mageblood"))
        assert search_id == "SEARCHID"
        assert hashes == ["h1", "h2", "h3"]
        assert total == 3
        assert state["search_posts"] == 1

    async def test_fetch_listings_parses_entries(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, _ = trade_http
        src = TradeSource(client, league="Mirage", sleep=_no_sleep)
        listings = await src.fetch_listings("SEARCHID", ["h1", "h2", "h3"])
        assert len(listings) == 5
        assert all(li.price_currency == "chaos" for li in listings)

    async def test_fetch_batches_at_ten(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, state = trade_http
        src = TradeSource(client, league="Mirage", sleep=_no_sleep)
        # 25 hashes → 3 fetch calls (10 + 10 + 5).
        await src.fetch_listings("SEARCHID", [f"h{i}" for i in range(25)])
        assert state["fetch_gets"] == 3

    async def test_quote_full_pipeline(self, trade_http: tuple[HttpClient, dict[str, Any]]) -> None:
        client, _ = trade_http
        src = TradeSource(client, league="Mirage", sleep=_no_sleep)
        quote = await src.quote(
            TradeQuery(name="Mageblood", type="Heavy Belt"),
            chaos_per_divine=200.0,
            category=ItemCategory.UNIQUE_ACCESSORY,
        )
        assert quote is not None
        assert quote.source == "ggg.trade"
        assert quote.category == ItemCategory.UNIQUE_ACCESSORY
        assert quote.chaos_value == 100.0  # outliers trimmed → median 100c
        assert quote.league == "Mirage"

    async def test_low_confidence_when_few_kept(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, state = trade_http
        # Only 2 listings → after trimming, very few kept → low_confidence.
        state["search_response"] = {"id": "S", "total": 2, "result": ["h1", "h2"]}
        state["fetch_response"] = {
            "result": [
                {
                    "id": f"h{i}",
                    "listing": {
                        "account": {"name": "x", "online": True},
                        "price": {"amount": amt, "currency": "chaos"},
                    },
                    "item": {},
                }
                for i, amt in enumerate([10.0, 12.0])
            ]
        }
        src = TradeSource(client, league="Mirage", sleep=_no_sleep)
        quote = await src.quote(TradeQuery(type="Heavy Belt"), chaos_per_divine=200.0)
        assert quote is not None
        assert quote.low_confidence is True

    async def test_empty_search_returns_none(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, state = trade_http
        state["search_response"] = {"id": "S", "total": 0, "result": []}
        src = TradeSource(client, league="Mirage", sleep=_no_sleep)
        quote = await src.quote(TradeQuery(type="ImpossibleItem"), chaos_per_divine=200.0)
        assert quote is None

    async def test_poesessid_propagated_as_cookie(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        seen: list[dict[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(dict(request.headers))
            if "/search/" in request.url.path:
                return httpx.Response(200, json={"id": "S", "total": 0, "result": []}, headers={})
            return httpx.Response(404)

        transport = httpx.MockTransport(handler)
        settings = Settings(cache_dir=tmp_path / ".cache_http", http_cache_ttl_seconds=0)
        original_enter = HttpClient.__aenter__

        async def patched_enter(self: HttpClient) -> HttpClient:
            result = await original_enter(self)
            await result._client.aclose()  # type: ignore[union-attr]
            result._client = httpx.AsyncClient(
                transport=transport,
                timeout=settings.http_timeout_seconds,
                headers={"User-Agent": settings.user_agent},
                follow_redirects=True,
            )
            return result

        monkeypatch.setattr(HttpClient, "__aenter__", patched_enter)

        async with HttpClient(settings) as client:
            src = TradeSource(client, league="Mirage", poesessid="abc123", sleep=_no_sleep)
            await src.search(TradeQuery(name="Mageblood"))

        assert seen, "the request handler should have been invoked"
        assert "POESESSID=abc123" in seen[0].get("cookie", "")


class TestRateLimitObservance:
    async def test_proactive_sleep_when_close_to_max(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, state = trade_http
        # State 7/8 → > 80% → must pause.
        state["search_headers"] = {
            "X-Rate-Limit-Rules": "Ip",
            "X-Rate-Limit-Ip": "8:10:60",
            "X-Rate-Limit-Ip-State": "7:10:0",
        }
        slept: list[float] = []

        async def fake_sleep(s: float) -> None:
            slept.append(s)

        src = TradeSource(client, league="Mirage", sleep=fake_sleep)
        await src.search(TradeQuery(name="Mageblood"))
        assert slept and slept[0] > 0

    async def test_retry_after_overrides_proactive_pace(
        self, trade_http: tuple[HttpClient, dict[str, Any]]
    ) -> None:
        client, state = trade_http
        state["search_headers"] = {
            "X-Rate-Limit-Rules": "Ip",
            "X-Rate-Limit-Ip": "8:10:60",
            "X-Rate-Limit-Ip-State": "8:10:0",
            "Retry-After": "12",
        }
        slept: list[float] = []

        async def fake_sleep(s: float) -> None:
            slept.append(s)

        src = TradeSource(client, league="Mirage", sleep=fake_sleep)
        await src.search(TradeQuery(name="Mageblood"))
        assert slept == [12.0]
