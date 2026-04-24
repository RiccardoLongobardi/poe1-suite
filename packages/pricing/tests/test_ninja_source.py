"""NinjaSource integration against saved real fixtures.

All tests run end-to-end through :class:`HttpClient` with an httpx
MockTransport that serves the real poe.ninja payloads captured on
2026-04-23 (see ``fixtures/`` and ``conftest.py``).
"""

from __future__ import annotations

import pytest

from poe1_pricing import ItemCategory, NinjaSource, NinjaSourceError
from poe1_shared.http import HttpClient


class TestIndexResolution:
    async def test_refresh_index_populates_league(self, ninja_source: NinjaSource) -> None:
        index = await ninja_source.refresh_index()
        assert any(r.name == "Mirage" for r in index.economy_leagues)
        assert ninja_source.league_api_name == "Mirage"

    async def test_unknown_league_raises(self, http_client: HttpClient) -> None:
        src = NinjaSource(http_client, league="BogusLeague")
        with pytest.raises(NinjaSourceError):
            await src.refresh_index()

    async def test_league_api_name_resolves_from_url_slug(self, http_client: HttpClient) -> None:
        # User passes the URL slug - ninja API wants the display name.
        src = NinjaSource(http_client, league="mirage")
        await src.refresh_index()
        assert src.league_api_name == "Mirage"


class TestCurrencySnapshot:
    async def test_parses_all_lines(self, ninja_source: NinjaSource) -> None:
        snap = await ninja_source.fetch_snapshot(ItemCategory.CURRENCY)
        assert snap.category == ItemCategory.CURRENCY
        assert snap.league == "Mirage"
        # Real fixture has 74 currency lines.
        assert len(snap.quotes) == 74

    async def test_mirror_of_kalandra_priced(self, ninja_source: NinjaSource) -> None:
        snap = await ninja_source.fetch_snapshot(ItemCategory.CURRENCY)
        mirror = snap.by_name("Mirror of Kalandra")
        assert mirror is not None
        assert mirror.chaos_value > 0
        # Mirror is listed in chaos, not divines.
        assert mirror.divine_value is None
        assert mirror.details_id == "mirror-of-kalandra"

    async def test_divine_orb_priced(self, ninja_source: NinjaSource) -> None:
        snap = await ninja_source.fetch_snapshot(ItemCategory.CURRENCY)
        divine = snap.by_name("Divine Orb")
        assert divine is not None
        assert divine.chaos_value > 0
        # Divine Orb's own divine value is meaningless.
        assert divine.divine_value is None

    async def test_sparkline_preserved(self, ninja_source: NinjaSource) -> None:
        """The 7-day cumulative-change array should survive parsing."""

        snap = await ninja_source.fetch_snapshot(ItemCategory.CURRENCY)
        mirror = snap.by_name("Mirror of Kalandra")
        assert mirror is not None
        # Sparkline may be empty on low-traffic currency, but if present it's a tuple.
        assert isinstance(mirror.sparkline_7d, tuple)


class TestItemSnapshot:
    async def test_unique_weapon_has_divine_value(self, ninja_source: NinjaSource) -> None:
        snap = await ninja_source.fetch_snapshot(ItemCategory.UNIQUE_WEAPON)
        assert len(snap.quotes) > 0
        first = snap.quotes[0]
        assert first.chaos_value > 0
        # Unique items report both chaos and divine values.
        assert first.divine_value is not None
        assert first.base_type is not None

    async def test_cluster_jewel_base_type_and_variant(self, ninja_source: NinjaSource) -> None:
        """Cluster jewels encode passive count in ``variant`` - keep it."""

        snap = await ninja_source.fetch_snapshot(ItemCategory.CLUSTER_JEWEL)
        assert len(snap.quotes) > 0
        cj = snap.quotes[0]
        assert cj.base_type is not None
        assert cj.variant is not None
        # "3 passives" / "4 passives" / ...
        assert "passives" in cj.variant

    async def test_unique_jewel_parsed(self, ninja_source: NinjaSource) -> None:
        snap = await ninja_source.fetch_snapshot(ItemCategory.UNIQUE_JEWEL)
        assert len(snap.quotes) > 0
        assert all(q.category == ItemCategory.UNIQUE_JEWEL for q in snap.quotes)

    async def test_icon_url_preserved_for_items(self, ninja_source: NinjaSource) -> None:
        snap = await ninja_source.fetch_snapshot(ItemCategory.UNIQUE_WEAPON)
        first = snap.quotes[0]
        assert first.icon_url is not None
        assert first.icon_url.startswith("https://")


class TestFetchQuote:
    async def test_fetch_quote_hits_known_item(self, ninja_source: NinjaSource) -> None:
        q = await ninja_source.fetch_quote("Divine Orb", category=ItemCategory.CURRENCY)
        assert q is not None
        assert q.name == "Divine Orb"

    async def test_fetch_quote_miss_returns_none(self, ninja_source: NinjaSource) -> None:
        q = await ninja_source.fetch_quote("Nonexistent Item", category=ItemCategory.CURRENCY)
        assert q is None

    async def test_fetch_quote_is_case_insensitive(self, ninja_source: NinjaSource) -> None:
        q = await ninja_source.fetch_quote("mirror of kalandra", category=ItemCategory.CURRENCY)
        assert q is not None
        assert q.name == "Mirror of Kalandra"
