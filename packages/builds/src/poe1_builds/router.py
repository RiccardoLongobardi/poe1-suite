"""FastAPI router for the /builds endpoints.

Two reads, both against the configured (or overridden) league:

* ``GET /builds/list`` — refs-only listing with server- and post-fetch
  filters. When ``main_skill`` / ``defense_type`` are supplied the
  router hydrates the fan-out and applies the two post-fetch filters
  before returning. Hydration is bounded via the service's semaphore
  (concurrency=4) so a loose filter can't hammer poe.ninja.
* ``GET /builds/detail`` — single-character hydration. Takes the
  ``account`` + ``name`` pair that uniquely identifies a row in
  ``buildLeagues``. ``league`` is optional (falls back to the server's
  configured league).

The router is stateless — each request opens a fresh :class:`HttpClient`
and closes it when done, matching the pricing router pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from poe1_shared.config import Settings
from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from .models import (
    BuildFilter,
    DefenseType,
    FullBuild,
    RemoteBuildRef,
)
from .service import BuildsService
from .sources.ninja import NinjaBuildsSourceError

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response envelopes
# ---------------------------------------------------------------------------


class BuildsListResponse(BaseModel):
    """Envelope for ``GET /builds/list``."""

    model_config = ConfigDict(frozen=True)

    league: str
    snapshot_version: str
    queried_at: datetime
    total: int  # server-reported total before post-fetch filters
    count: int  # size of the returned refs tuple
    refs: tuple[RemoteBuildRef, ...]


class BuildDetailResponse(BaseModel):
    """Envelope for ``GET /builds/detail``."""

    model_config = ConfigDict(frozen=True)

    league: str
    queried_at: datetime
    build: FullBuild


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def make_router(settings: Settings) -> APIRouter:
    """Build the ``/builds`` router for the server to mount."""

    router = APIRouter(prefix="/builds", tags=["builds"])

    @router.get(
        "/list",
        response_model=BuildsListResponse,
        summary="List builds for the league with optional filters.",
    )
    async def list_builds(
        class_: Annotated[
            str | None,
            Query(
                alias="class",
                description="Restrict to a single ascendancy (e.g. 'Slayer').",
            ),
        ] = None,
        main_skill: Annotated[
            str | None,
            Query(
                min_length=1,
                description=(
                    "Case-insensitive substring match against the computed "
                    "main skill. Forces hydration — slow on large fan-outs."
                ),
            ),
        ] = None,
        level_min: Annotated[
            int | None,
            Query(ge=1, le=100, description="Minimum character level (inclusive)."),
        ] = None,
        level_max: Annotated[
            int | None,
            Query(ge=1, le=100, description="Maximum character level (inclusive)."),
        ] = None,
        defense_type: Annotated[
            DefenseType | None,
            Query(
                description=(
                    "Defensive-layer classification applied post-hydration. "
                    "Forces hydration — slow on large fan-outs."
                ),
            ),
        ] = None,
        top_n_per_class: Annotated[
            int,
            Query(
                ge=1,
                le=2000,
                description="Cap refs returned per ascendancy (server limit is 100).",
            ),
        ] = 200,
        league: Annotated[
            str | None,
            Query(description="Override the configured league for this query."),
        ] = None,
    ) -> BuildsListResponse:
        effective_league = league or settings.poe_league

        level_range: tuple[int, int] | None = None
        if level_min is not None and level_max is not None:
            if level_min > level_max:
                raise HTTPException(
                    status_code=422,
                    detail=f"level_min ({level_min}) > level_max ({level_max})",
                )
            level_range = (level_min, level_max)
        elif (level_min is None) != (level_max is None):
            raise HTTPException(
                status_code=422,
                detail="level_min and level_max must be supplied together",
            )

        filt = BuildFilter(
            class_=class_,
            main_skill=main_skill,
            level_range=level_range,
            defense_type=defense_type,
            top_n_per_class=top_n_per_class,
        )

        try:
            async with HttpClient(settings) as http:
                service = BuildsService(http=http, league=effective_league)
                snapshot = await service.fetch_refs(filt)

                refs = snapshot.refs
                # Post-fetch filters that need the hydrated payload.
                if main_skill or defense_type is not None:
                    builds = await service.hydrate(refs, concurrency=4)
                    kept: list[RemoteBuildRef] = []
                    for ref, build in zip(refs, builds, strict=True):
                        if main_skill and not BuildsService.matches_main_skill(build, main_skill):
                            continue
                        if defense_type is not None and not BuildsService.matches_defense_type(
                            build, defense_type
                        ):
                            continue
                        kept.append(ref)
                    refs = tuple(kept)
        except NinjaBuildsSourceError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except HttpError as err:
            raise HTTPException(status_code=502, detail=f"upstream: {err}") from err

        log.info(
            "builds_list",
            league=effective_league,
            class_filter=class_,
            main_skill=main_skill,
            defense_type=defense_type.value if defense_type else None,
            total=snapshot.total,
            returned=len(refs),
        )
        return BuildsListResponse(
            league=snapshot.league,
            snapshot_version=snapshot.snapshot_version,
            queried_at=snapshot.fetched_at,
            total=snapshot.total,
            count=len(refs),
            refs=refs,
        )

    @router.get(
        "/detail",
        response_model=BuildDetailResponse,
        summary="Hydrate a single character to a FullBuild.",
    )
    async def get_detail(
        account: Annotated[str, Query(min_length=1, description="poe.ninja account name.")],
        name: Annotated[str, Query(min_length=1, description="Character name.")],
        league: Annotated[
            str | None,
            Query(description="Override the configured league for this query."),
        ] = None,
    ) -> BuildDetailResponse:
        effective_league = league or settings.poe_league
        try:
            async with HttpClient(settings) as http:
                service = BuildsService(http=http, league=effective_league)
                # Synthesize a minimal ref — fetch_build_detail only uses
                # account / character / league to drive the character
                # endpoint. The rest is bookkeeping injected post-fetch.
                ref = RemoteBuildRef.model_validate(
                    {
                        "source_id": f"ninja::{effective_league}::{account}::{name}",
                        "account": account,
                        "character": name,
                        "class": "",
                        "level": 1,
                        "life": 0,
                        "energy_shield": 0,
                        "ehp": 0,
                        "dps": 0,
                        "main_skill": None,
                        "league": effective_league,
                        "snapshot_version": "",
                        "fetched_at": datetime.now(tz=UTC),
                    }
                )
                build = await service.get_detail(ref)
        except NinjaBuildsSourceError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except HttpError as err:
            status = 502
            text = str(err)
            # A 404 from poe.ninja for an unknown character should bubble
            # up as a 404 to the caller, not a 502.
            if "404" in text:
                status = 404
            raise HTTPException(status_code=status, detail=f"upstream: {err}") from err

        log.info(
            "builds_detail",
            league=effective_league,
            account=account,
            name=name,
        )
        return BuildDetailResponse(
            league=build.league,
            queried_at=datetime.now(tz=UTC),
            build=build,
        )

    return router


__all__ = ["BuildDetailResponse", "BuildsListResponse", "make_router"]
