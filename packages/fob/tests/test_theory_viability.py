"""Unit tests for the Theorycrafter viability validation pass (Step 43).

Tests construct minimal :class:`BuildSkeleton`s directly — calling
:func:`generate_build` end-to-end would be slow (full pipeline + tree
data load) and orthogonal to what we want to check here.
"""

from __future__ import annotations

from poe1_fob.theory import (
    BuildSkeleton,
    GearSlot,
    GemLink,
    StatEstimate,
    TheoryIntent,
    TreeNodeRef,
    ViabilityReport,
    validate_build,
)


def _intent(**kw: object) -> TheoryIntent:
    base: dict[str, object] = {
        "character_class": "Witch",
        "ascendancy": "Occultist",
        "primary_skill": "Vortex",
        "damage_type": "cold",
        "defence_archetype": "life",
        "budget": "mid",
        "focus": "mapping",
    }
    base.update(kw)
    return TheoryIntent(**base)  # type: ignore[arg-type]


def _skeleton(
    *,
    intent: TheoryIntent | None = None,
    life: int = 5_000,
    es: int = 0,
    links: tuple[GemLink, ...] = (),
    gear_slots: tuple[GearSlot, ...] = (),
    tree_nodes: tuple[TreeNodeRef, ...] = (),
) -> BuildSkeleton:
    return BuildSkeleton(
        intent=intent or _intent(),
        links=links,
        tree_nodes=tree_nodes,
        gear_slots=gear_slots,
        stats=StatEstimate(
            life_estimate=life,
            es_estimate=es,
            dps_index=10_000,
            resistance_warning=None,
            estimated=True,
        ),
        rationale_it="",
        rationale_en="",
        pob_code="stub",
        viability=ViabilityReport(),
    )


def _movement_link() -> GemLink:
    return GemLink(
        skill="Flame Dash",
        supports=("Faster Casting", "Second Wind", "Arcane Surge"),
        slot="Boots",
        label="Movement 4L",
    )


def _mana_flask() -> GearSlot:
    return GearSlot(
        slot="Flask 1",
        base_name="Eternal Mana Flask",
        stat_priorities=(),
        budget_tier="mid",
    )


def _life_flask() -> GearSlot:
    return GearSlot(
        slot="Flask 1",
        base_name="Divine Life Flask",
        stat_priorities=(),
        budget_tier="mid",
    )


def _full_links() -> tuple[GemLink, ...]:
    return (
        GemLink(
            skill="Vortex",
            supports=("Efficacy", "Swift Affliction"),
            slot="Body Armour",
            label="Primary 6L",
        ),
        _movement_link(),
    )


def test_res_warning_always_present() -> None:
    """Every build carries the gear-resistance reminder, no matter what."""
    sk = _skeleton(
        life=10_000,
        links=_full_links(),
        gear_slots=(_mana_flask(),),
        tree_nodes=(TreeNodeRef(node_id=1, name="Acrobatics", type="keystone", stats=()),),
    )
    report = validate_build(sk)
    codes = {i.code for i in report.issues}
    assert "res_always_gear" in codes


def test_life_below_floor_starter() -> None:
    sk = _skeleton(intent=_intent(budget="starter"), life=2_500)
    report = validate_build(sk)
    error = next(i for i in report.issues if i.code == "life_below_floor")
    assert error.severity == "error"
    assert "2500" in error.message_it
    assert report.passed is False


def test_life_ok_starter() -> None:
    """Life just above the starter floor → no life_below_floor error."""
    sk = _skeleton(intent=_intent(budget="starter"), life=3_100)
    codes = {i.code for i in validate_build(sk).issues}
    assert "life_below_floor" not in codes


def test_es_below_floor_mid() -> None:
    sk = _skeleton(
        intent=_intent(defence_archetype="es"),
        life=0,
        es=4_000,
    )
    report = validate_build(sk)
    error = next(i for i in report.issues if i.code == "es_below_floor")
    assert error.severity == "error"
    assert report.passed is False


def test_single_layer_warning() -> None:
    """Defence=life with no defence keystones → only 1 layer → warning."""
    sk = _skeleton(life=10_000, links=_full_links(), gear_slots=(_mana_flask(),))
    codes = {i.code for i in validate_build(sk).issues}
    assert "single_defence_layer" in codes


def test_two_layers_no_warning() -> None:
    """life + Acrobatics keystone = 2 layers → no single_defence_layer warning."""
    sk = _skeleton(
        life=10_000,
        links=_full_links(),
        gear_slots=(_mana_flask(),),
        tree_nodes=(TreeNodeRef(node_id=1, name="Acrobatics", type="keystone", stats=()),),
    )
    codes = {i.code for i in validate_build(sk).issues}
    assert "single_defence_layer" not in codes


def test_no_movement_skill_warning() -> None:
    sk = _skeleton(
        life=10_000,
        # Vortex isn't in the movement-skill allowlist.
        links=(GemLink(skill="Vortex", supports=(), slot="Body Armour", label="Primary 6L"),),
        gear_slots=(_mana_flask(),),
        tree_nodes=(TreeNodeRef(node_id=1, name="Acrobatics", type="keystone", stats=()),),
    )
    codes = {i.code for i in validate_build(sk).issues}
    assert "no_movement_skill" in codes


def test_missing_mana_sustain_warning() -> None:
    """No mana flask AND no Lifetap support → warning."""
    sk = _skeleton(
        life=10_000,
        links=_full_links(),  # supports don't include Lifetap
        gear_slots=(_life_flask(),),  # Divine Life Flask — no "Mana"
        tree_nodes=(TreeNodeRef(node_id=1, name="Acrobatics", type="keystone", stats=()),),
    )
    codes = {i.code for i in validate_build(sk).issues}
    assert "missing_mana_sustain" in codes


def test_lifetap_satisfies_mana_check() -> None:
    """Lifetap in any link's supports counts as mana sustain."""
    sk = _skeleton(
        life=10_000,
        links=(
            GemLink(
                skill="Vortex",
                supports=("Efficacy", "Lifetap"),
                slot="Body Armour",
                label="Primary 6L",
            ),
            _movement_link(),
        ),
        gear_slots=(_life_flask(),),
        tree_nodes=(TreeNodeRef(node_id=1, name="Acrobatics", type="keystone", stats=()),),
    )
    codes = {i.code for i in validate_build(sk).issues}
    assert "missing_mana_sustain" not in codes
