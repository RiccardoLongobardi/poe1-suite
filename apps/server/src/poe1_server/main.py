"""FastAPI application factory and CLI entrypoint.

This module intentionally stays thin. Each tool package registers its
own router via ``make_router(settings)`` and it is mounted here behind
the tool's prefix.
"""

from __future__ import annotations

import os
from time import monotonic, time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    # Production sanity: force JSON logging when env is production
    # unless the operator has explicitly overridden ``log_format``.
    # Keeps Fly.io / log aggregators happy out of the box.
    if settings.environment == "production" and settings.log_format == "console":
        settings = settings.model_copy(update={"log_format": "json"})

    configure_logging(settings)
    log = get_logger(__name__)

    app = FastAPI(
        title="poe1-suite",
        version=server_version,
        summary="Unified API for all PoE 1 tools in poe1-suite.",
    )

    # CORS: required for the deployed frontend (Vercel) to call this
    # backend (Fly.io) cross-origin. Empty list in development means
    # the middleware is not mounted (the dev frontend uses Vite's
    # built-in proxy on the same host so no CORS is needed).
    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=False,  # we don't use cookies
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "Accept"],
            max_age=3600,
        )
        log.info("cors_enabled", origins=settings.cors_allowed_origins)

    started_at = monotonic()

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, object]:
        """Liveness + readiness probe.

        Returns the minimal info Fly.io / UptimeRobot need to verify
        the process is up: status, current league, server version,
        env, and uptime in seconds. No upstream calls.
        """

        return {
            "status": "ok",
            "environment": settings.environment,
            "league": settings.poe_league,
            "version": server_version,
            "uptime_seconds": round(monotonic() - started_at, 1),
            "timestamp": int(time()),
        }

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
        environment=settings.environment,
        league=settings.poe_league,
        log_level=settings.log_level,
        log_format=settings.log_format,
        cors_origins_count=len(settings.cors_allowed_origins),
        anthropic_llm_enabled=settings.anthropic_api_key is not None,
        http_max_concurrent_per_host=settings.http_max_concurrent_per_host,
    )
    return app


def run() -> None:
    """Uvicorn entrypoint used by the ``poe1-server`` console script.

    Reads ``HOST`` / ``PORT`` from the environment so the same binary
    works locally (defaults: 127.0.0.1:8765) and in containers
    (Fly.io sets ``PORT=8080`` and we must bind to ``0.0.0.0``).
    """

    import uvicorn

    settings = Settings()
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))

    uvicorn.run(
        "poe1_server.main:create_app",
        factory=True,
        host=host,
        port=port,
        log_level=settings.log_level.lower(),
        reload=False,
    )


__all__ = ["create_app", "run"]
