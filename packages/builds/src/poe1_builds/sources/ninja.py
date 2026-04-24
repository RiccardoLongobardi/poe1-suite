"""poe.ninja builds source adapter.

URL scheme (post /poe1/ migration, verified live 2026-04)::

    GET /poe1/api/data/index-state
        -> {buildLeagues, economyLeagues, oldBuildLeagues,
            oldEconomyLeagues, snapshotVersions}
        buildLeagues includes SSF variants that economyLeagues doesn't,
        so we match against buildLeagues here. snapshotVersions is
        shared: the same ``type="exp"`` token works for both economy and
        builds on a given league.

    GET /poe1/api/builds/{version}/search?overview={league_url}[&class=X]
        -> protobuf body (NinjaSearchResult.result).
        Columnar layout: ~11 value_lists indexed by field_id with up to
        100 rows each (server cap). The dictionaries referenced by the
        result are NOT inlined - they'd require a separate /dict/{hash}
        fetch (which in practice returns 404 from the public API).
        Our strategy: drive per-class queries so we know ``class_name``
        a priori, and skip dictionary-only fields (main_skill,
        keypassives) in the ref - they're recovered from
        ``FullBuild.path_of_building_export`` downstream.

    GET /poe1/api/builds/{version}/character
            ?overview={league_url}&account=X&name=Y&type=Exp
        -> JSON character payload parsed as :class:`FullBuild`.
        The bookkeeping fields (source_id / snapshot_version /
        fetched_at / league) are injected client-side before
        validation.

Caching:

* Index (``index-state``): 300s TTL - tiny payload, but versions can
  roll hourly.
* Search snapshots: 900s TTL - 100-row protobuf payloads, per-class.
* Character details: 3600s TTL - ~150 KB each, rarely churns within an
  hour.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from ..generated import ninja_builds_pb2 as pb
from ..models import (
    BuildFilter,
    BuildsSnapshot,
    RemoteBuildRef,
)

log = get_logger(__name__)


class NinjaBuildsSourceError(RuntimeError):
    """Raised when poe.ninja builds can't serve a request we expected to succeed.

    Distinct from :class:`poe1_shared.http.HttpError`: that covers
    transport-level failures, this covers *semantic* failures like an
    unknown league or a snapshot with no ``exp`` version.
    """


_DEFAULT_BASE_URL = "https://poe.ninja/poe1/api"
_INDEX_TTL_SECONDS = 300  # 5 min — index payload is tiny, churns often
_SEARCH_TTL_SECONDS = 900  # 15 min — ladder snapshots
_DETAIL_TTL_SECONDS = 3600  # 1 h — character blob is stable within a hour
_SERVER_ROW_CAP = 100  # ninja returns at most 100 rows per search call


# ---------------------------------------------------------------------------
# Local index models (scoped to the builds flavour of the endpoint)
# ---------------------------------------------------------------------------


class _BuildLeagueRef(BaseModel):
    """Entry in ``index-state.buildLeagues``."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    name: str  # e.g. "Mirage" — the value the API expects in league=/name=
    url: str  # e.g. "mirage" — the URL slug
    display_name: str = Field(alias="displayName")


