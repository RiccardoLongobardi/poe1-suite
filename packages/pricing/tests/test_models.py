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
