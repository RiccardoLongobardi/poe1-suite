"""Runtime configuration loaded from environment (and optional .env).

All settings are validated at construction time via Pydantic. Modules
that need configuration should accept a :class:`Settings` instance in
their constructors rather than instantiating it themselves; this keeps
the unit-testable surface small.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- PoE league ---
    poe_league: str = Field(
        default="Standard",
        description="League slug used as a parameter against poe.ninja / GGG APIs.",
    )

    # --- poe.ninja ---
    poe_ninja_base_url: HttpUrl = Field(
        default=HttpUrl("https://poe.ninja/api/data"),
        description="Base URL for poe.ninja public JSON API.",
    )

    # --- GGG official APIs (optional) ---
    poesessid: SecretStr | None = Field(
        default=None,
        description="Optional POESESSID cookie for authenticated GGG API calls.",
    )

    # --- LLM (optional) ---
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key — required only for FOB Intent Engine LLM fallback.",
    )

    # --- App runtime ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "console"
    cache_dir: Path = Field(default=Path(".cache_http"))
    http_timeout_seconds: float = Field(default=15.0, gt=0.0)
    http_max_retries: int = Field(default=3, ge=0, le=10)
    http_cache_ttl_seconds: int = Field(default=3600, ge=0)
    user_agent: str = Field(
        default="poe1-suite/0.1 (contact: ric.longobardi@outlook.it)",
        description="User-Agent sent with every HTTP request — identifies us to external APIs.",
    )

    def ensure_cache_dir(self) -> Path:
        """Create :attr:`cache_dir` if it does not exist and return it."""

        path = self.cache_dir
        path.mkdir(parents=True, exist_ok=True)
        return path


__all__ = ["Settings"]
