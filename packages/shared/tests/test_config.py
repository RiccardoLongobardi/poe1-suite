"""Tests for poe1_shared.config.Settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from poe1_shared.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """With no env set, defaults are sane."""

    # Neutralise any env that might be present in the CI runner.
    for key in (
        "POE_LEAGUE",
        "POE_NINJA_BASE_URL",
        "POESESSID",
        "ANTHROPIC_API_KEY",
        "LOG_LEVEL",
        "LOG_FORMAT",
        "CACHE_DIR",
        "HTTP_TIMEOUT_SECONDS",
        "HTTP_MAX_RETRIES",
        "HTTP_CACHE_TTL_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)

    # Ensure no project-level .env influences the test.
    monkeypatch.chdir(tmp_path)

    settings = Settings()
    assert settings.poe_league == "Standard"
    assert str(settings.poe_ninja_base_url).startswith("https://poe.ninja")
    assert settings.log_level == "INFO"
    assert settings.http_timeout_seconds == 15.0
    assert settings.http_max_retries == 3


def test_env_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("POE_LEAGUE", "Settlers")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("HTTP_MAX_RETRIES", "5")

    settings = Settings()
    assert settings.poe_league == "Settlers"
    assert settings.log_level == "DEBUG"
    assert settings.http_max_retries == 5


def test_invalid_log_level_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LOG_LEVEL", "NOISY")
    with pytest.raises(ValidationError):
        Settings()


def test_ensure_cache_dir_creates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "deep" / "nested"))
    settings = Settings()
    path = settings.ensure_cache_dir()
    assert path.exists() and path.is_dir()


# Production hardening (Fase 1) ----------------------------------


def test_environment_default_is_development(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default ``environment`` is ``development``."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert Settings().environment == "development"


def test_environment_production_via_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert Settings().environment == "production"


def test_cors_origins_csv_parses_into_list(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CORS_ALLOWED_ORIGINS=https://a.com,https://b.com → list[str]."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "https://fob.vercel.app, https://fob.tools",
    )
    settings = Settings()
    assert settings.cors_allowed_origins == [
        "https://fob.vercel.app",
        "https://fob.tools",
    ]


def test_cors_origins_empty_string_yields_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "")
    assert Settings().cors_allowed_origins == []


def test_cors_origins_default_is_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    assert Settings().cors_allowed_origins == []


def test_http_max_concurrent_per_host_default_and_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HTTP_MAX_CONCURRENT_PER_HOST", raising=False)
    assert Settings().http_max_concurrent_per_host == 4

    monkeypatch.setenv("HTTP_MAX_CONCURRENT_PER_HOST", "8")
    assert Settings().http_max_concurrent_per_host == 8
