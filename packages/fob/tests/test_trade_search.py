"""Unit tests for the ``POST /fob/trade-search`` request/response models.

The HTTP wiring is exercised end-to-end by the FastAPI test client at a
higher level; this module checks the typed request payload behaves the
way the planner UI expects (mod filters serialise correctly, links
constraint passes through, empty stat values stay un-keyed).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from poe1_fob.planner.models import (
    TradeSearchModFilter,
    TradeSearchRequest,
    TradeSearchResponse,
)


class TestTradeSearchModFilter:
    def test_minimum_payload(self) -> None:
        f = TradeSearchModFilter(stat_id="explicit.stat_3299347043")
        assert f.stat_id == "explicit.stat_3299347043"
        assert f.min is None
        assert f.max is None

    def test_with_min_only(self) -> None:
        f = TradeSearchModFilter(stat_id="explicit.stat_x", min=80.0)
        assert f.min == 80.0
        assert f.max is None

    def test_rejects_empty_stat_id(self) -> None:
        with pytest.raises(ValidationError):
            TradeSearchModFilter(stat_id="")


class TestTradeSearchRequest:
    def test_unique_by_name_only(self) -> None:
        req = TradeSearchRequest(item_name="Mageblood")
        assert req.item_name == "Mageblood"
        assert req.online_only is True
        assert req.mods == ()
        assert req.min_links is None

    def test_rare_with_stat_filters(self) -> None:
        req = TradeSearchRequest(
            item_type="Vaal Regalia",
            mods=(
                TradeSearchModFilter(stat_id="explicit.stat_3299347043", min=80.0),
                TradeSearchModFilter(stat_id="explicit.stat_3372524247", min=40.0),
            ),
            min_links=6,
        )
        assert req.item_type == "Vaal Regalia"
        assert len(req.mods) == 2
        assert req.min_links == 6

    def test_min_links_bounds(self) -> None:
        # Out-of-range values rejected.
        with pytest.raises(ValidationError):
            TradeSearchRequest(item_name="X", min_links=0)
        with pytest.raises(ValidationError):
            TradeSearchRequest(item_name="X", min_links=7)

    def test_offline_search(self) -> None:
        req = TradeSearchRequest(item_name="Mageblood", online_only=False)
        assert req.online_only is False


class TestTradeSearchResponse:
    def test_full_response_shape(self) -> None:
        resp = TradeSearchResponse(
            league="Mirage",
            search_id="abc123",
            url="https://www.pathofexile.com/trade/search/Mirage/abc123",
            total_listings=42,
        )
        assert resp.league == "Mirage"
        assert resp.search_id == "abc123"
        assert "abc123" in resp.url
        assert resp.total_listings == 42

    def test_zero_listings_allowed(self) -> None:
        resp = TradeSearchResponse(
            league="Mirage",
            search_id="empty",
            url="https://x",
            total_listings=0,
        )
        assert resp.total_listings == 0

    def test_negative_listings_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TradeSearchResponse(
                league="Mirage",
                search_id="x",
                url="https://x",
                total_listings=-1,
            )
