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
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from poe1_core.models import Build
from poe1_core.models.build_intent import BuildIntent
from poe1_pricing import PricingService, StatFilter, TradeQuery, TradeSource
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from .intent import IntentLlmError, extract_intent
from .planner import (
    ExtractedTradeMod,
    PlannerService,
    PlanRequest,
    PlanResponse,
    PricingProgress,
    TradeModExtractRequest,
    TradeModExtractResponse,
    TradeSearchRequest,
    TradeSearchResponse,
)
from .pob import (
    PobInputError,
    PobParseError,
    PobSnapshot,
    decode_export,
    load_pob,
    parse_snapshot,
    snapshot_to_build,
)
from .pob import clean_mod_lines as _clean_mod_lines
from .pob import extract_mods as _extract_mod_patterns
from .ranking import RankingEngine, RecommendRequest, RecommendResponse, SourceAggregator

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


# ---------------------------------------------------------------------------
# Helpers
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

        async with HttpClient(settings) as http:
            build, _ = await _resolve_pob_to_build(payload.input, http=http)

            pricing = PricingService(http=http, league=settings.poe_league)
            trade = TradeSource(http=http, league=settings.poe_league)
            planner = PlannerService(pricing, trade=trade)
            plan = await planner.plan(build, target_goal=payload.target_goal)

        log.info(
            "fob_plan_ok",
            source_id=build.source_id,
            target_goal=payload.target_goal.value,
            stages=len(plan.stages),
            total_min_div=plan.total_estimated_cost.min.amount,
            total_max_div=plan.total_estimated_cost.max.amount,
        )
        return PlanResponse(build=build, plan=plan)

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

        from .reverse import AwakenedGemDegrader, CompositeDegrader, HardcodedDegrader

        async with HttpClient(settings) as http:
            build, _ = await _resolve_pob_to_build(payload.input, http=http)

            pricing = PricingService(http=http, league=settings.poe_league)
            trade = TradeSource(http=http, league=settings.poe_league)
            degrader = CompositeDegrader([AwakenedGemDegrader(), HardcodedDegrader()])
            planner = PlannerService(pricing, trade=trade, degrader=degrader)
            plan = await planner.plan_reverse(build, target_goal=payload.target_goal)

        log.info(
            "fob_plan_reverse_ok",
            source_id=build.source_id,
            target_goal=payload.target_goal.value,
            key_items=len(build.key_items),
            stages=len(plan.stages),
            total_min_div=plan.total_estimated_cost.min.amount,
            total_max_div=plan.total_estimated_cost.max.amount,
        )
        return PlanResponse(build=build, plan=plan)

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
        "/trade-search",
        response_model=TradeSearchResponse,
        summary=(
            "Build a pre-filled GGG Trade search from a focused mod selection "
            "and return the share URL the frontend can open in a new tab."
        ),
    )
    async def trade_search_endpoint(
        payload: Annotated[TradeSearchRequest, Body()],
    ) -> TradeSearchResponse:
        """Mirror of poe.ninja's character trade search.

        The frontend extracts mods from an analyzed PoB / planned item,
        lets the user toggle which ones to require and adjust the
        strictness slider, then submits the assembled filter spec
        here. We POST it to GGG's ``/api/trade/search/<league>`` and
        return the share URL — the same one
        ``https://www.pathofexile.com/trade/search/<league>/<id>``
        the Trade UI itself uses.

        We deliberately don't fetch listings: this endpoint exists so
        the user can inspect / negotiate / buy on the official trade
        site. Pricing remains the planner's job.
        """

        # Reject empty queries up-front. GGG would happily run them
        # but the result list (every rare in the league) is useless and
        # wastes a rate-limit token.
        if not payload.item_name and not payload.item_type and not payload.mods:
            raise HTTPException(
                status_code=422,
                detail="trade-search requires at least a name, type, or one mod filter",
            )

        stats = tuple(StatFilter(stat_id=m.stat_id, min=m.min, max=m.max) for m in payload.mods)
        # Optional 6L / 5L socket filter goes in the GGG ``filters``
        # bag rather than as a stat.
        extra_filters: dict[str, dict[str, dict[str, dict[str, int]]]] | None = None
        if payload.min_links is not None:
            extra_filters = {
                "socket_filters": {
                    "filters": {"links": {"min": payload.min_links}},
                },
            }
        query = TradeQuery(
            name=payload.item_name,
            type=payload.item_type,
            stats=stats,
            online_only=payload.online_only,
            extra_filters=extra_filters,
        )

        async with HttpClient(settings) as http:
            trade = TradeSource(http=http, league=settings.poe_league)
            try:
                search_id, _hashes, total = await trade.search(query)
            except HttpError as err:
                raise HTTPException(
                    status_code=502,
                    detail=f"GGG Trade search failed: {err}",
                ) from err

        url = f"https://www.pathofexile.com/trade/search/{settings.poe_league}/{search_id}"

        log.info(
            "fob_trade_search_ok",
            league=settings.poe_league,
            search_id=search_id,
            total=total,
            mods=len(payload.mods),
            has_name=bool(payload.item_name),
            has_type=bool(payload.item_type),
        )
        return TradeSearchResponse(
            league=settings.poe_league,
            search_id=search_id,
            url=url,
            total_listings=total,
        )

    @router.post(
        "/extract-trade-mods",
        response_model=TradeModExtractResponse,
        summary=(
            "Run the rare-mod pattern table over a list of mod text "
            "lines and return the dialog-ready filter rows."
        ),
    )
    async def extract_trade_mods_endpoint(
        payload: Annotated[TradeModExtractRequest, Body()],
    ) -> TradeModExtractResponse:
        """Pure-extraction preview for the Trade-search dialog.

        The frontend sends the verbatim mod text lines from a CoreItem
        (or any other PoB-derived item) and gets back the rows ready
        to render: ``stat_id``, label, rolled value. Mod lines that
        don't match any pattern in :data:`MOD_PATTERNS` are silently
        dropped — no point surfacing rolls we can't query on Trade.

        Stateless and offline: no HTTP calls, no rate limit.
        """

        cleaned = _clean_mod_lines(payload.mods)
        extracted = _extract_mod_patterns(cleaned)
        # Dedupe by stat_id, keeping the first seen — same dedup rule
        # the pricing layer uses, so the dialog matches the pricer.
        seen: set[str] = set()
        out: list[ExtractedTradeMod] = []
        for em in extracted:
            if em.stat_id in seen:
                continue
            seen.add(em.stat_id)
            out.append(
                ExtractedTradeMod(
                    line=em.line,
                    stat_id=em.stat_id,
                    value=em.value,
                    label=em.label,
                )
            )
        return TradeModExtractResponse(mods=tuple(out))

    return router


__all__ = [
    "AnalyzePobRequest",
    "AnalyzePobResponse",
    "ExtractIntentRequest",
    "make_router",
]
