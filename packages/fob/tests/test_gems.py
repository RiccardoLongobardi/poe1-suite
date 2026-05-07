"""Tests for the Step 14 T3 gem progression module."""

from __future__ import annotations

import pytest

from poe1_core.models.enums import ItemSlot
from poe1_fob.gems import (
    GemLink,
    GemProgression,
    GemSpec,
    StageGemLinks,
    gem_progression_for,
)

# ---------------------------------------------------------------------------
# GemSpec
# ---------------------------------------------------------------------------


def test_gem_spec_defaults() -> None:
    g = GemSpec(name="Righteous Fire")
    assert g.level == 20
    assert g.quality == 20
    assert g.is_support is False
    assert g.alt_quality is None


def test_gem_spec_alt_quality_validates() -> None:
    """Pydantic should reject an unknown alt-quality value."""

    with pytest.raises(ValueError):
        GemSpec(name="x", alt_quality="bad")  # type: ignore[arg-type]


def test_gem_spec_quality_clamped_to_23() -> None:
    """Quality > 23 (max with corrupted) is rejected."""

    with pytest.raises(ValueError):
        GemSpec(name="x", quality=30)


# ---------------------------------------------------------------------------
# GemLink
# ---------------------------------------------------------------------------


def test_gem_link_socket_count_must_match() -> None:
    """sockets=4 with only 3 gems → validator fires."""

    with pytest.raises(ValueError, match="sockets=4 but gems has 3"):
        GemLink(
            slot=ItemSlot.BODY_ARMOUR,
            sockets=4,
            gems=(
                GemSpec(name="A"),
                GemSpec(name="B"),
                GemSpec(name="C"),
            ),
        )


def test_gem_link_color_pattern_length_must_match_sockets() -> None:
    with pytest.raises(ValueError, match="color_pattern length"):
        GemLink(
            slot=ItemSlot.BODY_ARMOUR,
            sockets=2,
            color_pattern="RRRR",
            gems=(GemSpec(name="A"), GemSpec(name="B")),
        )


def test_gem_link_valid_6L() -> None:
    link = GemLink(
        slot=ItemSlot.BODY_ARMOUR,
        sockets=6,
        color_pattern="RRRRRR",
        gems=(
            GemSpec(name="Righteous Fire"),
            GemSpec(name="Burning Damage Support", is_support=True),
            GemSpec(name="Empower Support", level=3, is_support=True),
            GemSpec(name="Concentrated Effect Support", is_support=True),
            GemSpec(name="Combustion Support", is_support=True),
            GemSpec(name="Elemental Focus Support", is_support=True),
        ),
    )
    assert link.sockets == 6
    assert link.gems[0].name == "Righteous Fire"
    assert link.gems[2].level == 3


# ---------------------------------------------------------------------------
# StageGemLinks
# ---------------------------------------------------------------------------


def test_stage_gem_links_lookup_by_slot() -> None:
    s = StageGemLinks(
        stage_key="early_campaign",
        links=(
            GemLink(
                slot=ItemSlot.BODY_ARMOUR,
                sockets=1,
                gems=(GemSpec(name="A"),),
            ),
            GemLink(
                slot=ItemSlot.HELMET,
                sockets=1,
                gems=(GemSpec(name="B"),),
            ),
        ),
    )
    assert s.link_for_slot(ItemSlot.HELMET) is not None
    assert s.link_for_slot(ItemSlot.HELMET).gems[0].name == "B"  # type: ignore[union-attr]
    assert s.link_for_slot(ItemSlot.BOOTS) is None


# ---------------------------------------------------------------------------
# GemProgression
# ---------------------------------------------------------------------------


def test_gem_progression_rejects_duplicate_stage_keys() -> None:
    with pytest.raises(ValueError, match="duplicate stage_key"):
        GemProgression(
            target_name="bad",
            stages=(
                StageGemLinks(
                    stage_key="early_campaign",
                    links=(
                        GemLink(
                            slot=ItemSlot.BODY_ARMOUR,
                            sockets=1,
                            gems=(GemSpec(name="A"),),
                        ),
                    ),
                ),
                StageGemLinks(
                    stage_key="early_campaign",
                    links=(
                        GemLink(
                            slot=ItemSlot.BODY_ARMOUR,
                            sockets=1,
                            gems=(GemSpec(name="B"),),
                        ),
                    ),
                ),
            ),
        )


# ---------------------------------------------------------------------------
# RF Pohx registry hit
# ---------------------------------------------------------------------------


def test_gem_progression_for_rf_pohx_returns_six_stages() -> None:
    p = gem_progression_for("rf_pohx")
    assert p is not None
    assert p.target_name == "rf_pohx"
    assert len(p.stages) == 6


def test_rf_pohx_high_investment_has_6L_body_with_awakened() -> None:
    """High Investment 6L body should include Awakened Burning Damage 5."""

    p = gem_progression_for("rf_pohx")
    assert p is not None
    high_inv = p.for_stage("high_investment")
    assert high_inv is not None
    body_link = high_inv.link_for_slot(ItemSlot.BODY_ARMOUR)
    assert body_link is not None
    assert body_link.sockets == 6
    gem_names = [g.name for g in body_link.gems]
    assert "Righteous Fire" in gem_names
    assert any("Awakened Burning Damage" in n for n in gem_names)
    assert any("Awakened Empower" in n for n in gem_names)


def test_rf_pohx_early_campaign_uses_holy_flame_totem() -> None:
    p = gem_progression_for("rf_pohx")
    assert p is not None
    early = p.for_stage("early_campaign")
    assert early is not None
    body_link = early.link_for_slot(ItemSlot.BODY_ARMOUR)
    assert body_link is not None
    gem_names = [g.name for g in body_link.gems]
    assert "Holy Flame Totem" in gem_names


def test_gem_progression_for_unknown_returns_none() -> None:
    assert gem_progression_for("nonexistent_template") is None
