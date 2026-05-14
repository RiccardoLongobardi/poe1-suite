"""FastAPI router for the FOB (Frusta Oracle Builder) endpoints.

This module exposes:

* ``POST /fob/analyze-pob`` — resolves a raw PoB code or pobb.in / pastebin
  share URL into a :class:`poe1_core.Build` plus the full :class:`PobSnapshot`.
* ``POST /fob/extract-intent`` — converts a free-text query (IT or EN) into a
  strongly-typed :class:`poe1_core.BuildIntent` using the hybrid rule-based +
  LLM fallback pipeline.
* ``POST /fob/recommend`` — given a :class:`BuildIntent`, fetches build
  candidates from all sources, applies hard-constraint filtering, scores each
  candidate on six weighted dimensions, and returns the top-N ranked builds.
* ``POST /fob/plan`` — given the same input as ``/analyze-pob``, runs the
  analyze pipeline and then turns the resulting :class:`Build` into a
  staged upgrade :class:`BuildPlan` with poe.ninja-priced items.

Keep all HTTP-shaped types (request/response models) local to this file
so the core domain models don't pick up FastAPI/OpenAPI concerns.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import AsyncIterator
from typing import Annotated, Literal

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from poe1_core.models import Build
from poe1_core.models.build_intent import BuildIntent
from poe1_pricing import PricingService, StatFilter, TradeQuery, TradeSource
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from .gear import GearProgression, gear_progression_for
from .gems import GemProgression, derive_gem_progression, gem_progression_for
from .intent import IntentLlmError, extract_intent
from .planner import (
    PlannerService,
    PlanRequest,
    PlanResponse,
    PricingProgress,
)
from .pob import (
    PobInputError,
    PobParseError,
    PobSnapshot,
    decode_export,
    encode_pob_code,
    load_pob,
    parse_snapshot,
    snapshot_to_build,
)
from .pob import clean_mod_lines as _clean_mod_lines
from .pob import extract_mods as _extract_mod_patterns
from .ranking import RankingEngine, RecommendRequest, RecommendResponse, SourceAggregator
from .tree import StageTree, TreeProgression, encode_pob_tree_url, progression_for

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Request / response shapes
# ---------------------------------------------------------------------------


class ExtractIntentRequest(BaseModel):
    """Input for ``POST /fob/extract-intent``."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Free-text description of the desired build — Italian or English. "
            "Example: 'voglio una cold build comfy per mapping' or "
            "'looking for a cheap CI caster for bossing'."
        ),
    )


class AnalyzePobRequest(BaseModel):
    """Input for ``POST /fob/analyze-pob``.

    The ``input`` field accepts any of:
    * a raw PoB export code (url-safe base64 of zlib-compressed XML),
    * a ``https://pobb.in/<id>`` share URL,
    * a ``https://pastebin.com/<id>`` share URL.
    """

    model_config = ConfigDict(frozen=True)

    input: str = Field(
        ...,
        min_length=1,
        description=(
            "Raw PoB export code, or a pobb.in / pastebin share URL pointing "
            "at one. The server will follow the URL to fetch the raw code."
        ),
    )


class AnalyzePobResponse(BaseModel):
    """Response from ``POST /fob/analyze-pob``.

    ``build`` is the cross-source normalised view used by ranking and
    planning. ``snapshot`` keeps the full PoB detail (tree, jewels, flasks,
    config, notes) for debugging and for the UI to render a PoB-style
    summary without re-parsing.
    """

    model_config = ConfigDict(frozen=True)

    build: Build
    snapshot: PobSnapshot


