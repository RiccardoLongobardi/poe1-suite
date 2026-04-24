"""FastAPI router for the pricing endpoints.

Exposes two reads against the configured league:

* ``GET /pricing/quote?name=...&category=...`` — single-item lookup
  across categories (or a specific one if supplied).
* ``GET /pricing/snapshot?category=...`` — full category listing.

The router is stateless apart from the settings it captures at
construction time; each request opens a short-lived ``HttpClient`` so a
hung upstream can't starve subsequent calls. The HTTP layer's on-disk
cache absorbs the cost of reopening.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from poe1_shared.config import Settings
from poe1_shared.http import HttpClient, HttpError
from poe1_shared.logging import get_logger

from .models import ItemCategory, PriceQuote, PriceSnapshot
from .service import PricingService
from .sources.ninja import NinjaSourceError

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------


class QuoteResponse(BaseModel):
    """Envelope for ``GET /pricing/quote``."""

    model_config = ConfigDict(frozen=True)

    league: str
    queried_at: datetime
    quote: PriceQuote | None


class SnapshotResponse(BaseModel):
    """Envelope for ``GET /pricing/snapshot``.

    We don't return the full :class:`PriceSnapshot` body when large —
    this is an API convenience response, not the canonical cache.
    """

    model_config = ConfigDict(frozen=True)

    league: str
    category: ItemCategory
    version: str
    fetched_at: datetime
    count: int
    quotes: tuple[PriceQuote, ...]


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def make_router(settings: Settings) -> APIRouter:
    """Build the ``/pricing`` router for the server to mount."""

    router = APIRouter(prefix="/pricing", tags=["pricing"])

    @router.get(
        "/quote",
        response_model=QuoteResponse,
        summary="Look up a single item or currency price by name.",
    )
    async def get_quote(
        name: Annotated[str, Query(min_length=1, description="Item or currency name.")],
        category: Annotated[
            ItemCategory | None,
            Query(
                description=(
                    "Restrict the search to one category. Omit to walk all "
                    "categories (currency -> uniques -> commoditised)."
                ),
            ),
        ] = None,
        league: Annotated[
            str | None,
            Query(description="Override the configured league for this query."),
        ] = None,
    ) -> QuoteResponse:
        effective_league = league or settings.poe_league
        try:
            async with HttpClient(settings) as http:
                service = PricingService(http=http, league=effective_league)
                quote = await service.quote_by_name(name, category=category)
        except NinjaSourceError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except HttpError as err:
            raise HTTPException(status_code=502, detail=f"upstream: {err}") from err

        fetched = quote.fetched_at if quote is not None else datetime.now(tz=UTC)
        log.info(
            "pricing_quote",
            name=name,
            hit=quote is not None,
            category=category.value if category else "any",
            league=effective_league,
        )
        return QuoteResponse(league=effective_league, queried_at=fetched, quote=quote)

    @router.get(
        "/snapshot",
        response_model=SnapshotResponse,
        summary="Fetch a full category price snapshot.",
    )
    async def get_snapshot(
        category: Annotated[ItemCategory, Query(description="poe.ninja overview type.")],
        league: Annotated[
            str | None,
            Query(description="Override the configured league for this query."),
        ] = None,
    ) -> SnapshotResponse:
        effective_league = league or settings.poe_league
        try:
            async with HttpClient(settings) as http:
                service = PricingService(http=http, league=effective_league)
                snapshot: PriceSnapshot = await service.snapshot(category)
        except NinjaSourceError as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except HttpError as err:
            raise HTTPException(status_code=502, detail=f"upstream: {err}") from err

        log.info(
            "pricing_snapshot",
            category=category.value,
            league=effective_league,
            count=len(snapshot.quotes),
        )
        return SnapshotResponse(
            league=snapshot.league,
            category=snapshot.category,
            version=snapshot.version,
            fetched_at=snapshot.fetched_at,
            count=len(snapshot.quotes),
            quotes=snapshot.quotes,
        )

    return router


__all__ = ["QuoteResponse", "SnapshotResponse", "make_router"]
