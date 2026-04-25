"""Unit tests for pricing domain models — no I/O."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from poe1_pricing import (
    ItemCategory,
    NinjaIndex,
    PriceQuote,
    PriceSnapshot,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TestItemCategory:
    def test_currency_types_flagged(self) -> None:
        assert ItemCategory.CURRENCY.is_currency
        assert ItemCategory.FRAGMENT.is_currency
        assert ItemCategory.CURRENCY.path_segment == "currency"

    def test_item_types_flagged(self) -> None:
        assert not ItemCategory.UNIQUE_WEAPON.is_currency
        assert not ItemCategory.CLUSTER_JEWEL.is_currency
        assert ItemCategory.UNIQUE_JEWEL.path_segment == "item"

    def test_enum_value_matches_ninja_param(self) -> None:
        # The StrEnum value IS the API's type= param — no translation layer.
        assert ItemCategory.UNIQUE_WEAPON.value == "UniqueWeapon"
        assert ItemCategory.CLUSTER_JEWEL.value == "ClusterJewel"


class TestNinjaIndex:
    @pytest.fixture()
    def index(self) -> NinjaIndex:
        with (FIXTURE_DIR / "index_state.json").open() as f:
            return NinjaIndex.model_validate(json.load(f))

    def test_parses_real_index(self, index: NinjaIndex) -> None:
        assert len(index.economy_leagues) >= 2
        assert any(ref.name == "Mirage" for ref in index.economy_leagues)

    def test_resolve_league_by_name(self, index: NinjaIndex) -> None:
        assert index.resolve_league_url("Mirage") == "mirage"
        assert index.resolve_league_url("mirage") == "mirage"
        # Case-insensitive.
        assert index.resolve_league_url("MIRAGE") == "mirage"

    def test_resolve_league_unknown(self, index: NinjaIndex) -> None:
        assert index.resolve_league_url("NotALeague") is None

    def test_find_exp_version(self, index: NinjaIndex) -> None:
        snap = index.economy_version_for("mirage", type_="exp")
        assert snap is not None
        # Version format is an opaque token; sanity-check format.
        assert "-" in snap.version

    def test_no_depthsolo_without_asking(self, index: NinjaIndex) -> None:
        # index_state fixture only has 'exp' entries; asking for depthsolo -> None.
        assert index.economy_version_for("mirage", type_="depthsolo") is None


class TestPriceSnapshot:
    @pytest.fixture()
    def snapshot(self) -> PriceSnapshot:
        now = datetime.now(UTC)
        quotes = (
            PriceQuote(
                name="Divine Orb",
                category=ItemCategory.CURRENCY,
                chaos_value=370.0,
                league="Mirage",
                fetched_at=now,
            ),
            PriceQuote(
                name="Mageblood",
                base_type="Heavy Belt",
                category=ItemCategory.UNIQUE_ACCESSORY,
                chaos_value=20000.0,
                divine_value=54.0,
                league="Mirage",
                fetched_at=now,
            ),
        )
        return PriceSnapshot(
            category=ItemCategory.CURRENCY,
            league="Mirage",
            version="test-1",
            fetched_at=now,
            quotes=quotes,
        )

    def test_by_name_exact_match(self, snapshot: PriceSnapshot) -> None:
        assert snapshot.by_name("Divine Orb") is not None
        assert snapshot.by_name("divine orb") is None  # case-sensitive

    def test_by_name_ci(self, snapshot: PriceSnapshot) -> None:
        hit = snapshot.by_name_ci("mageblood")
        assert hit is not None
        assert hit.name == "Mageblood"
        assert hit.divine_value == pytest.approx(54.0)

    def test_by_name_miss(self, snapshot: PriceSnapshot) -> None:
        assert snapshot.by_name_ci("Headhunter") is None


class TestVariantLookup:
    """Variant-aware lookups on PriceSnapshot."""

    @pytest.fixture()
    def variant_snapshot(self) -> PriceSnapshot:
        now = datetime.now(UTC)
        # Three variants of the same unique + a non-variant filler.
        quotes = (
            PriceQuote(
                name="Forbidden Shako",
                base_type="Great Crown",
                variant="Avatar of Fire",
                category=ItemCategory.UNIQUE_ARMOUR,
                chaos_value=120.0,
                league="Mirage",
                fetched_at=now,
            ),
            PriceQuote(
                name="Forbidden Shako",
                base_type="Great Crown",
                variant="Eldritch Battery",
                category=ItemCategory.UNIQUE_ARMOUR,
                chaos_value=4500.0,
                league="Mirage",
                fetched_at=now,
            ),
            PriceQuote(
                name="Forbidden Shako",
                base_type="Great Crown",
                variant="Mind Over Matter",
                category=ItemCategory.UNIQUE_ARMOUR,
                chaos_value=900.0,
                league="Mirage",
                fetched_at=now,
            ),
            PriceQuote(
                name="Tabula Rasa",
                base_type="Simple Robe",
                variant=None,
                category=ItemCategory.UNIQUE_ARMOUR,
                chaos_value=20.0,
                league="Mirage",
                fetched_at=now,
            ),
        )
        return PriceSnapshot(
            category=ItemCategory.UNIQUE_ARMOUR,
            league="Mirage",
            version="test-2",
            fetched_at=now,
            quotes=quotes,
        )

    def test_variant_match_picks_right_quote(self, variant_snapshot: PriceSnapshot) -> None:
        hit = variant_snapshot.by_name_and_variant("Forbidden Shako", "Eldritch Battery")
        assert hit is not None
        assert hit.chaos_value == pytest.approx(4500.0)

    def test_variant_match_case_insensitive(self, variant_snapshot: PriceSnapshot) -> None:
        hit = variant_snapshot.by_name_and_variant("forbidden shako", "MIND OVER MATTER")
        assert hit is not None
        assert hit.variant == "Mind Over Matter"

    def test_unknown_variant_returns_none(self, variant_snapshot: PriceSnapshot) -> None:
        # Caller asked for a specific variant — we don't silently downgrade.
        hit = variant_snapshot.by_name_and_variant("Forbidden Shako", "Nonexistent Keystone")
        assert hit is None

    def test_no_variant_falls_back_to_first(self, variant_snapshot: PriceSnapshot) -> None:
        # variant=None means "any variant" — degrades to by_name_ci.
        hit = variant_snapshot.by_name_and_variant("Forbidden Shako", None)
        assert hit is not None
        assert hit.name == "Forbidden Shako"

    def test_variant_skipped_when_quote_has_no_variant(
        self, variant_snapshot: PriceSnapshot
    ) -> None:
        # Tabula has variant=None; asking with a specific variant must miss.
        hit = variant_snapshot.by_name_and_variant("Tabula Rasa", "Anything")
        assert hit is None

    def test_variants_of_returns_all(self, variant_snapshot: PriceSnapshot) -> None:
        all_shakos = variant_snapshot.variants_of("Forbidden Shako")
        assert len(all_shakos) == 3
        assert {q.variant for q in all_shakos} == {
            "Avatar of Fire",
            "Eldritch Battery",
            "Mind Over Matter",
        }

    def test_variants_of_miss_returns_empty(self, variant_snapshot: PriceSnapshot) -> None:
        assert variant_snapshot.variants_of("Nonexistent Item") == ()


class TestPriceQuoteValidation:
    def test_negative_chaos_rejected(self) -> None:
        with pytest.raises(ValueError):
            PriceQuote(
                name="x",
                category=ItemCategory.CURRENCY,
                chaos_value=-1.0,
                league="Mirage",
                fetched_at=datetime.now(UTC),
            )

    def test_frozen(self) -> None:
        q = PriceQuote(
            name="Divine Orb",
            category=ItemCategory.CURRENCY,
            chaos_value=370.0,
            league="Mirage",
            fetched_at=datetime.now(UTC),
        )
        with pytest.raises(ValueError):
            q.chaos_value = 400.0
