"""GGG official Trade API source adapter.

Used by the planner to price items poe.ninja can't price reliably:

* **Rare items with custom mods** — poe.ninja only indexes uniques,
  cluster jewels, etc. A 6L body armour with +1 socketed gems / life /
  resists / suppression has no poe.ninja entry; the only authoritative
  source is the Trade API.
* **Variant-rich uniques whose poe.ninja variant string we can't pin
  down** — e.g. Watcher's Eye combos with two specific stats.

The Trade API is two-step:

1. ``POST https://www.pathofexile.com/api/trade/search/<league>``
   submits a search query JSON. Returns ``{id, total, result: [hash...]}``
   where ``result`` is up to 100 listing hashes ordered by sort key
   (default: price ascending).

2. ``GET /api/trade/fetch/<id1,id2,...,id10>?query=<searchId>`` fetches
   up to 10 listings at a time, returning their full ``listing`` and
   ``item`` objects. Price lives at ``result[].listing.price`` as
   ``{type: 'price', amount: float, currency: 'chaos'|'divine'|...}``.

GGG enforces rate limits via ``X-Rate-Limit-*`` headers; we parse them
and sleep proactively when any window is close to saturating, and
honour ``Retry-After`` on 429 responses.

Pricing strategy
----------------
Listings are noisy. Two failure modes dominate:

* **Scam-low listings** — sellers price an item very low to bait
  whispers and then negotiate up. Trimming the cheapest 15% removes
  most of them.
* **AFK-high listings** — sellers list above market and forget; the
  prices live forever in the index. Trimming the top 25% removes most.

After trimming we take the median of what remains. With ≥10 trimmed
listings the median is a good proxy for the actual market price; with
< 5 we mark the quote as ``low_confidence``.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from ..models import ItemCategory, PriceQuote

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://www.pathofexile.com/api/trade"
# GGG's fetch endpoint takes up to 10 IDs per call; respect that limit.
_FETCH_BATCH_SIZE = 10
# Trim the cheapest fraction (likely scams / typos) before computing percentile.
_TRIM_LOW_FRACTION = 0.15
# Trim the most expensive fraction (likely AFK / overpriced) before percentile.
_TRIM_HIGH_FRACTION = 0.25
# Below this many trimmed listings the quote is flagged low confidence.
_LOW_CONFIDENCE_THRESHOLD = 5


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TradeSourceError(RuntimeError):
    """Trade API returned a semantically invalid response."""


# ---------------------------------------------------------------------------
# Rate limit parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimitWindow:
    """One ``max:period:penalty`` window from an X-Rate-Limit-* header.

    GGG ships three windows per limit (10s, 60s, 300s); the *state*
    header reports current usage in the same triple format.
    """

    max_hits: int
    period_seconds: int
    penalty_seconds: int

    def remaining(self, current: int) -> int:
        """Hits left in this window before triggering a penalty."""

        return max(0, self.max_hits - current)


@dataclass(frozen=True)
class RateLimitState:
    """Parsed pair of ``X-Rate-Limit-Ip`` and ``X-Rate-Limit-Ip-State`` headers."""

    windows: tuple[RateLimitWindow, ...]
    current: tuple[int, ...]  # parallel to .windows

    @classmethod
    def parse(cls, limit_header: str, state_header: str) -> RateLimitState:
        """Parse the comma-separated triples into structured windows.

        Tolerant: missing / malformed triples produce empty state, so a
        bad header doesn't crash a request — we just lose proactive
        pacing for that response.
        """

        windows: list[RateLimitWindow] = []
        for chunk in (s.strip() for s in limit_header.split(",") if s.strip()):
            try:
                m, p, pen = (int(x) for x in chunk.split(":", 2))
            except ValueError:
                continue
            windows.append(RateLimitWindow(m, p, pen))
        currents: list[int] = []
        for chunk in (s.strip() for s in state_header.split(",") if s.strip()):
            try:
                hits = int(chunk.split(":", 2)[0])
            except (ValueError, IndexError):
                continue
            currents.append(hits)
        # If counts don't match, pad with zeros — we'd rather under-pace
        # than block on a malformed header.
        while len(currents) < len(windows):
            currents.append(0)
        return cls(windows=tuple(windows), current=tuple(currents[: len(windows)]))

    def needs_pause(self, *, headroom: float = 0.8) -> float:
        """Return a sleep time (s) to leave ``headroom`` of capacity in every window.

        Returns 0.0 when every window is comfortably under-utilised.
        For a window at 90% of max with a 10s period, the result is ~1s
        — enough for the oldest hits to age out and bring us back below
        the threshold.
        """

        sleep = 0.0
        for window, current in zip(self.windows, self.current, strict=True):
            if window.max_hits <= 0:
                continue
            usage = current / window.max_hits
            if usage >= headroom:
                # Sleep proportional to how close we are; never longer
                # than the period itself.
                proportion = (usage - headroom) / max(1.0 - headroom, 1e-9)
                proposed = min(float(window.period_seconds), max(0.5, proportion * 2.0))
                sleep = max(sleep, proposed)
        return sleep


def _parse_rate_limit(headers: dict[str, str]) -> RateLimitState | None:
    """Extract the IP-scoped rate limit state from response headers.

    Returns ``None`` when GGG didn't ship the headers (e.g. mocked
    transport in tests, or a 5xx that bypassed the limiter).
    """

    rules = headers.get("x-rate-limit-rules", "")
    # The 'rules' header lists which scopes apply (Ip, Account); we
    # always pace against the IP scope because it's what an unauth'd
    # client is bound by.
    if "Ip" not in rules and "ip" not in rules:
        return None
    limit = headers.get("x-rate-limit-ip")
    state = headers.get("x-rate-limit-ip-state")
    if not limit or not state:
        return None
    return RateLimitState.parse(limit, state)


_RETRY_AFTER_RE = re.compile(r"^\s*(\d+)\s*$")


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    raw = headers.get("retry-after")
    if not raw:
        return None
    m = _RETRY_AFTER_RE.match(raw)
    if m:
        return float(m.group(1))
    # GGG always uses delta-seconds, but date format is in the spec; ignore.
    return None


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StatFilter:
    """One Trade API stat filter.

    ``stat_id`` is the opaque GGG stat token (e.g.
    ``explicit.stat_3299347043`` for ``+# to maximum Life``). The
    full mapping lives in GGG's ``/api/trade/data/stats`` endpoint;
    the planner will discover IDs at run time, not hard-code them
    here. ``min``/``max`` bound the value range; either may be
    ``None`` for an open bound.
    """

    stat_id: str
    min: float | None = None
    max: float | None = None

    def to_payload(self) -> dict[str, Any]:
        value: dict[str, Any] = {}
        if self.min is not None:
            value["min"] = self.min
        if self.max is not None:
            value["max"] = self.max
        out: dict[str, Any] = {"id": self.stat_id, "disabled": False}
        if value:
            out["value"] = value
        return out


@dataclass(frozen=True)
class TradeQuery:
    """Minimal Trade API search query.

    Covers the high-frequency cases we actually need:

    * Pricing a unique by name + base + (optionally) stat filters that
      pin down the variant.
    * Pricing a rare by base type + stat filters for the most valuable
      affixes.

    Less common dimensions (sockets, links, influence, item level
    range, corruption flag) are reachable via :meth:`extra` but most
    callers won't need them — keep the typed surface narrow.
    """

    type: str | None = None
    name: str | None = None
    stats: tuple[StatFilter, ...] = ()
    online_only: bool = True
    extra_filters: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Render the JSON body GGG expects under ``POST /search/<league>``."""

        query: dict[str, Any] = {"status": {"option": "online" if self.online_only else "any"}}
        if self.name is not None:
            query["name"] = self.name
        if self.type is not None:
            query["type"] = self.type
        if self.stats:
            query["stats"] = [
                {"type": "and", "filters": [f.to_payload() for f in self.stats]},
            ]
        if self.extra_filters:
            query["filters"] = self.extra_filters
        return {"query": query, "sort": {"price": "asc"}}


# ---------------------------------------------------------------------------
# Listing parsing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeListing:
    """One parsed listing from the Trade API fetch response."""

    listing_id: str
    account: str
    online: bool
    price_amount: float
    price_currency: str
    item_name: str | None
    base_type: str | None
    item_level: int | None


def _parse_listing(entry: dict[str, Any]) -> TradeListing | None:
    """Turn one fetch ``result[]`` element into a TradeListing.

    Returns ``None`` for malformed entries (missing price, weird
    structure) — we'd rather drop a listing than surface garbage to
    the percentile calculation.
    """

    listing = entry.get("listing") or {}
    item = entry.get("item") or {}
    price = listing.get("price") or {}
    amount = price.get("amount")
    currency = price.get("currency")
    if amount is None or currency is None:
        return None
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return None
    if amount_f <= 0:
        return None
    account = (listing.get("account") or {}).get("name") or ""
    online = bool((listing.get("account") or {}).get("online"))
    return TradeListing(
        listing_id=str(entry.get("id", "")),
        account=str(account),
        online=online,
        price_amount=amount_f,
        price_currency=str(currency),
        item_name=item.get("name") or None,
        base_type=item.get("typeLine") or item.get("baseType") or None,
        item_level=item.get("ilvl"),
    )


# ---------------------------------------------------------------------------
# Percentile pricing
# ---------------------------------------------------------------------------


def _to_chaos(amount: float, currency: str, *, chaos_per_divine: float) -> float | None:
    """Convert a listing's price to chaos for percentile aggregation.

    Returns ``None`` for currencies we don't know how to convert; those
    listings are dropped (a Mageblood listed in mirror shards isn't
    helping anyway). The two universal currencies cover ~99% of
    real-world listings.
    """

    cur = currency.casefold()
    if cur in {"chaos", "chaos orb"}:
        return amount
    if cur in {"divine", "divine orb"}:
        return amount * chaos_per_divine
    return None


def percentile_price(
    listings: list[TradeListing],
    *,
    chaos_per_divine: float,
    trim_low: float = _TRIM_LOW_FRACTION,
    trim_high: float = _TRIM_HIGH_FRACTION,
) -> tuple[float, int] | None:
    """Compute the trimmed-median chaos price from a list of listings.

    Returns ``(chaos_price, kept_listings_count)`` or ``None`` when no
    listing can be priced. The kept count is what the caller should
    feed into the confidence heuristic.

    The sort is by chaos-equivalent ascending; the median index falls
    in the middle of the surviving slice after trimming.
    """

    chaos_values: list[float] = []
    for li in listings:
        c = _to_chaos(li.price_amount, li.price_currency, chaos_per_divine=chaos_per_divine)
        if c is not None:
            chaos_values.append(c)
    if not chaos_values:
        return None
    chaos_values.sort()
    n = len(chaos_values)
    lo = int(n * trim_low)
    hi = max(lo + 1, n - int(n * trim_high))
    kept = chaos_values[lo:hi]
    if not kept:
        kept = chaos_values  # everything was trimmed — fall back to raw median
    mid = kept[len(kept) // 2]
    return mid, len(kept)


# ---------------------------------------------------------------------------
# TradeSource
# ---------------------------------------------------------------------------


class TradeSource:
    """GGG Trade API client — search → fetch → percentile.

    One instance is bound to a league. Auth is optional: pass
    ``poesessid`` to read past the first page of un-authenticated
    listings (rarely needed for pricing — we only look at the cheapest
    ~50 listings).
    """

    def __init__(
        self,
        http: HttpClient,
        league: str,
        *,
        poesessid: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        max_listings: int = 50,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self._http = http
        self._league = league
        self._poesessid = poesessid
        self._base_url = base_url.rstrip("/")
        self._max_listings = max_listings
        # Indirected so tests can inject a no-op sleep.
        self._sleep = sleep

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def league(self) -> str:
        return self._league

    async def search(self, query: TradeQuery) -> tuple[str, list[str], int]:
        """POST a search; return ``(search_id, listing_hashes, total)``.

        ``listing_hashes`` is capped at :attr:`max_listings` (GGG returns
        up to 100 by default; we only need the cheapest N for
        percentile pricing).
        """

        url = f"{self._base_url}/search/{self._league}"
        body, headers = await self._http.post_json(
            url, json_body=query.to_payload(), headers=self._headers()
        )
        await self._honour_rate_limit(headers)

        search_id = str(body.get("id", "")) or None
        if search_id is None:
            raise TradeSourceError(f"trade search response missing 'id': {body!r}")
        result = list(body.get("result") or [])
        total = int(body.get("total") or len(result))
        return search_id, [str(h) for h in result[: self._max_listings]], total

    async def fetch_listings(
        self,
        search_id: str,
        listing_hashes: list[str],
    ) -> list[TradeListing]:
        """Hydrate ``listing_hashes`` into :class:`TradeListing` objects.

        Batches into groups of ten (GGG's per-call cap) and paces between
        batches to stay inside the rate limit windows.
        """

        out: list[TradeListing] = []
        for chunk in _chunks(listing_hashes, _FETCH_BATCH_SIZE):
            url = f"{self._base_url}/fetch/{','.join(chunk)}"
            body, headers = await self._http.request_json(
                "GET",
                url,
                params={"query": search_id},
                headers=self._headers(),
            )
            for entry in body.get("result") or []:
                parsed = _parse_listing(entry)
                if parsed is not None:
                    out.append(parsed)
            await self._honour_rate_limit(headers)
        return out

    async def quote(
        self,
        query: TradeQuery,
        *,
        chaos_per_divine: float,
        category: ItemCategory = ItemCategory.UNIQUE_ARMOUR,
    ) -> PriceQuote | None:
        """End-to-end: search → fetch → trimmed median → :class:`PriceQuote`.

        ``category`` is stamped on the result so downstream consumers
        can route it the same way as poe.ninja quotes; the source
        always reports ``source="ggg.trade"``.
        """

        try:
            search_id, hashes, total = await self.search(query)
        except HttpError as err:
            log.warning("trade_search_failed", url=err.url, status=err.status_code)
            return None
        if not hashes:
            return None

        listings = await self.fetch_listings(search_id, hashes)
        priced = percentile_price(listings, chaos_per_divine=chaos_per_divine)
        if priced is None:
            return None
        chaos_value, kept = priced
        low_confidence = kept < _LOW_CONFIDENCE_THRESHOLD

        return PriceQuote(
            name=query.name or query.type or "",
            base_type=query.type,
            variant=None,
            category=category,
            details_id=None,
            chaos_value=round(chaos_value, 2),
            divine_value=round(chaos_value / chaos_per_divine, 4) if chaos_per_divine > 0 else None,
            exalted_value=None,
            listing_count=total,
            sample_count=kept,
            sparkline_7d=(),
            low_confidence=low_confidence,
            source="ggg.trade",
            league=self._league,
            icon_url=None,
            fetched_at=datetime.now(UTC),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str] | None:
        if self._poesessid is None:
            return None
        return {"Cookie": f"POESESSID={self._poesessid}"}

    async def _honour_rate_limit(self, headers: dict[str, str]) -> None:
        retry = _retry_after_seconds(headers)
        if retry is not None and retry > 0:
            log.warning("trade_rate_limit_hit", sleep_seconds=retry)
            await self._sleep(retry)
            return
        state = _parse_rate_limit(headers)
        if state is None:
            return
        pause = state.needs_pause()
        if pause > 0:
            log.info("trade_rate_limit_pace", sleep_seconds=pause)
            await self._sleep(pause)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _chunks(seq: list[str], size: int) -> list[list[str]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


__all__ = [
    "RateLimitState",
    "RateLimitWindow",
    "StatFilter",
    "TradeListing",
    "TradeQuery",
    "TradeSource",
    "TradeSourceError",
    "percentile_price",
]