class StageExportRequest(BaseModel):
    """Input for ``POST /fob/stage-export``.

    Carries the same identifiers as the GET variant plus the user's
    original PoB code. When the matched template has no curated tree
    progression, the server decodes ``user_pob_code`` and uses its
    allocated nodes — so the import preserves the user's actual tree
    instead of falling back to an empty one.
    """

    model_config = ConfigDict(frozen=True)

    template_name: str = Field(..., min_length=1)
    stage_key: str = Field(..., min_length=1)
    character_class: str = Field(default="Marauder", min_length=1)
    ascendancy: str | None = None
    level: int = Field(default=90, ge=1, le=100)
    user_pob_code: str | None = Field(
        default=None,
        description=(
            "Optional raw PoB export code the user originally pasted. "
            "Used as the tree fallback when no curated TreeProgression "
            "is registered for ``template_name``. Accepted as raw code "
            "only (no pobb.in / pastebin URL resolution — keep this "
            "endpoint network-free)."
        ),
    )


class StageExportResponse(BaseModel):
    """Output for ``GET|POST /fob/stage-export``."""

    model_config = ConfigDict(frozen=True)

    code: str | None
    stage_key: str
    template_name: str
    tree_source: str = Field(
        default="progression",
        description=(
            "Where the tree in the exported code came from: "
            "'progression' (curated for the template), "
            "'user_pob' (decoded from the user's original PoB), "
            "'empty' (no tree — PoB will show class start only)."
        ),
    )


class TradeUrlRequest(BaseModel):
    """Input for ``POST /fob/trade-url``.

    Asks the server to build a pre-filled GGG Trade search URL for an
    item. The request must specify at least ``item_name`` (unique
    lookups) or ``item_type`` (rare-by-base lookups). ``mod_lines``
    are the raw PoB mod text lines — the server extracts numeric
    stat filters via the same pattern table the pricer uses.
    """

    model_config = ConfigDict(frozen=True)

    item_name: str | None = Field(
        default=None,
        description="Unique name (e.g. 'Mageblood'). Mutually-best with item_type.",
    )
    item_type: str | None = Field(
        default=None,
        description="Base type (e.g. 'Astral Plate') — used when item_name is None.",
    )
    mod_lines: tuple[str, ...] = Field(
        default=(),
        description=(
            "Raw mod text lines from the item. The server extracts "
            "stat_id + min via MOD_PATTERNS. Lines that don't match "
            "any pattern are silently dropped."
        ),
    )


