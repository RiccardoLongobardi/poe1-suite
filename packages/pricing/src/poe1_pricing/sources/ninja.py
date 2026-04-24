"""poe.ninja source adapter.

URL scheme (as of 2026-04, post /poe1/ migration)::

    GET /poe1/api/data/index-state
        -> leagues + snapshot versions (opaque tokens)

    GET /poe1/api/economy/stash/{version}/currency/overview?type=<T>&league=<L>
        T in {Currency, Fragment}
        -> {lines: [{currencyTypeName, chaosEquivalent, receive{…}, pay{…},
                     paySparkLine, receiveSparkLine, detailsId, …}],
            currencyDetails: [{id, name, icon, tradeId}]}

    GET /poe1/api/economy/stash/{version}/item/overview?type=<T>&league=<L>
        T in {UniqueWeapon, UniqueArmour, UniqueAccessory, UniqueFlask,
              UniqueJewel, ClusterJewel, SkillGem, Map, DivinationCard,
              Essence, Scarab, Fossil, …}
        -> {lines: [{name, baseType, variant, icon, chaosValue,
                     divineValue, exaltedValue, listingCount, count,
                     sparkLine, lowConfidenceSparkLine, detailsId, …}]}

We do *not* hardcode the version in the URL; we fetch the index first
and pick the latest ``type=="exp"`` snapshot for the requested league.
Index lookups are cached for the short term (poe.ninja updates the
tokens on every snapshot roll — at most once per hour).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from ..models import (
    ItemCategory,
    NinjaIndex,
    NinjaSnapshotVersion,
    PriceQuote,
    PriceSnapshot,
)

log = get_logger(__name__)


class NinjaSourceError(RuntimeError):
    """Raised when poe.ninja can't serve a request we expected to succeed.

    Distinct from :class:`poe1_shared.http.HttpError`: that covers
    transport-level failures, this covers *semantic* failures like an
    unknown league or a snapshot with no ``exp`` version.
    """


_DEFAULT_BASE_URL = "https://poe.ninja/poe1/api"
_INDEX_TTL_SECONDS = 300  # 5 min — index payload is tiny, churns often
_OVERVIEW_TTL_SECONDS = 900  # 15 min — values are the real cost


class NinjaSource:
    """poe.ninja data source for a single league.

    One instance is bound to a user-facing league string (display name
    or URL slug) and lazily resolves it against the live
    ``index-state`` on first use. All subsequent overview fetches reuse
    the resolved snapshot version until :meth:`refresh_index` is
    called.
    """

    def __init__(
        self,
        http: HttpClient,
        league: str,
        *,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._http = http
        self._league_label = league
        self._base_url = base_url.rstrip("/")
        self._index: NinjaIndex | None = None
        self._resolved_league_url: str | None = None

    # ------------------------------------------------------------------
    # Index resolution
    # ------------------------------------------------------------------

    async def refresh_index(self) -> NinjaIndex:
        """Force a re-fetch of the index-state document."""

        url = f"{self._base_url}/data/index-state"
        payload = await self._http.get_json(url, cache_ttl_seconds=_INDEX_TTL_SECONDS)
        index = NinjaIndex.model_validate(payload)
        self._index = index
        resolved = index.resolve_league_url(self._league_label)
        if resolved is None:
            known = ", ".join(
                ref.name for ref in (*index.economy_leagues, *index.old_economy_leagues)
            )
            raise NinjaSourceError(
                f"unknown league {self._league_label!r} — active leagues are: {known}"
            )
        self._resolved_league_url = resolved
        log.info(
            "ninja_index_refreshed",
            league=self._league_label,
            resolved=resolved,
            economy_leagues=len(index.economy_leagues),
        )
        return index

    async def _ensure_index(self) -> NinjaIndex:
        if self._index is None:
            return await self.refresh_index()
        return self._index

    async def _ensure_version(self) -> NinjaSnapshotVersion:
        index = await self._ensure_index()
        assert self._resolved_league_url is not None  # set in refresh_index
        snap = index.economy_version_for(self._resolved_league_url, type_="exp")
        if snap is None:
            raise NinjaSourceError(
                f"no 'exp' snapshot for league {self._league_label!r} "
                f"(resolved to {self._resolved_league_url!r})"
            )
        return snap

    @property
    def league_api_name(self) -> str:
        """The ``league=`` query value poe.ninja expects.

        poe.ninja keys overviews by the league *display name* (``Mirage``),
        not the URL slug (``mirage``). We preserve the name the
        ``economyLeagues`` list gave us.
        """

        index = self._index
        if index is None or self._resolved_league_url is None:
            return self._league_label
        all_refs = tuple(index.economy_leagues) + tuple(index.old_economy_leagues)
        for ref in all_refs:
            if ref.url == self._resolved_league_url:
                return ref.name
        return self._league_label

    # ------------------------------------------------------------------
    # Overviews
    # ------------------------------------------------------------------

    async def fetch_snapshot(self, category: ItemCategory) -> PriceSnapshot:
        """Fetch a full category snapshot for this source's league."""

        snap = await self._ensure_version()
        league_name = self.league_api_name
        url = f"{self._base_url}/economy/stash/{snap.version}/{category.path_segment}/overview"
        params = {"type": category.value, "league": league_name}
        try:
            payload = await self._http.get_json(
                url, params=params, cache_ttl_seconds=_OVERVIEW_TTL_SECONDS
            )
        except HttpError:
            raise
        lines = payload.get("lines") or []
        fetched_at = datetime.now(UTC)
        quotes = tuple(
            _parse_line(line, category=category, league=league_name, fetched_at=fetched_at)
            for line in lines
        )
        return PriceSnapshot(
            category=category,
            league=league_name,
            version=snap.version,
            fetched_at=fetched_at,
            quotes=quotes,
        )

    async def fetch_quote(
        self,
        name: str,
        *,
        category: ItemCategory,
    ) -> PriceQuote | None:
        """Convenience: fetch a category snapshot and look up one name.

        For bulk lookups call :meth:`fetch_snapshot` once and reuse the
        returned :class:`PriceSnapshot`.
        """

        snapshot = await self.fetch_snapshot(category)
        return snapshot.by_name_ci(name)


