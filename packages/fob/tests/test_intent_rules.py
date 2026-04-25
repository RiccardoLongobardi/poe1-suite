"""Unit tests for the rule-based intent extractor.

All cases use real player queries from fixtures/intents/cases.json.
Tests are fully offline — no API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from poe1_fob.intent.rules import rule_based_extract

_CASES_PATH = Path(__file__).parent / "fixtures" / "intents" / "cases.json"


def _load_cases() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], json.loads(_CASES_PATH.read_text(encoding="utf-8")))


@pytest.mark.parametrize("case", _load_cases(), ids=[c["id"] for c in _load_cases()])
def test_rule_based_extract(case: dict[str, Any]) -> None:
    raw: str = case["raw"]
    expect: dict[str, Any] = case["expect"]

    intent, confidence = rule_based_extract(raw)

    # --- confidence floor ---
    assert confidence >= expect["min_confidence"], (
        f"[{case['id']}] confidence {confidence:.2f} < {expect['min_confidence']}"
    )

    # --- damage_profile ---
    if "damage_profile" in expect and expect["damage_profile"] is not None:
        assert intent.damage_profile is not None, f"[{case['id']}] damage_profile not extracted"
        assert intent.damage_profile.value == expect["damage_profile"], (
            f"[{case['id']}] damage_profile={intent.damage_profile!r}"
            f" != {expect['damage_profile']!r}"
        )

    # --- playstyle ---
    if "playstyle" in expect and expect["playstyle"] is not None:
        assert intent.playstyle is not None, f"[{case['id']}] playstyle not extracted"
        assert intent.playstyle.value == expect["playstyle"], (
            f"[{case['id']}] playstyle={intent.playstyle!r} != {expect['playstyle']!r}"
        )

    # --- content_focus ---
    if "content_focus_contains" in expect:
        extracted_focuses = {cfw.focus.value for cfw in intent.content_focus}
        for expected_focus in expect["content_focus_contains"]:
            assert expected_focus in extracted_focuses, (
                f"[{case['id']}] content_focus missing {expected_focus!r}, got {extracted_focuses}"
            )

    # --- budget_tier ---
    if "budget_tier" in expect and expect["budget_tier"] is not None:
        assert intent.budget is not None, f"[{case['id']}] budget not extracted"
        assert intent.budget.tier is not None
        assert intent.budget.tier.value == expect["budget_tier"], (
            f"[{case['id']}] budget_tier={intent.budget.tier!r} != {expect['budget_tier']!r}"
        )

    # --- complexity_cap ---
    if "complexity_cap" in expect and expect["complexity_cap"] is not None:
        assert intent.complexity_cap is not None, f"[{case['id']}] complexity_cap not extracted"
        assert intent.complexity_cap.value == expect["complexity_cap"], (
            f"[{case['id']}] complexity_cap={intent.complexity_cap!r}"
            f" != {expect['complexity_cap']!r}"
        )

    # --- defense_profile ---
    if "defense_profile" in expect and expect["defense_profile"] is not None:
        assert intent.defense_profile is not None, f"[{case['id']}] defense_profile not extracted"
        assert intent.defense_profile.value == expect["defense_profile"], (
            f"[{case['id']}] defense_profile={intent.defense_profile!r}"
            f" != {expect['defense_profile']!r}"
        )

    # --- hard_constraints ---
    if "hard_constraints_contains" in expect:
        extracted_constraints = {hc.value for hc in intent.hard_constraints}
        for expected_hc in expect["hard_constraints_contains"]:
            assert expected_hc in extracted_constraints, (
                f"[{case['id']}] hard_constraints missing {expected_hc!r},"
                f" got {extracted_constraints}"
            )


def test_raw_input_preserved() -> None:
    raw = "cold build per mapping"
    intent, _ = rule_based_extract(raw)
    assert intent.raw_input == raw


def test_empty_query_returns_zero_confidence() -> None:
    intent, confidence = rule_based_extract("  ")
    assert confidence == 0.0
    assert intent.damage_profile is None
    assert intent.playstyle is None
    assert intent.content_focus == []


def test_confidence_not_above_one() -> None:
    _, confidence = rule_based_extract(
        "cold fire lightning minion physical chaos mapping bossing uber delve sanctum "
        "simulacrum heist racing league start ssf hardcore ci evasion armour block low budget high"
    )
    assert confidence <= 1.0


def test_content_focus_weights_sum_le_one() -> None:
    intent, _ = rule_based_extract("mapping bossing uber delve sanctum")
    total = sum(cfw.weight for cfw in intent.content_focus)
    assert total <= 1.01  # allow tiny float rounding


def test_rule_based_parser_origin() -> None:
    from poe1_core.models.enums import ParserOrigin

    intent, _ = rule_based_extract("cold mapping")
    assert intent.parser_origin == ParserOrigin.RULE_BASED