class TradeUrlResponse(BaseModel):
    """Output for ``POST /fob/trade-url``."""

    model_config = ConfigDict(frozen=True)

    url: str | None = Field(
        default=None,
        description=(
            "Pre-filled pathofexile.com/trade URL ready to open. None "
            "when source='rate_limited' — frontend should fall back to "
            "the bare search page."
        ),
    )
    source: Literal["cache", "fresh", "rate_limited"] = Field(
        default="fresh",
        description=(
            "Where the URL came from: 'cache' (in-memory hit, no GGG "
            "call), 'fresh' (one GGG call made, result cached for "
            "future requests), 'rate_limited' (GGG returned 429 — try "
            "again in 30-60 s)."
        ),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# In-memory TTL cache for /fob/trade-url. Keyed by sha256 of the
# normalised query (league + name + type + sorted stat_ids). GGG search
# IDs live ~10 min on their side, so we cache for slightly less to avoid
# returning stale ids that fail to load. The cache survives across
# requests but resets on container restart — acceptable for free-tier
# Render that spins down after 15 min idle anyway.
_TRADE_URL_CACHE_TTL = 480.0  # 8 minutes
_TRADE_URL_CACHE_MAX = 500  # entries; trims LRU-style when exceeded
_trade_url_cache: dict[str, tuple[str, float]] = {}


def _trade_url_cache_get(key: str) -> str | None:
    entry = _trade_url_cache.get(key)
    if entry is None:
        return None
    url, expires_at = entry
    if time.monotonic() > expires_at:
        del _trade_url_cache[key]
        return None
    return url


def _trade_url_cache_set(key: str, url: str) -> None:
    if len(_trade_url_cache) >= _TRADE_URL_CACHE_MAX:
        # Cheap LRU-ish eviction: drop the oldest entry.
        oldest = min(_trade_url_cache.items(), key=lambda kv: kv[1][1])
        _trade_url_cache.pop(oldest[0], None)
    _trade_url_cache[key] = (url, time.monotonic() + _TRADE_URL_CACHE_TTL)


# ---------------------------------------------------------------------------
# Helpers (legacy)
# ---------------------------------------------------------------------------


def _sse_format(event: PricingProgress) -> str:
    """Render one progress event as a Server-Sent Events frame.

    SSE expects ``data: <payload>\\n\\n`` blocks. We serialise the
    Pydantic model with ``by_alias=True`` so camelCase aliases on the
    nested :class:`BuildPlan` (when the ``done`` event carries it)
    match what the rest of the API emits — same shape the React shell
    already parses.
    """

    payload = event.model_dump_json(by_alias=True)
    return f"data: {payload}\n\n"


def _source_id_for(code: str) -> str:
    """Derive a stable build id from the export code.

    Same code => same id, so re-importing the same build is idempotent.
    """

    digest = hashlib.sha1(code.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"pob::{digest[:12]}"


async def _resolve_pob_to_build(
    pob_input: str,
    *,
    http: HttpClient,
) -> tuple[Build, PobSnapshot]:
    """Run the full ingest → parse → map pipeline.

    Shared by ``/analyze-pob`` and ``/plan`` so the two endpoints stay
    in lockstep on input handling and error semantics.
    """

    try:
        code, origin_url = await load_pob(pob_input, http=http)
    except PobInputError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except HttpError as err:
        raise HTTPException(status_code=502, detail=f"upstream fetch failed: {err}") from err

    try:
        xml_bytes = decode_export(code)
        snapshot = parse_snapshot(xml_bytes, export_code=code, origin_url=origin_url)
    except PobParseError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    try:
        build = snapshot_to_build(snapshot, source_id=_source_id_for(code))
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err

    return build, snapshot


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def make_router(settings: Settings) -> APIRouter:
    """Build the ``/fob`` router.

    The factory takes :class:`Settings` so the router can share the
    HTTP cache directory and user-agent with the rest of the app. The
    :class:`HttpClient` is opened per-request to keep the blast radius
    of failed requests small — request-scoped clients are cheap because
    the on-disk cache is shared.
    """

    router = APIRouter(prefix="/fob", tags=["fob"])

    @router.post(
        "/analyze-pob",
        response_model=AnalyzePobResponse,
        summary="Decode a PoB export, URL, or paste and classify the build.",
    )
    async def analyze_pob(
        payload: Annotated[AnalyzePobRequest, Body()],
    ) -> AnalyzePobResponse:
        async with HttpClient(settings) as http:
            build, snapshot = await _resolve_pob_to_build(payload.input, http=http)

        log.info(
            "fob_analyze_pob_ok",
            source_id=build.source_id,
            character_class=build.character_class,
            ascendancy=build.ascendancy,
            main_skill=build.main_skill,
            origin_url=snapshot.origin_url,
        )
        return AnalyzePobResponse(build=build, snapshot=snapshot)

    @router.post(
        "/extract-intent",
        response_model=BuildIntent,
        summary="Convert a free-text query into a structured BuildIntent.",
    )
    async def extract_intent_endpoint(
        payload: Annotated[ExtractIntentRequest, Body()],
    ) -> BuildIntent:
        try:
            intent = await extract_intent(payload.query, settings=settings)
        except IntentLlmError as exc:
            raise HTTPException(status_code=502, detail=f"LLM fallback failed: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        log.info(
            "fob_extract_intent_ok",
            origin=intent.parser_origin,
            confidence=intent.confidence,
            damage=intent.damage_profile,
            playstyle=intent.playstyle,
        )
        return intent

    @router.post(
        "/recommend",
        response_model=RecommendResponse,
        summary=("Rank ladder builds against a BuildIntent and return the top-N candidates."),
    )
    async def recommend(
        payload: Annotated[RecommendRequest, Body()],
    ) -> RecommendResponse:
        """Fetch → filter → score → sort.

        1. :class:`SourceAggregator` fans out to poe.ninja (19 ascendancies
           concurrently) and merges refs.
        2. :class:`RankingEngine` drops hard-constraint violations, scores
           each ref on six weighted dimensions, and returns the top-N.

        On upstream timeout the engine still runs over whatever refs were
        fetched in time.
        """
        async with HttpClient(settings) as http:
            agg = SourceAggregator(settings)
            refs = await agg.fetch_candidates(payload.intent, http=http)

        engine = RankingEngine()
        ranked = engine.rank(payload.intent, refs, top_n=payload.top_n)

        log.info(
            "fob_recommend_ok",
            candidates=len(refs),
            returned=len(ranked),
            top_score=ranked[0].score.total if ranked else 0.0,
        )
        return RecommendResponse(
            ranked=tuple(ranked),
            total_candidates=len(refs),
            intent=payload.intent,
        )

    @router.post(
        "/plan",
        response_model=PlanResponse,
        summary=(
            "Run analyze-pob then turn the build into a staged upgrade plan "
            "with poe.ninja-priced items."
        ),
    )
    async def plan_endpoint(
        payload: Annotated[PlanRequest, Body()],
    ) -> PlanResponse:
        """Analyze → price → bucket → assemble plan.

        1. The PoB ingest pipeline produces a :class:`Build` (same path
           as ``/analyze-pob``).
        2. :class:`PricingService` is opened against the configured
           league for poe.ninja lookups.
        3. :class:`PlannerService` prices each unique key item, buckets
           by divine cost into the 6-stage layout (Early/Mid/End Campaign
           + Early/End Mapping + High Investment), and returns the
           assembled :class:`BuildPlan`.

        The HTTP client and pricing service share a single
        :class:`HttpClient` so cache and rate-limit accounting are
        unified.
        """

        from .planner.templates import pick_template

        async with HttpClient(settings) as http:
            build, _ = await _resolve_pob_to_build(payload.input, http=http)

            pricing = PricingService(http=http, league=settings.poe_league)
            trade = TradeSource(http=http, league=settings.poe_league)
            planner = PlannerService(pricing, trade=trade)
            plan = await planner.plan(build, target_goal=payload.target_goal)
            template_name = pick_template(build).name

        log.info(
            "fob_plan_ok",
            source_id=build.source_id,
            target_goal=payload.target_goal.value,
            template_name=template_name,
            stages=len(plan.stages),
            total_min_div=plan.total_estimated_cost.min.amount,
            total_max_div=plan.total_estimated_cost.max.amount,
        )
        return PlanResponse(build=build, plan=plan, template_name=template_name)

    @router.post(
        "/plan/reverse",
        response_model=PlanResponse,
        summary=(
            "Like /plan but enriched with per-item upgrade ladders derived "
            "from the user's endgame KeyItems (Step 13.C — reverse-progression)."
        ),
    )
    async def plan_reverse_endpoint(
        payload: Annotated[PlanRequest, Body()],
    ) -> PlanResponse:
        """Reverse-mode plan: template advice + ladder rationales per stage.

        Same input shape as ``/plan``. Internally:

        1. Build is resolved from the PoB input (same as ``/plan``).
        2. :class:`PlannerService` is wired with a default
           :class:`CompositeDegrader` (AwakenedGemDegrader →
           HardcodedDegrader). This is the same pipeline tests use; it's
           a sensible default for production but should become
           configurable when more degraders land (T5+).
        3. :meth:`PlannerService.plan_reverse` runs the standard plan
           and then merges the ladder rationales into each stage's
           ``gem_changes`` list, prefixed with ``[target_name]`` so the
           UI can group/filter them.
        """

        from .planner.templates import pick_template
        from .reverse import (
            AwakenedGemDegrader,
            CompositeDegrader,
            HardcodedDegrader,
            InfluenceItemDegrader,
        )

        async with HttpClient(settings) as http:
            build, _ = await _resolve_pob_to_build(payload.input, http=http)

            pricing = PricingService(http=http, league=settings.poe_league)
            trade = TradeSource(http=http, league=settings.poe_league)
            degrader = CompositeDegrader(
                [
                    AwakenedGemDegrader(),
                    HardcodedDegrader(),
                    InfluenceItemDegrader(),
                ]
            )
            planner = PlannerService(pricing, trade=trade, degrader=degrader)
            plan = await planner.plan_reverse(build, target_goal=payload.target_goal)
            template_name = pick_template(build).name

        log.info(
            "fob_plan_reverse_ok",
            source_id=build.source_id,
            target_goal=payload.target_goal.value,
            template_name=template_name,
            key_items=len(build.key_items),
            stages=len(plan.stages),
            total_min_div=plan.total_estimated_cost.min.amount,
            total_max_div=plan.total_estimated_cost.max.amount,
        )
        return PlanResponse(build=build, plan=plan, template_name=template_name)

    @router.post(
        "/plan/stream",
        summary=(
            "Stream the plan generation as Server-Sent Events. Each event "
            "is a PricingProgress JSON; the final 'done' event carries the "
            "full BuildPlan in its final_plan field."
        ),
    )
    async def plan_stream_endpoint(
        payload: Annotated[PlanRequest, Body()],
    ) -> StreamingResponse:
        """SSE-streamed planning.

        The body is the same :class:`PlanRequest` used by ``/plan``.
        The response is ``text/event-stream`` with one ``data:``-prefixed
        JSON event per :class:`PricingProgress`. The browser's
        ``EventSource`` API consumes these directly.

        We deliberately resolve the PoB before opening the stream so a
        bad input fails fast with the regular HTTPException semantics
        (400 / 422 / 502) rather than mid-stream. Pricing happens inside
        the streamed generator where progress events naturally surface.
        """

        # Resolve the PoB synchronously up-front so input errors return
        # a clean HTTP error rather than a half-opened SSE stream.
        async with HttpClient(settings) as http:
            build, _ = await _resolve_pob_to_build(payload.input, http=http)

        async def event_source() -> AsyncIterator[str]:
            async with HttpClient(settings) as http:
                pricing = PricingService(http=http, league=settings.poe_league)
                trade = TradeSource(http=http, league=settings.poe_league)
                planner = PlannerService(pricing, trade=trade)
                async for event in planner.plan_with_progress(
                    build, target_goal=payload.target_goal
                ):
                    yield _sse_format(event)
                log.info(
                    "fob_plan_stream_ok",
                    source_id=build.source_id,
                    target_goal=payload.target_goal.value,
                )

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                # Disable proxy buffering so events flush immediately.
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post(
        "/plan/reverse/stream",
        summary=(
            "Stream the reverse-progression plan as Server-Sent Events. "
            "Same shape as /plan/stream, but the final 'done' event's "
            "BuildPlan carries per-item ladder rationales (Step 13.C)."
        ),
    )
    async def plan_reverse_stream_endpoint(
        payload: Annotated[PlanRequest, Body()],
    ) -> StreamingResponse:
        """SSE-streamed reverse-progression planning.

        Same input/event shape as ``/plan/stream``: one progress event
        per :class:`KeyItem` priced + start/done bookends. The ``done``
        event's ``final_plan`` is post-processed via
        :meth:`PlannerService._merge_ladder_advice` so consumers see the
        merged plan with ``[target] rationale`` lines in
        ``gem_changes`` already included — no second round-trip.
        """

        from .reverse import (
            AwakenedGemDegrader,
            CompositeDegrader,
            HardcodedDegrader,
            InfluenceItemDegrader,
        )

        async with HttpClient(settings) as http:
            build, _ = await _resolve_pob_to_build(payload.input, http=http)

        async def event_source() -> AsyncIterator[str]:
            async with HttpClient(settings) as http:
                pricing = PricingService(http=http, league=settings.poe_league)
                trade = TradeSource(http=http, league=settings.poe_league)
                degrader = CompositeDegrader(
                    [
                        AwakenedGemDegrader(),
                        HardcodedDegrader(),
                        InfluenceItemDegrader(),
                    ]
                )
                planner = PlannerService(pricing, trade=trade, degrader=degrader)
                async for event in planner.plan_reverse_with_progress(
                    build, target_goal=payload.target_goal
                ):
                    yield _sse_format(event)
                log.info(
                    "fob_plan_reverse_stream_ok",
                    source_id=build.source_id,
                    target_goal=payload.target_goal.value,
                    key_items=len(build.key_items),
                )

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @router.post(
        "/trade-url",
        response_model=TradeUrlResponse,
        summary=(
            "Build a pre-filled pathofexile.com/trade search URL for an "
            "item. Result is cached in-memory (TTL 8 min) keyed by query "
            "hash so repeat clicks on the same item don't hit GGG."
        ),
    )
    async def trade_url_endpoint(
        payload: Annotated[TradeUrlRequest, Body()],
    ) -> TradeUrlResponse:
        """Return a pre-filled GGG Trade search URL for ``payload``.

        Caches aggressively (TTL 8 min, ~10 min less than GGG's own
        search-id lifetime) so common items like Mageblood / Kaom's
        Heart hit the cache for the second user onward — no GGG call,
        no rate-limit consumption. On 429 the response carries
        ``source='rate_limited'`` and ``url=null`` so the frontend can
        fall back to opening the bare search page.
        """

        if not payload.item_name and not payload.item_type:
            raise HTTPException(
                status_code=422,
                detail="trade-url requires at least item_name or item_type",
            )

        # Extract numeric stat filters from the raw mod text. Lines that
        # don't match any MOD_PATTERNS entry are silently dropped.
        stats: list[StatFilter] = []
        if payload.mod_lines:
            cleaned = _clean_mod_lines(payload.mod_lines)
            extracted = _extract_mod_patterns(cleaned)
            seen: set[str] = set()
            for em in extracted:
                if em.stat_id in seen:
                    continue
                seen.add(em.stat_id)
                stats.append(StatFilter(stat_id=em.stat_id, min=em.value))

        # When we have a unique name, search by name (Trade resolves
        # the base automatically). When we have only a rare base, search
        # by type. Sending both confuses GGG's filter set.
        query = TradeQuery(
            name=payload.item_name,
            type=payload.item_type if not payload.item_name else None,
            stats=tuple(stats),
            online_only=True,
        )

        cache_key = hashlib.sha256(
            "|".join(
                [
                    settings.poe_league,
                    payload.item_name or "",
                    payload.item_type or "",
                    ",".join(sorted(f"{s.stat_id}:{s.min}" for s in stats)),
                ]
            ).encode("utf-8")
        ).hexdigest()[:24]

        if (cached := _trade_url_cache_get(cache_key)) is not None:
            log.info(
                "fob_trade_url_cache_hit",
                cache_key=cache_key,
                item_name=payload.item_name,
                item_type=payload.item_type,
                mods=len(stats),
            )
            return TradeUrlResponse(url=cached, source="cache")

        async with HttpClient(settings) as http:
            trade = TradeSource(http=http, league=settings.poe_league)
            try:
                search_id, _hashes, total = await trade.search(query)
            except HttpError as err:
                if err.status_code == 429:
                    log.warning(
                        "fob_trade_url_rate_limited",
                        item_name=payload.item_name,
                        item_type=payload.item_type,
                    )
                    return TradeUrlResponse(url=None, source="rate_limited")
                raise HTTPException(
                    status_code=502,
                    detail=f"GGG Trade search failed: {err}",
                ) from err

        url = f"https://www.pathofexile.com/trade/search/{settings.poe_league}/{search_id}"
        _trade_url_cache_set(cache_key, url)
        log.info(
            "fob_trade_url_fresh",
            cache_key=cache_key,
            item_name=payload.item_name,
            item_type=payload.item_type,
            mods=len(stats),
            total_listings=total,
        )
        return TradeUrlResponse(url=url, source="fresh")

    @router.get(
        "/tree-progression/{template_name}",
        response_model=TreeProgression | None,
        summary=(
            "Return the per-stage skill-tree progression for a build "
            "template (Step 14 — Pohx-style stage builds)."
        ),
    )
    async def tree_progression_endpoint(
        template_name: str,
    ) -> TreeProgression | None:
        """Look up the hand-curated tree progression for a template.

        Returns 404-shaped null when no progression has been authored
        yet for ``template_name`` — the frontend treats this as
        "tree non disponibile per questo template" and falls back
        to the gem advice.
        """

        prog = progression_for(template_name)
        log.info(
            "fob_tree_progression_lookup",
            template_name=template_name,
            found=prog is not None,
        )
        return prog

    @router.get(
        "/tree-progression/{template_name}/{stage_key}/url",
        summary=(
            "Build a passive-skill-tree share URL for a specific stage of a template's progression."
        ),
    )
    async def tree_progression_url_endpoint(
        template_name: str,
        stage_key: str,
        character_class: str = "Marauder",
        ascendancy: str | None = None,
    ) -> dict[str, str | None]:
        """Encode the stage's node set into a pathofexile.com tree URL."""

        prog = progression_for(template_name)
        if prog is None:
            return {"url": None}
        stage = prog.for_stage(stage_key)
        if stage is None:
            return {"url": None}
        url = stage.pob_url or encode_pob_tree_url(
            node_ids=stage.node_ids,
            character_class=character_class,
            ascendancy=ascendancy,
        )
        return {"url": url}

    @router.get(
        "/gear-progression/{template_name}",
        response_model=GearProgression | None,
        summary=(
            "Return the per-stage gear specification for a build template "
            "(Step 14 T2 — Pohx-style stage gear suite)."
        ),
    )
    async def gear_progression_endpoint(
        template_name: str,
    ) -> GearProgression | None:
        """Look up the hand-curated gear progression for a template."""

        prog = gear_progression_for(template_name)
        log.info(
            "fob_gear_progression_lookup",
            template_name=template_name,
            found=prog is not None,
        )
        return prog

    @router.get(
        "/gem-progression/{template_name}",
        response_model=GemProgression | None,
        summary=(
            "Return the per-stage gem-link progression for a build template "
            "(Step 14 T3 — Pohx-style stage gem setup)."
        ),
    )
    async def gem_progression_endpoint(
        template_name: str,
    ) -> GemProgression | None:
        """Look up the hand-curated gem progression for a template.

        Returns null when no progression has been authored. The frontend
        falls back to the free-form ``gem_changes`` strings already on
        each PlanStage.
        """

        prog = gem_progression_for(template_name)
        log.info(
            "fob_gem_progression_lookup",
            template_name=template_name,
            found=prog is not None,
        )
        return prog

    def _compose_stage_export(
        *,
        template_name: str,
        stage_key: str,
        character_class: str,
        ascendancy: str | None,
        level: int,
        user_pob_code: str | None,
    ) -> StageExportResponse:
        """Compose a Stage Export response.

        Tries in order:
        1. Curated TreeProgression for ``template_name`` (Step 14 T1).
        2. User's original PoB code, decoded to extract its allocated
           node set (fallback when 1 fails — preserves the user's
           actual tree).
        3. Empty tree spec (last resort — PoB still imports a valid code,
           the user keeps whatever tree they have open in PoB desktop).

        Gear and gem progressions are optional in all paths.
        """

        # Decode the user's PoB once at the top — reused by both the
        # tree fallback (user_pob source) and the dynamic gem
        # progression (Step 18).
        snapshot: PobSnapshot | None = None
        if user_pob_code:
            try:
                snapshot = parse_snapshot(
                    decode_export(user_pob_code),
                    export_code=user_pob_code,
                )
            except (PobParseError, ValueError) as err:
                log.warning(
                    "fob_stage_export_user_pob_decode_failed",
                    template_name=template_name,
                    stage_key=stage_key,
                    error=str(err),
                )
                snapshot = None

        tree_prog = progression_for(template_name)
        stage_tree = tree_prog.for_stage(stage_key) if tree_prog is not None else None
        tree_source: str
        if stage_tree is not None:
            tree_source = "progression"
        elif snapshot is not None:
            # Pass mastery_effects through so PoB doesn't silently
            # drop the user's mastery nodes on import (PoB rejects
            # any mastery in ``nodes=`` that isn't also in
            # ``masteryEffects=``).
            stage_tree = StageTree(
                stage_key=stage_key,
                node_ids=tuple(snapshot.tree.node_ids),
                mastery_effects=tuple(snapshot.tree.mastery_effects.items()),
            )
            tree_source = "user_pob"
        else:
            tree_source = "empty"

        gear_prog = gear_progression_for(template_name)
        stage_gear = gear_prog.for_stage(stage_key) if gear_prog is not None else None

        # Step 18 — dynamic gem progression derived from user PoB takes
        # precedence over the curated registry. The registry remains the
        # fallback for builds without a pasted PoB.
        stage_gems = None
        if snapshot is not None:
            dyn_prog = derive_gem_progression(snapshot, target_name=template_name)
            if dyn_prog is not None:
                stage_gems = dyn_prog.for_stage(stage_key)
        if stage_gems is None:
            curated_prog = gem_progression_for(template_name)
            stage_gems = curated_prog.for_stage(stage_key) if curated_prog is not None else None

        code = encode_pob_code(
            character_class=character_class,
            ascendancy=ascendancy,
            tree=stage_tree,
            gear=stage_gear,
            gems=stage_gems,
            level=level,
            passthrough_user_pob=user_pob_code,
        )
        log.info(
            "fob_stage_export_ok",
            template_name=template_name,
            stage_key=stage_key,
            character_class=character_class,
            tree_source=tree_source,
            has_gear=stage_gear is not None,
            has_gems=stage_gems is not None,
            has_passthrough=user_pob_code is not None,
        )
        return StageExportResponse(
            code=code,
            stage_key=stage_key,
            template_name=template_name,
            tree_source=tree_source,
        )

    @router.get(
        "/stage-export/{template_name}/{stage_key}",
        response_model=StageExportResponse,
        summary=(
            "Build a PathOfBuilding-importable code combining the tree, gear "
            "and gem-link progressions for a single stage of a template."
        ),
    )
    async def stage_export_endpoint(
        template_name: str,
        stage_key: str,
        character_class: str = "Marauder",
        ascendancy: str | None = None,
        level: int = 90,
    ) -> StageExportResponse:
        """Compose a Step 14 PoB export code for one stage.

        GET variant: no user_pob_code fallback. When the template has
        no curated tree progression, the exported code carries an empty
        tree spec — PoB still imports it, but the user loses their tree.
        Prefer the POST variant when you can supply the original PoB.
        """

        return _compose_stage_export(
            template_name=template_name,
            stage_key=stage_key,
            character_class=character_class,
            ascendancy=ascendancy,
            level=level,
            user_pob_code=None,
        )

    @router.post(
        "/stage-export",
        response_model=StageExportResponse,
        summary=(
            "Build a PathOfBuilding-importable code for a stage, with the "
            "user's original PoB tree as a fallback when no curated "
            "TreeProgression is registered for the template."
        ),
    )
    async def stage_export_post_endpoint(
        payload: Annotated[StageExportRequest, Body()],
    ) -> StageExportResponse:
        """POST variant of /stage-export with user_pob_code fallback.

        Exists because 47/49 BuildTemplates don't yet ship a curated
        TreeProgression (only ``rf_pohx`` and ``spectre_necromancer``
        do as of Step 14 T5). For those builds, decoding the user's
        original PoB and re-using its allocated nodes gives an import
        that doesn't wipe their tree.
        """

        return _compose_stage_export(
            template_name=payload.template_name,
            stage_key=payload.stage_key,
            character_class=payload.character_class,
            ascendancy=payload.ascendancy,
            level=payload.level,
            user_pob_code=payload.user_pob_code,
        )

    # POST /fob/extract-trade-mods removed alongside /trade-search.
    # It only existed to populate the deleted TradeSearchDialog mod
    # filter list. The MOD_PATTERNS table is still used internally by
    # the planner's Trade pricer (see _matches_rf in templates.py and
    # _price_combo_unique in planner/service.py).

    return router


__all__ = [
    "AnalyzePobRequest",
    "AnalyzePobResponse",
    "ExtractIntentRequest",
    "make_router",
]
