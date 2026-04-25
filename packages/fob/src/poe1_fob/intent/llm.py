"""LLM fallback for intent extraction via Anthropic tool use.

Uses ``claude-haiku-4-5-20251001`` with a single tool whose input schema
mirrors :class:`poe1_core.BuildIntent`.  Tool use forces the model to emit
valid JSON — enum hallucinations are caught at Pydantic validation time and
surfaced as :class:`IntentLlmError`.

The caller must already hold a :class:`poe1_shared.Settings` instance with
a non-None :attr:`anthropic_api_key`.  Raising :class:`IntentLlmError` on
missing key avoids any import-time failure so the rule-based path stays
usable without an API key installed.
"""

from __future__ import annotations

import json
from typing import Any, cast

import anthropic

from poe1_core.models.build_intent import BudgetRange, BuildIntent, ContentFocusWeight
from poe1_core.models.enums import (
    BudgetTier,
    ComplexityLevel,
    ContentFocus,
    DamageProfile,
    DefenseProfile,
    HardConstraint,
    ParserOrigin,
    Playstyle,
)
from poe1_shared.config import Settings
from poe1_shared.logging import get_logger

log = get_logger(__name__)

_MODEL: str = "claude-haiku-4-5-20251001"

# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

_TOOL_NAME = "extract_build_intent"

_TOOL_SCHEMA: dict[str, Any] = {
    "name": _TOOL_NAME,
    "description": (
        "Extract a strongly-typed Path of Exile 1 build intent from a natural-language "
        "query.  The query may be in Italian or English.  Only set fields you are "
        "confident about.  Leave everything else null or empty."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "damage_profile": {
                "type": ["string", "null"],
                "enum": [None, *[v.value for v in DamageProfile]],
                "description": "Primary damage type / source.",
            },
            "alternative_damage_profiles": {
                "type": "array",
                "items": {"type": "string", "enum": [v.value for v in DamageProfile]},
                "description": "Up to two secondary damage profiles if the query is ambiguous.",
            },
            "playstyle": {
                "type": ["string", "null"],
                "enum": [None, *[v.value for v in Playstyle]],
                "description": "How the build is played.",
            },
            "alternative_playstyles": {
                "type": "array",
                "items": {"type": "string", "enum": [v.value for v in Playstyle]},
                "description": "Secondary playstyles if ambiguous.",
            },
            "content_focus": {
                "type": "array",
                "description": "Intended content with relative weights summing to ≤ 1.0.",
                "items": {
                    "type": "object",
                    "properties": {
                        "focus": {"type": "string", "enum": [v.value for v in ContentFocus]},
                        "weight": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                    "required": ["focus", "weight"],
                },
            },
            "budget_tier": {
                "type": ["string", "null"],
                "enum": [None, *[v.value for v in BudgetTier]],
                "description": "Overall budget tier.",
            },
            "complexity_cap": {
                "type": ["string", "null"],
                "enum": [None, *[v.value for v in ComplexityLevel]],
                "description": "Maximum complexity the player is comfortable with.",
            },
            "defense_profile": {
                "type": ["string", "null"],
                "enum": [None, *[v.value for v in DefenseProfile]],
                "description": "Preferred defensive layer.",
            },
            "hard_constraints": {
                "type": "array",
                "items": {"type": "string", "enum": [v.value for v in HardConstraint]},
                "description": "Non-negotiable filters (e.g. no_melee, ssf_viable).",
            },
        },
        "required": [
            "damage_profile",
            "alternative_damage_profiles",
            "playstyle",
            "alternative_playstyles",
            "content_focus",
            "budget_tier",
            "complexity_cap",
            "defense_profile",
            "hard_constraints",
        ],
    },
}

_SYSTEM_PROMPT = """\
You are a Path of Exile 1 build advisor assistant.
Your job is to call the `extract_build_intent` tool to convert the user's request \
into a structured build intent.
Use only the valid enum values listed in the tool schema — do not invent values.
The request may be in Italian or English; understand both.
Set only fields you are genuinely confident about; leave the rest null/empty.\
"""


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------


