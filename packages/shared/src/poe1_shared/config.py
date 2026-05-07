"""Runtime configuration loaded from environment (and optional .env).

All settings are validated at construction time via Pydantic. Modules
that need configuration should accept a :class:`Settings` instance in
their constructors rather than instantiating it themselves; this keeps
the unit-testable surface small.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    environment: Literal["development", "production"] = Field(
        default="development",
        description=(
            "Deployment environment marker. 'production' triggers JSON "
            "logging and stricter CORS defaults."
        ),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "console"
    cache_dir: Path = Field(default=Path(".cache_http"))
    http_timeout_seconds: float = Field(default=15.0, gt=0.0)
    http_max_retries: int = Field(default=3, ge=0, le=10)
    http_cache_ttl_seconds: int = Field(default=3600, ge=0)
    http_max_concurrent_per_host: int = Field(
        default=4,
        ge=1,
        le=64,
        description=(
            "Max in-flight HTTP requests per upstream host. Protects "
            "poe.ninja and the GGG Trade API from burst calls when "
            "multiple users plan builds simultaneously. 4 is a "
            "conservative default that fits inside both APIs' headroom."
        ),
    )
    user_agent: str = Field(
        default="poe1-suite/0.1 (contact: ric.longobardi@outlook.it)",
        description="User-Agent sent with every HTTP request — identifies us to external APIs.",
    )

    # --- CORS ---
    # ``NoDecode`` disables pydantic-settings' default JSON parsing of
    # list[str] env vars; the field_validator below splits the raw
    # comma-separated string into a list.
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        description=(
            "Origins allowed by the CORS middleware. In env, "
            "comma-separated list (e.g. 'https://fob.vercel.app'). "
            "Empty list in development means the dev frontend uses a "
            "Vite proxy on the same host. In production MUST list the "
            "deployed frontend URL."
        ),
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _split_csv_origins(cls, v: object) -> object:
        """Allow ``CORS_ALLOWED_ORIGINS=https://a.com,https://b.com`` in env.

        Pydantic v2 BaseSettings parses ``list[str]`` env vars as JSON
        by default, which forces operators to write ``'["..."]'`` —
        ergonomically painful for env files. This validator accepts
        comma-separated strings and splits them, falling back to JSON
        parsing for backward compatibility.
        """

        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            # If it looks like JSON, let pydantic handle it.
            if stripped.startswith("["):
                return v
            return [piece.strip() for piece in stripped.split(",") if piece.strip()]
        return v

    def ensure_cache_dir(self) -> Path:
        """Create :attr:`cache_dir` if it does not exist and return it."""

        path = self.cache_dir
        path.mkdir(parents=True, exist_ok=True)
        return path


__all__ = ["Settings"]
