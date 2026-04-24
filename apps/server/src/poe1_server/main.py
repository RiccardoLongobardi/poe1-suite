"""FastAPI application factory and CLI entrypoint.

This module intentionally stays thin. Each tool package registers its
own router via ``make_router(settings)`` and it is mounted here behind
the tool's prefix.
"""

from __future__ import annotations

from fastapi import FastAPI

from poe1_builds import __version__ as builds_version
from poe1_builds.router import make_router as make_builds_router
from poe1_core import __version__ as core_version
from poe1_fob import __version__ as fob_version
from poe1_fob.router import make_router as make_fob_router
from poe1_pricing import __version__ as pricing_version
from poe1_pricing.router import make_router as make_pricing_router
from poe1_shared import __version__ as shared_version
from poe1_shared.config import Settings
from poe1_shared.logging import configure_logging, get_logger

from . import __version__ as server_version


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""

    settings = settings or Settings()
    configure_logging(settings)
    log = get_logger(__name__)

    app = FastAPI(
        title="poe1-suite",
        version=server_version,
        summary="Unified API for all PoE 1 tools in poe1-suite.",
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/version", tags=["system"])
    async def version() -> dict[str, str]:
        return {
            "server": server_version,
            "core": core_version,
            "shared": shared_version,
            "fob": fob_version,
            "pricing": pricing_version,
            "builds": builds_version,
        }

    app.include_router(make_fob_router(settings))
    app.include_router(make_pricing_router(settings))
    app.include_router(make_builds_router(settings))

    log.info(
        "server_ready",
        league=settings.poe_league,
        log_level=settings.log_level,
    )
    return app


def run() -> None:
    """Uvicorn entrypoint used by the ``poe1-server`` console script."""

    import uvicorn

    settings = Settings()
    uvicorn.run(
        "poe1_server.main:create_app",
        factory=True,
        host="127.0.0.1",
        port=8765,
        log_level=settings.log_level.lower(),
        reload=False,
    )


__all__ = ["create_app", "run"]
