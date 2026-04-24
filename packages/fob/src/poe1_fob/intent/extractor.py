"""Intent extraction orchestrator.

Decision tree
-------------
1. Run :func:`rule_based_extract` on the raw query.
2. If confidence ≥ 0.70 → return the rule-based result directly.
3. Otherwise → call :func:`llm_extract` with the partial rule result as hint.
   - If the LLM call succeeds → return its result (origin = ``llm`` or ``hybrid``).
   - If the LLM call fails (missing key, network error, bad output) and we
     already have a partial result → return the partial result with a
     confidence penalty and origin ``rule_based``.
   - If we have nothing → re-raise :class:`IntentLlmError`.

The threshold of 0.70 is tuned so that at least two well-matched synonym
fields (e.g. ``damage_profile`` + ``content_focus``) will skip the LLM path
in typical usage, keeping latency and cost low for common queries.
"""

from __future__ import annotations

from poe1_core.models.build_intent import BuildIntent
from poe1_shared.config import Settings
from poe1_shared.logging import get_logger

from .llm import IntentLlmError, llm_extract
from .rules import rule_based_extract

log = get_logger(__name__)

_CONFIDENCE_THRESHOLD: float = 0.70


async def extract_intent(raw: str, *, settings: Settings) -> BuildIntent:
    """Convert a free-text query into a :class:`BuildIntent`.

    Parameters
    ----------
    raw:
        User query — Italian or English, any length.
    settings:
        App-wide settings.  LLM fallback is only attempted when
        :attr:`~poe1_shared.Settings.anthropic_api_key` is set.
    """
    if not raw.strip():
        raise ValueError("Query is empty")

    partial, confidence = rule_based_extract(raw)

    log.debug(
        "intent_rule_result",
        confidence=confidence,
        damage=partial.damage_profile,
        playstyle=partial.playstyle,
        content=[cfw.focus for cfw in partial.content_focus],
    )

    if confidence >= _CONFIDENCE_THRESHOLD:
        log.info("intent_rule_ok", confidence=confidence, raw=raw[:80])
        return partial

    # LLM fallback
    if settings.anthropic_api_key is None:
        # No key — return best-effort rule result as-is
        log.warning("intent_llm_skipped_no_key", confidence=confidence)
        return partial

    try:
        intent = await llm_extract(raw, partial_intent=partial, settings=settings)
        log.info("intent_llm_used", confidence=intent.confidence, raw=raw[:80])
        return intent
    except IntentLlmError as exc:
        log.warning("intent_llm_failed", error=str(exc), fallback_confidence=confidence)
        if confidence > 0.0:
            # Partial rule result is better than nothing
            return partial
        raise


__all__ = ["extract_intent"]