class _SnapshotVersion(BaseModel):
    """Entry in ``index-state.snapshotVersions``."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    url: str  # league URL slug
    type: str  # "exp" / "depthsolo" / ...
    name: str
    version: str  # opaque token — plugged into the search / character URLs


class _BuildsIndex(BaseModel):
    """Trimmed ``/poe1/api/data/index-state`` view for the builds adapter."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="allow")

    build_leagues: tuple[_BuildLeagueRef, ...] = Field(alias="buildLeagues", default=())
    old_build_leagues: tuple[_BuildLeagueRef, ...] = Field(alias="oldBuildLeagues", default=())
    snapshot_versions: tuple[_SnapshotVersion, ...] = Field(alias="snapshotVersions", default=())

    def resolve_league_url(self, league: str) -> str | None:
        """Resolve a user-facing league string to its build-league ``url`` slug.

        Accepts either a URL slug (``"mirage"``) or a display/official
        name (``"Mirage"``, ``"SSF Mirage"``). Case-insensitive.
        """

        needle = league.strip().casefold()
        all_leagues = tuple(self.build_leagues) + tuple(self.old_build_leagues)
        for ref in all_leagues:
            if ref.url.casefold() == needle or ref.name.casefold() == needle:
                return ref.url
        return None

    def version_for(self, league_url: str, *, type_: str = "exp") -> _SnapshotVersion | None:
        for snap in self.snapshot_versions:
            if snap.url == league_url and snap.type == type_:
                return snap
        return None


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class NinjaBuildsSource:
    """poe.ninja builds data source for a single league.

    One instance is bound to a user-facing league string (display name
    or URL slug) and lazily resolves it against the live
    ``index-state`` on first use. Subsequent search / detail fetches
    reuse the resolved snapshot version until :meth:`refresh_index` is
    called.

    Two methods:

    * :meth:`fetch_snapshot` — one columnar search, cheap refs only.
    * :meth:`fetch_build_detail` — per-character hydration (~150 KB).
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
        self._index: _BuildsIndex | None = None
        self._resolved_league_url: str | None = None

    # ------------------------------------------------------------------
    # Index resolution
    # ------------------------------------------------------------------

    async def refresh_index(self) -> _BuildsIndex:
        """Force a re-fetch of the index-state document."""

        url = f"{self._base_url}/data/index-state"
        payload = await self._http.get_json(url, cache_ttl_seconds=_INDEX_TTL_SECONDS)
        index = _BuildsIndex.model_validate(payload)
        resolved = index.resolve_league_url(self._league_label)
        if resolved is None:
            known = ", ".join(ref.name for ref in (*index.build_leagues, *index.old_build_leagues))
            raise NinjaBuildsSourceError(
                f"unknown build league {self._league_label!r} — known build leagues are: {known}"
            )
        self._index = index
        self._resolved_league_url = resolved
        log.info(
            "ninja_builds_index_refreshed",
            league=self._league_label,
            resolved=resolved,
            build_leagues=len(index.build_leagues),
        )
        return index

    async def _ensure_index(self) -> _BuildsIndex:
        if self._index is None:
            return await self.refresh_index()
        return self._index

    async def _ensure_version(self) -> tuple[_BuildsIndex, _SnapshotVersion, str]:
        index = await self._ensure_index()
        assert self._resolved_league_url is not None  # set in refresh_index
        snap = index.version_for(self._resolved_league_url, type_="exp")
        if snap is None:
            raise NinjaBuildsSourceError(
                f"no 'exp' snapshot for league {self._league_label!r} "
                f"(resolved to {self._resolved_league_url!r})"
            )
        return index, snap, self._resolved_league_url

    @property
    def league_api_name(self) -> str:
        """The league display name (``Mirage`` / ``SSF Mirage`` / …).

        We key both query params and the source_id on this name so
        downstream consumers don't need to resolve the slug.
        """

        index = self._index
        if index is None or self._resolved_league_url is None:
            return self._league_label
        all_refs = tuple(index.build_leagues) + tuple(index.old_build_leagues)
        for ref in all_refs:
            if ref.url == self._resolved_league_url:
                return ref.name
        return self._league_label

    # ------------------------------------------------------------------
    # Search (ref listing)
    # ------------------------------------------------------------------

    async def fetch_snapshot(self, filt: BuildFilter | None = None) -> BuildsSnapshot:
        """One search call, decoded into :class:`BuildsSnapshot`.

        The server returns at most 100 rows per call. When ``filt``
        doesn't pin a ``class_`` the rows mix all ascendancies (class
        names can't be resolved without the class dictionary, which
        isn't served by the public API); in that case the refs carry an
        empty ``class_name``. Callers that need per-class coverage
        should drive per-class queries via :class:`BuildsService`.
        """

        _, snap, league_url = await self._ensure_version()
        league_name = self.league_api_name
        filt = filt or BuildFilter()

        url = f"{self._base_url}/builds/{snap.version}/search"
        params: dict[str, Any] = {"overview": league_url}
        if filt.class_:
            params["class"] = filt.class_
        try:
            body = await self._http.get_bytes(
                url,
                params=params,
                cache_ttl_seconds=_SEARCH_TTL_SECONDS,
            )
        except HttpError:
            raise

        result: Any = pb.NinjaSearchResult()  # type: ignore[attr-defined]
        result.ParseFromString(body)
        search = result.result

        fetched_at = datetime.now(UTC)
        refs = tuple(
            _decode_refs(
                search,
                league_url=league_url,
                league_name=league_name,
                class_filter=filt.class_,
                snapshot_version=snap.version,
                fetched_at=fetched_at,
            )
        )

        # Apply post-fetch caps / filters that the server doesn't cover.
        refs = _apply_level_range(refs, filt.level_range)
        if filt.top_n_per_class is not None:
            refs = refs[: filt.top_n_per_class]

        log.info(
            "ninja_builds_search",
            league=league_name,
            version=snap.version,
            class_filter=filt.class_,
            total=search.total,
            rows=len(refs),
        )
        return BuildsSnapshot(
            league=league_name,
            snapshot_version=snap.version,
            fetched_at=fetched_at,
            total=search.total,
            refs=refs,
        )

    # ------------------------------------------------------------------
    # Detail (hydration)
    # ------------------------------------------------------------------

    async def fetch_build_detail(self, ref: RemoteBuildRef) -> Any:
        """Fetch the full character payload for a ref.

        Returns a :class:`FullBuild` (typed as ``Any`` here to keep this
        module free of a circular ``FullBuild`` import — the real type
        is ``poe1_builds.models.FullBuild``).
        """

        # Local import to break the light cycle models ↔ sources.ninja.
        from ..models import FullBuild

        _, snap, league_url = await self._ensure_version()
        league_name = self.league_api_name

        url = f"{self._base_url}/builds/{snap.version}/character"
        params: dict[str, Any] = {
            "overview": league_url,
            "account": ref.account,
            "name": ref.character,
            "type": "Exp",
        }
        try:
            payload = cast(
                "dict[str, Any]",
                await self._http.get_json(
                    url,
                    params=params,
                    cache_ttl_seconds=_DETAIL_TTL_SECONDS,
                ),
            )
        except HttpError:
            raise

        # Inject bookkeeping (source_id is stable across snapshots).
        payload = dict(payload)
        payload["source_id"] = ref.source_id
        payload["snapshot_version"] = snap.version
        payload["fetched_at"] = datetime.now(UTC).isoformat()
        payload["league"] = league_name

        build = FullBuild.model_validate(payload)
        log.debug(
            "ninja_builds_detail_fetched",
            account=ref.account,
            character=ref.character,
            source_id=ref.source_id,
        )
        return build


# ---------------------------------------------------------------------------
# Columnar decoding helpers
# ---------------------------------------------------------------------------


_SHORTNUM_RE = re.compile(
    r"^\s*(?P<op>>|<)?\s*(?P<num>[0-9]+(?:\.[0-9]+)?)\s*(?P<suf>[kKmMbB])?\s*$"
)


def _parse_shortnum(raw: str) -> int:
    """Decode poe.ninja's short-form numbers (``"119k"``, ``"2.9M"``, ``"> 10M"``).

    Returns 0 for empty / unrecognised input. Prefix operators (``>``,
    ``<``) are accepted and ignored — the payload uses them only for
    defensive-cap display, never for real numeric comparisons.
    """

    if not raw:
        return 0
    m = _SHORTNUM_RE.match(raw)
    if m is None:
        return 0
    num = float(m.group("num"))
    suf = (m.group("suf") or "").lower()
    mult = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suf, 1)
    return int(num * mult)


def _value_list(search: Any, name: str) -> Any | None:
    """Return the first value-list with the given id, or ``None``."""

    for vl in search.value_lists:
        if vl.id == name:
            return vl
    return None


def _column_size(search: Any) -> int:
    """Number of rows present - take the shortest parallel column.

    value_lists are parallel arrays indexed by row position. In practice
    the server keeps them aligned at 100; we still bound by the shortest
    defensively so a ragged payload can't IndexError.
    """

    names = ("name", "account", "level", "class", "life", "energyshield", "ehp", "dps")
    sizes = [len(vl.values) for n in names if (vl := _value_list(search, n)) is not None]
    return min(sizes) if sizes else 0


def _decode_refs(
    search: Any,
    *,
    league_url: str,
    league_name: str,
    class_filter: str | None,
    snapshot_version: str,
    fetched_at: datetime,
) -> list[RemoteBuildRef]:
    """Decode the columnar value_lists into a list of :class:`RemoteBuildRef`."""

    names_vl = _value_list(search, "name")
    accounts_vl = _value_list(search, "account")
    level_vl = _value_list(search, "level")
    life_vl = _value_list(search, "life")
    es_vl = _value_list(search, "energyshield")
    ehp_vl = _value_list(search, "ehp")
    dps_vl = _value_list(search, "dps")

    if names_vl is None or accounts_vl is None:
        return []

    n = _column_size(search)
    refs: list[RemoteBuildRef] = []
    for i in range(n):
        name = names_vl.values[i].str
        account = accounts_vl.values[i].str
        if not name or not account:
            continue  # defensive — drop rows without identity

        level = level_vl.values[i].number if level_vl is not None else 0
        # level column can be unset for some low-tier rows; clamp to [1,100]
        level = max(1, min(100, int(level) or 1))

        life = max(0, int(life_vl.values[i].number) if life_vl is not None else 0)
        es = max(0, int(es_vl.values[i].number) if es_vl is not None else 0)
        ehp_raw = ehp_vl.values[i].str if ehp_vl is not None else ""
        dps_raw = dps_vl.values[i].str if dps_vl is not None else ""
        ehp = _parse_shortnum(ehp_raw)
        dps = _parse_shortnum(dps_raw)

        # When class_filter is set, every row has that class. When not,
        # we leave it blank (resolving the dict would require a /dict/
        # endpoint the public API doesn't expose).
        class_name = class_filter or ""

        source_id = f"ninja::{league_url}::{account}::{name}"

        ref = RemoteBuildRef.model_validate(
            {
                "source_id": source_id,
                "account": account,
                "character": name,
                "class": class_name,
                "level": level,
                "life": life,
                "energy_shield": es,
                "ehp": ehp,
                "dps": dps,
                "main_skill": None,
                "weapon_mode": None,
                "league": league_name,
                "snapshot_version": snapshot_version,
                "fetched_at": fetched_at,
            }
        )
        refs.append(ref)
    return refs


def _apply_level_range(
    refs: tuple[RemoteBuildRef, ...],
    level_range: tuple[int, int] | None,
) -> tuple[RemoteBuildRef, ...]:
    if level_range is None:
        return refs
    lo, hi = level_range
    return tuple(r for r in refs if lo <= r.level <= hi)


__all__ = ["NinjaBuildsSource", "NinjaBuildsSourceError"]
