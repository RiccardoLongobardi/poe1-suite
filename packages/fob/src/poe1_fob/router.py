"""FastAPI router for the FOB (Frusta Oracle Builder) endpoints.

This module exposes:

* ``POST /fob/analyze-pob`` — resolves a raw PoB code or pobb.in / pastebin
  share URL into a :class:`poe1_core.Build` plus the full :class:`PobSnapshot`.
* ``POST /fob/extract-intent`` — converts a free-text query (IT or EN) into a
  strongly-typed :class:`poe1_core.BuildIntent` using the hybrid rule-based +
  LLM fallback pipeline.

Keep all HTTP-shaped types (request/response models) local to this file
so the core domain models don't pick up FastAPI/OpenAPI concerns.
"""

from __future__ import annotations

import hashlib
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from poe1_core.models import Build
from poe1_core.models.build_intent import BuildIntent
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from .intent import IntentLlmError, extract_intent
from .pob import (
    PobInputError,
    PobParseError,
    PobSnapshot,
    decode_export,
    load_pob,
    parse_snapshot,
    snapshot_to_build,
)

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


def _source_id_for(code: str) -> str:
    """Derive a stable build id from the export code.

    Same code => same id, so re-importing the same build is idempotent.
    """

    digest = hashlib.sha1(code.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"pob::{digest[:12]}"


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
        try:
            async with HttpClient(settings) as http:
                code, origin_url = await load_pob(payload.input, http=http)
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

        log.info(
            "fob_analyze_pob_ok",
            source_id=build.source_id,
            character_class=build.character_class,
            ascendancy=build.ascendancy,
            main_skill=build.main_skill,
            origin_url=origin_url,
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

    return router


__all__ = ["AnalyzePobRequest", "AnalyzePobResponse", "ExtractIntentRequest", "make_router"]
