"""poe1-shared — infrastructure shared by every tool in poe1-suite."""

from __future__ import annotations

__version__ = "0.1.0"

from .config import Settings
from .http import HttpClient, HttpError
from .logging import configure_logging, get_logger

__all__ = [
    "HttpClient",
    "HttpError",
    "Settings",
    "__version__",
    "configure_logging",
    "get_logger",
]
