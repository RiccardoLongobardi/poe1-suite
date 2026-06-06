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


# ---------------------------------------------------------------------------
# Step 15 — class / ascendancy / sort / numeric stat parsing
# ---------------------------------------------------------------------------


def test_extract_ascendancy_juggernaut() -> None:
    intent, _ = rule_based_extract("voglio una build juggernaut")
    assert intent.class_filter == "juggernaut"


def test_extract_ascendancy_short_form() -> None:
    intent, _ = rule_based_extract("rf jugg cheap")
    assert intent.class_filter == "juggernaut"


def test_extract_base_class_marauder() -> None:
    """Base class fallback when no ascendancy is present in the query."""

    intent, _ = rule_based_extract("marauder che faccia mapping")
    assert intent.class_filter == "marauder"


def test_extract_ascendancy_beats_base_class() -> None:
    """When both are mentioned, the more-specific ascendancy wins."""

    intent, _ = rule_based_extract("marauder juggernaut cheap")
    assert intent.class_filter == "juggernaut"


def test_extract_skill_and_class_together() -> None:
    """A 'skill + ascendancy' query must extract BOTH (the bug: 'elemental hit
    slayer' was only matching Slayer because Elemental Hit wasn't a known skill,
    so the Finder searched the whole Slayer ladder)."""

    intent, _ = rule_based_extract("elemental hit slayer")
    assert intent.main_skill_hint == "Elemental Hit"
    assert intent.class_filter == "slayer"


def test_extract_min_life_with_k_suffix() -> None:
    intent, _ = rule_based_extract("rf con 6k vita")
    assert intent.min_life == 6000


def test_extract_min_life_with_almeno_prefix() -> None:
    intent, _ = rule_based_extract("cyclone slayer almeno 5000 life")
    assert intent.min_life == 5000


def test_extract_min_dps_with_m_suffix() -> None:
    intent, _ = rule_based_extract("voglio almeno 1m dps per bossing")
    assert intent.min_dps == 1_000_000


def test_extract_min_ehp_explicit() -> None:
    intent, _ = rule_based_extract("build da 8000 ehp")
    assert intent.min_ehp == 8000


def test_extract_min_level() -> None:
    intent, _ = rule_based_extract("level 90+ marauder")
    assert intent.min_level == 90


def test_extract_sort_by_dps() -> None:
    intent, _ = rule_based_extract("rf jugg ordina per dps")
    assert intent.sort_by is not None
    assert intent.sort_by.value == "dps"


def test_extract_sort_by_life() -> None:
    intent, _ = rule_based_extract("max life builds")
    assert intent.sort_by is not None
    assert intent.sort_by.value == "life"


def test_extract_combined_query() -> None:
    """One realistic query exercising several Step 15 dimensions."""

    intent, conf = rule_based_extract(
        "spectre necromancer per bossing, almeno 1m dps e 8000 ehp, ordina per ehp"
    )
    assert intent.class_filter == "necromancer"
    assert intent.min_dps == 1_000_000
    assert intent.min_ehp == 8000
    assert intent.sort_by is not None and intent.sort_by.value == "ehp"
    # Combined signals should yield high confidence.
    assert conf >= 0.5
