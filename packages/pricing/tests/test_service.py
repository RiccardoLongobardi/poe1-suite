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


class TestQuoteUniqueVariant:
    """Variant-aware unique helpers."""

    async def test_falls_back_to_quote_unique_when_variant_none(
        self, pricing_service: PricingService
    ) -> None:
        snap = await pricing_service.snapshot(ItemCategory.UNIQUE_ARMOUR)
        target = snap.quotes[0].name
        q = await pricing_service.quote_unique_variant(target, None)
        assert q is not None
        assert q.name == target

    async def test_returns_specific_variant_match(self, pricing_service: PricingService) -> None:
        snap = await pricing_service.snapshot(ItemCategory.UNIQUE_ARMOUR)
        # Find a quote with a non-None variant deterministically.
        target = next((q for q in snap.quotes if q.variant is not None), None)
        assert target is not None, "fixture must include at least one variant unique"
        q = await pricing_service.quote_unique_variant(target.name, target.variant)
        assert q is not None
        assert q.name == target.name
        assert q.variant == target.variant
        assert q.chaos_value == target.chaos_value

    async def test_unknown_variant_returns_none(self, pricing_service: PricingService) -> None:
        snap = await pricing_service.snapshot(ItemCategory.UNIQUE_ARMOUR)
        target = next((q for q in snap.quotes if q.variant is not None), None)
        assert target is not None
        # Right name, wrong variant → caller decides whether to fall back.
        q = await pricing_service.quote_unique_variant(target.name, "Definitely Not A Real Variant")
        assert q is None

    async def test_quote_variants_lists_all(self, pricing_service: PricingService) -> None:
        snap = await pricing_service.snapshot(ItemCategory.UNIQUE_ARMOUR)
        # Pick a name that appears more than once in the fixture.
        from collections import Counter

        names = Counter(q.name for q in snap.quotes)
        multi = next((n for n, c in names.items() if c > 1), None)
        if multi is None:
            # Fixture may not have duplicates; in that case the helper
            # should at least return one entry for any known name.
            multi = snap.quotes[0].name
        variants = await pricing_service.quote_variants(multi)
        assert len(variants) >= 1
        assert all(v.name == multi for v in variants)


class TestNewCategories:
    """The HelmetEnchantment and Oil categories should be enumerable."""

    def test_helmet_enchant_value(self) -> None:
        assert ItemCategory.HELMET_ENCHANT.value == "HelmetEnchantment"
        assert not ItemCategory.HELMET_ENCHANT.is_currency

    def test_oil_value(self) -> None:
        assert ItemCategory.OIL.value == "Oil"
        assert not ItemCategory.OIL.is_currency