# ---------------------------------------------------------------------------
# Line parser helpers
# ---------------------------------------------------------------------------


def _parse_line(
    line: dict[str, Any],
    *,
    category: ItemCategory,
    league: str,
    fetched_at: datetime,
) -> PriceQuote:
    """Decode one ``lines[]`` element into a :class:`PriceQuote`."""

    if category.is_currency:
        return _parse_currency_line(line, category=category, league=league, fetched_at=fetched_at)
    return _parse_item_line(line, category=category, league=league, fetched_at=fetched_at)


def _parse_currency_line(
    line: dict[str, Any],
    *,
    category: ItemCategory,
    league: str,
    fetched_at: datetime,
) -> PriceQuote:
    """Decode a currency/fragment line.

    Currency lines have no ``divineValue``; the headline number lives in
    ``chaosEquivalent``. Listing count lives on the ``receive`` sub-object
    (what sellers list) and falls back to ``pay`` if absent.
    """

    chaos = float(line.get("chaosEquivalent", 0.0) or 0.0)
    receive = line.get("receive") or {}
    pay = line.get("pay") or {}
    listing_count = receive.get("listing_count") or pay.get("listing_count")
    sample_count = receive.get("count") or pay.get("count")

    receive_spark = (line.get("receiveSparkLine") or {}).get("data") or []
    pay_spark = (line.get("paySparkLine") or {}).get("data") or []
    sparkline: tuple[float | None, ...] = tuple(
        _as_optional_float(v) for v in (receive_spark or pay_spark)
    )

    low_confidence_receive = (line.get("lowConfidenceReceiveSparkLine") or {}).get("data") or []
    low_confidence_pay = (line.get("lowConfidencePaySparkLine") or {}).get("data") or []
    # If the primary sparklines are empty but the low-confidence ones
    # have points, ninja is flagging the quote as thin.
    low_confidence = bool(
        (not receive_spark and low_confidence_receive) or (not pay_spark and low_confidence_pay)
    )

    return PriceQuote(
        name=str(line.get("currencyTypeName", "")),
        base_type=None,
        variant=None,
        category=category,
        details_id=line.get("detailsId"),
        chaos_value=chaos,
        divine_value=None,
        exalted_value=None,
        listing_count=_as_optional_int(listing_count),
        sample_count=_as_optional_int(sample_count),
        sparkline_7d=sparkline,
        low_confidence=low_confidence,
        source="poe.ninja",
        league=league,
        icon_url=None,
        fetched_at=fetched_at,
    )


def _parse_item_line(
    line: dict[str, Any],
    *,
    category: ItemCategory,
    league: str,
    fetched_at: datetime,
) -> PriceQuote:
    """Decode a unique/jewel/skill-gem/… line."""

    spark = (line.get("sparkLine") or {}).get("data") or []
    low_spark = (line.get("lowConfidenceSparkLine") or {}).get("data") or []
    sparkline: tuple[float | None, ...] = tuple(_as_optional_float(v) for v in (spark or low_spark))
    low_confidence = bool(not spark and low_spark)

    return PriceQuote(
        name=str(line.get("name", "")),
        base_type=cast("str | None", line.get("baseType")),
        variant=cast("str | None", line.get("variant")),
        category=category,
        details_id=line.get("detailsId"),
        chaos_value=float(line.get("chaosValue", 0.0) or 0.0),
        divine_value=_as_optional_float(line.get("divineValue")),
        exalted_value=_as_optional_float(line.get("exaltedValue")),
        listing_count=_as_optional_int(line.get("listingCount")),
        sample_count=_as_optional_int(line.get("count")),
        sparkline_7d=sparkline,
        low_confidence=low_confidence,
        source="poe.ninja",
        league=league,
        icon_url=cast("str | None", line.get("icon")),
        fetched_at=fetched_at,
    )


def _as_optional_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _as_optional_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


__all__ = ["NinjaSource", "NinjaSourceError"]
