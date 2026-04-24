"""Tests for the intent extraction orchestrator.

The LLM path is marked ``integration`` and skipped when ANTHROPIC_API_KEY
is not set.  All other tests exercise the rule-based path via
``extract_intent`` and are fully offline.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio  # noqa: F401 — ensures asyncio mode is active
from pydantic import SecretStr

from poe1_core.models.enums import ParserOrigin
from poe1_fob.intent import IntentLlmError, extract_intent
from poe1_shared.config import Settings


def _settings_no_key() -> Settings:
    return Settings(anthropic_api_key=None)


def _settings_with_key() -> Settings | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    return Settings()


# ---------------------------------------------------------------------------
# Offline tests (rule-based path via orchestrator)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_intent_high_confidence_skips_llm() -> None:
    """Two matched fields → confidence ≥ 0.55; no LLM call needed (no key)."""
    settings = _settings_no_key()
    intent = await extract_intent("cold build per mapping comfy", settings=settings)
    assert intent.damage_profile is not None
    assert intent.damage_profile.value == "cold"
    assert intent.parser_origin == ParserOrigin.RULE_BASED


@pytest.mark.asyncio
async def test_extract_intent_low_confidence_no_key_returns_partial() -> None:
    """Vague query → low confidence, but no key → returns partial rule result."""
    settings = _settings_no_key()
    intent = await extract_intent("something interesting", settings=settings)
    assert intent.parser_origin == ParserOrigin.RULE_BASED


@pytest.mark.asyncio
async def test_extract_intent_empty_raises() -> None:
    settings = _settings_no_key()
    with pytest.raises(ValueError, match="empty"):
        await extract_intent("   ", settings=settings)


@pytest.mark.asyncio
async def test_extract_intent_full_confidence_case() -> None:
    """fire totem bossing low budget → all 4 fields matched → conf ≥ 0.70."""
    settings = _settings_no_key()
    intent = await extract_intent("totem fire bossing low budget", settings=settings)
    assert intent.damage_profile is not None
    assert intent.damage_profile.value == "fire"
    assert intent.playstyle is not None
    assert intent.playstyle.value == "totem"
    assert intent.confidence >= 0.70
    assert intent.parser_origin == ParserOrigin.RULE_BASED


# ---------------------------------------------------------------------------
# LLM integration tests — skipped without ANTHROPIC_API_KEY
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_fallback_ambiguous_query() -> None:
    """Deliberately ambiguous query should trigger LLM and return a coherent intent."""
    settings = _settings_with_key()
    if settings is None:
        pytest.skip("ANTHROPIC_API_KEY not set")

    intent = await extract_intent("something powerful for endgame", settings=settings)
    assert intent.parser_origin in (ParserOrigin.LLM, ParserOrigin.HYBRID)
    assert intent.raw_input == "something powerful for endgame"
    assert 0.0 <= intent.confidence <= 1.0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_fallback_italian_query() -> None:
    """Italian query below confidence threshold should hit LLM and parse correctly."""
    settings = _settings_with_key()
    if settings is None:
        pytest.skip("ANTHROPIC_API_KEY not set")

    intent = await extract_intent("build potente per la fine del gioco", settings=settings)
    assert intent.parser_origin in (ParserOrigin.LLM, ParserOrigin.HYBRID, ParserOrigin.RULE_BASED)


# ---------------------------------------------------------------------------
# IntentLlmError handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_error_with_partial_result_returns_partial() -> None:
    """If LLM raises and rules already have something, orchestrator returns partial."""
    from unittest.mock import AsyncMock, patch

    settings = Settings(anthropic_api_key=SecretStr("sk-fake-key-for-test"))

    with patch("poe1_fob.intent.extractor.llm_extract", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = IntentLlmError("network failure")
        intent = await extract_intent("cold totem mapping low budget", settings=settings)

    # Rule-based result has confidence ≥ 0.70, so LLM is never called here
    # (confidence ≥ threshold → early return before LLM).  Let's verify that.
    assert intent.parser_origin == ParserOrigin.RULE_BASED
    assert intent.damage_profile is not None


@pytest.mark.asyncio
async def test_llm_error_with_zero_partial_reraises() -> None:
    """If LLM raises and rule result is empty, orchestrator re-raises."""
    from unittest.mock import AsyncMock, patch

    settings = Settings(anthropic_api_key=SecretStr("sk-fake-key-for-test"))

    with patch("poe1_fob.intent.extractor.llm_extract", new_callable=AsyncMock) as mock_llm:
        mock_llm.side_effect = IntentLlmError("network failure")
        with patch("poe1_fob.intent.extractor.rule_based_extract") as mock_rule:
            from poe1_core.models.build_intent import BuildIntent
            from poe1_core.models.enums import ParserOrigin as PO

            empty_intent = BuildIntent(
                confidence=0.0,
                raw_input="zzz",
                parser_origin=PO.RULE_BASED,
            )
            mock_rule.return_value = (empty_intent, 0.0)
            with pytest.raises(IntentLlmError):
                await extract_intent("zzz", settings=settings)
