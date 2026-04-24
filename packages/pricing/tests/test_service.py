"""PricingService facade integration tests.

These exercise the cross-category lookup, in-memory snapshot cache,
and category-specific helpers using the real fixture set.
"""

from __future__ import annotations

from poe1_pricing import ItemCategory, PricingService


class TestQuoteByNameWithCategory:
    async def test_currency_category(self, pricing_service: PricingService) -> None:
        quote = await pricing_service.quote_by_name(
            "Divine Orb",
            category=ItemCategory.CURRENCY,
        )
        assert quote is not None
        assert quote.name == "Divine Orb"
        assert quote.category == ItemCategory.CURRENCY

    async def test_unique_weapon_by_category(self, pricing_service: PricingService) -> None:
        # Pick any weapon name from our fixture deterministically.
        snap = await pricing_service.snapshot(ItemCategory.UNIQUE_WEAPON)
        target = snap.quotes[0].name
        quote = await pricing_service.quote_by_name(
            target,
            category=ItemCategory.UNIQUE_WEAPON,
        )
        assert quote is not None
        assert quote.name == target


class TestQuoteByNameSearch:
    async def test_finds_currency_first(self, pricing_service: PricingService) -> None:
        q = await pricing_service.quote_by_name("Divine Orb")
        assert q is not None
        assert q.category == ItemCategory.CURRENCY

    async def test_miss_returns_none(self, pricing_service: PricingService) -> None:
        q = await pricing_service.quote_by_name("Totally Made Up Item Name")
        assert q is None

    async def test_case_insensitive_cross_category(self, pricing_service: PricingService) -> None:
        q = await pricing_service.quote_by_name("mirror of kalandra")
        assert q is not None
        assert q.category == ItemCategory.CURRENCY


class TestSnapshotCache:
    async def test_snapshot_memoized(self, pricing_service: PricingService) -> None:
        a = await pricing_service.snapshot(ItemCategory.CURRENCY)
        b = await pricing_service.snapshot(ItemCategory.CURRENCY)
        # Same object — no re-fetch within a service lifetime.
        assert a is b

    async def test_invalidate_specific_category(self, pricing_service: PricingService) -> None:
        a = await pricing_service.snapshot(ItemCategory.CURRENCY)
        pricing_service.invalidate(category=ItemCategory.CURRENCY)
        b = await pricing_service.snapshot(ItemCategory.CURRENCY)
        assert a is not b

    async def test_invalidate_all(self, pricing_service: PricingService) -> None:
        await pricing_service.snapshot(ItemCategory.CURRENCY)
        await pricing_service.snapshot(ItemCategory.UNIQUE_WEAPON)
        pricing_service.invalidate()
        # After invalidate the next snapshot calls should re-populate.
        c = await pricing_service.snapshot(ItemCategory.CURRENCY)
        assert c.category == ItemCategory.CURRENCY


class TestQuoteUniqueHelper:
    async def test_finds_any_unique(self, pricing_service: PricingService) -> None:
        # Pull a name from the armour fixture to test the helper.
        snap = await pricing_service.snapshot(ItemCategory.UNIQUE_ARMOUR)
        target = snap.quotes[0].name
        q = await pricing_service.quote_unique(target)
        assert q is not None
        assert q.name == target

    async def test_miss_returns_none(self, pricing_service: PricingService) -> None:
        q = await pricing_service.quote_unique("Headhunter of Nothing")
        assert q is None


class TestCurrencyHelper:
    async def test_quote_currency_basic(self, pricing_service: PricingService) -> None:
        q = await pricing_service.quote_currency("Divine Orb")
        assert q is not None
        assert q.category == ItemCategory.CURRENCY
