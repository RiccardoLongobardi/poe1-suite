"""Domain models for the pricing subsystem.

Two layers are modelled here:

* :class:`NinjaIndex` / :class:`NinjaLeagueRef` / :class:`NinjaSnapshotVersion`
  mirror the response of ``GET /poe1/api/data/index-state`` on poe.ninja.
  They tell us which leagues are live right now and which snapshot
  version strings to plug into the overview URLs. This is the *only*
  poe.ninja-shaped type that escapes the :mod:`sources` subpackage — the
  rest of the world talks :class:`PriceQuote`.

* :class:`PriceQuote` / :class:`PriceSnapshot` are the source-agnostic
  view: one normalised price point per item, plus a bag of quotes for
  a full category (all uniques, all currency, etc). Downstream
  consumers (FOB, future Faustus) only import these.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ItemCategory(StrEnum):
    """poe.ninja overview type slugs we support.

    Kept as a string enum so the same values flow straight into the
    ``type=`` query parameter of poe.ninja's overview endpoints.
    """

    # Currency-shaped endpoints (include ``currencyDetails`` alongside ``lines``).
    CURRENCY = "Currency"
    FRAGMENT = "Fragment"

    # Item-shaped endpoints.
    UNIQUE_WEAPON = "UniqueWeapon"
    UNIQUE_ARMOUR = "UniqueArmour"
    UNIQUE_ACCESSORY = "UniqueAccessory"
    UNIQUE_FLASK = "UniqueFlask"
    UNIQUE_JEWEL = "UniqueJewel"
    CLUSTER_JEWEL = "ClusterJewel"
    SKILL_GEM = "SkillGem"
    MAP = "Map"
    DIVINATION_CARD = "DivinationCard"
    ESSENCE = "Essence"
    SCARAB = "Scarab"
    FOSSIL = "Fossil"

    @property
    def is_currency(self) -> bool:
        """Whether this category lives under the ``currency/overview`` path."""

        return self in {ItemCategory.CURRENCY, ItemCategory.FRAGMENT}

    @property
    def path_segment(self) -> str:
        """poe.ninja URL segment for this category (``currency`` vs ``item``)."""

        return "currency" if self.is_currency else "item"


class NinjaLeagueRef(BaseModel):
    """Entry in ``index-state.economyLeagues``."""

    model_config = ConfigDict(frozen=True)

    name: str  # e.g. "Mirage" — the value the API expects in league=
    url: str  # e.g. "mirage" — the URL slug
    display_name: str = Field(alias="displayName")


class NinjaSnapshotVersion(BaseModel):
    """Entry in ``index-state.snapshotVersions``.

    Versions are published per-league, per-mode (``exp`` / ``depthsolo``).
    For economy lookups we always want ``type == "exp"``.
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    url: str  # league URL slug
    type: str  # "exp" / "depthsolo" / "streamers" / ...
    name: str
    version: str  # opaque token — must be plugged into the overview URL
    snapshot_name: str = Field(alias="snapshotName")
    overview_type: int = Field(alias="overviewType")


class NinjaIndex(BaseModel):
    """Decoded ``/poe1/api/data/index-state`` response."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    economy_leagues: tuple[NinjaLeagueRef, ...] = Field(alias="economyLeagues")
    old_economy_leagues: tuple[NinjaLeagueRef, ...] = Field(
        alias="oldEconomyLeagues",
        default=(),
    )
    snapshot_versions: tuple[NinjaSnapshotVersion, ...] = Field(alias="snapshotVersions")

    def economy_version_for(
        self,
        league_url: str,
        *,
        type_: str = "exp",
    ) -> NinjaSnapshotVersion | None:
        """Find the active snapshot for an economy league & mode, or ``None``.

        ``league_url`` is matched against :attr:`NinjaSnapshotVersion.url`,
        not the display name, so the caller must resolve their label to a
        slug first (see :meth:`resolve_league_url`).
        """

        for snap in self.snapshot_versions:
            if snap.url == league_url and snap.type == type_:
                return snap
        return None

    def resolve_league_url(self, league: str) -> str | None:
        """Resolve a user-facing league string to its ``url`` slug.

        Accepts either a URL slug (``"mirage"``) or a display/official
        name (``"Mirage"``, ``"Hardcore Mirage"``). Case-insensitive.
        Returns ``None`` when the label is not a known active league.
        """

        needle = league.strip().casefold()
        all_leagues: tuple[NinjaLeagueRef, ...] = tuple(self.economy_leagues) + tuple(
            self.old_economy_leagues
        )
        for ref in all_leagues:
            if ref.url.casefold() == needle or ref.name.casefold() == needle:
                return ref.url
        return None


class PriceQuote(BaseModel):
    """Normalised, source-agnostic price point for a single item.

    Divine and exalted values are optional because poe.ninja's currency
    endpoints report only ``chaosEquivalent`` — we leave them ``None``
    rather than fabricating a cross-rate at read time.
    """

    model_config = ConfigDict(frozen=True)

    # Identity
    name: str
    base_type: str | None = None
    variant: str | None = None
    category: ItemCategory
    details_id: str | None = None  # poe.ninja slug, handy for deep links

    # Pricing
    chaos_value: float = Field(ge=0.0)
    divine_value: float | None = Field(default=None, ge=0.0)
    exalted_value: float | None = Field(default=None, ge=0.0)
    listing_count: int | None = Field(default=None, ge=0)
    sample_count: int | None = Field(default=None, ge=0)

    # Last-7-day sparkline as cumulative % change per day.
    sparkline_7d: tuple[float | None, ...] = ()
    low_confidence: bool = False

    # Provenance
    source: str = "poe.ninja"
    league: str  # the API ``league=`` value used
    icon_url: str | None = None
    fetched_at: datetime


class PriceSnapshot(BaseModel):
    """Full category listing at a point in time.

    A snapshot pairs the decoded :class:`PriceQuote`s with the metadata
    required to re-fetch: league, category, upstream version token.
    """

    model_config = ConfigDict(frozen=True)

    category: ItemCategory
    league: str
    version: str
    fetched_at: datetime
    quotes: tuple[PriceQuote, ...]

    def by_name(self, name: str) -> PriceQuote | None:
        """Case-sensitive exact-name lookup — returns the first match."""

        for q in self.quotes:
            if q.name == name:
                return q
        return None

    def by_name_ci(self, name: str) -> PriceQuote | None:
        """Case-insensitive exact-name lookup."""

        needle = name.casefold()
        for q in self.quotes:
            if q.name.casefold() == needle:
                return q
        return None


__all__ = [
    "ItemCategory",
    "NinjaIndex",
    "NinjaLeagueRef",
    "NinjaSnapshotVersion",
    "PriceQuote",
    "PriceSnapshot",
]
