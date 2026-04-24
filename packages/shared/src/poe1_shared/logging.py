"""Structured logging setup.

Every package in the suite calls :func:`configure_logging` once at
startup (idempotent) and uses :func:`get_logger` thereafter. Do not
configure the stdlib ``logging`` module directly in other modules.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

from .config import Settings

_CONFIGURED = False


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging + structlog.

    Safe to call multiple times; only the first call does work.
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    level = getattr(logging, settings.log_level)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    renderer: structlog.types.Processor
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    _CONFIGURED = True


def get_logger(name: str | None = None, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound with ``initial_values``."""

    # structlog is dynamically typed; assert the concrete wrapper we configured.
    return cast(
        "structlog.stdlib.BoundLogger",
        structlog.get_logger(name).bind(**initial_values),
    )


__all__ = ["configure_logging", "get_logger"]