class IntentLlmError(RuntimeError):
    """Raised when the LLM call fails or returns unusable output."""


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


async def llm_extract(
    raw: str,
    *,
    partial_intent: BuildIntent | None = None,
    settings: Settings,
) -> BuildIntent:
    """Call the Anthropic API to produce a :class:`BuildIntent`.

    *partial_intent* is forwarded as context so the model knows what the
    rule-based pass already found.
    """
    if settings.anthropic_api_key is None:
        raise IntentLlmError("ANTHROPIC_API_KEY is not set — LLM fallback unavailable")

    api_key = settings.anthropic_api_key.get_secret_value()
    client = anthropic.AsyncAnthropic(api_key=api_key)

    user_content = raw
    if partial_intent is not None:
        partial_json = partial_intent.model_dump(
            mode="json",
            exclude_none=True,
            exclude={"raw_input", "confidence", "parser_origin"},
        )
        if partial_json:
            user_content = (
                f"{raw}\n\n"
                f"[Partial parse from rule engine — use as a hint, not a constraint]: "
                f"{json.dumps(partial_json, ensure_ascii=False)}"
            )

    log.debug("intent_llm_call", model=_MODEL, raw_length=len(raw))

    try:
        response = await client.messages.create(  # type: ignore[call-overload]
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": user_content}],
        )
    except anthropic.APIError as exc:
        raise IntentLlmError(f"Anthropic API error: {exc}") from exc

    # Extract the tool-use block
    tool_block = next(
        (b for b in response.content if b.type == "tool_use" and b.name == _TOOL_NAME),
        None,
    )
    if tool_block is None:
        raise IntentLlmError("LLM did not call extract_build_intent tool")

    data: dict[str, Any] = cast(dict[str, Any], tool_block.input)

    # --- Reconstruct typed objects ---
    try:
        damage_profile: DamageProfile | None = (
            DamageProfile(data["damage_profile"]) if data.get("damage_profile") else None
        )
        alt_damage: list[DamageProfile] = [
            DamageProfile(v) for v in data.get("alternative_damage_profiles", [])
        ]
        playstyle: Playstyle | None = (
            Playstyle(data["playstyle"]) if data.get("playstyle") else None
        )
        alt_playstyle: list[Playstyle] = [
            Playstyle(v) for v in data.get("alternative_playstyles", [])
        ]
        content_focus: list[ContentFocusWeight] = [
            ContentFocusWeight(focus=ContentFocus(item["focus"]), weight=item["weight"])
            for item in data.get("content_focus", [])
        ]
        budget: BudgetRange | None = (
            BudgetRange(tier=BudgetTier(data["budget_tier"])) if data.get("budget_tier") else None
        )
        complexity: ComplexityLevel | None = (
            ComplexityLevel(data["complexity_cap"]) if data.get("complexity_cap") else None
        )
        defense: DefenseProfile | None = (
            DefenseProfile(data["defense_profile"]) if data.get("defense_profile") else None
        )
        constraints: set[HardConstraint] = {
            HardConstraint(v) for v in data.get("hard_constraints", [])
        }

        # Determine parser_origin
        has_partial = partial_intent is not None and (
            partial_intent.damage_profile is not None
            or partial_intent.playstyle is not None
            or bool(partial_intent.content_focus)
        )
        origin = ParserOrigin.HYBRID if has_partial else ParserOrigin.LLM

        intent = BuildIntent(
            damage_profile=damage_profile,
            alternative_damage_profiles=alt_damage,
            playstyle=playstyle,
            alternative_playstyles=alt_playstyle,
            content_focus=content_focus,
            budget=budget,
            complexity_cap=complexity,
            defense_profile=defense,
            hard_constraints=constraints,
            confidence=0.85,  # LLM result carries fixed confidence
            raw_input=raw,
            parser_origin=origin,
        )
    except (KeyError, ValueError) as exc:
        raise IntentLlmError(f"LLM output failed validation: {exc}") from exc

    log.info("intent_llm_ok", origin=origin, damage=damage_profile, playstyle=playstyle)
    return intent


__all__ = ["IntentLlmError", "llm_extract"]
