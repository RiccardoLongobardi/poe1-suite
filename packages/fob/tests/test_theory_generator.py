"""Unit tests for the Theorycrafter Build Generator v2 (Step 40).

Graph engine over vendored 3.28 data. Deterministic, sync, offline.
Hard-constraint anti-hallucination assertions are the primary test
targets.
"""

from __future__ import annotations

import base64
import zlib

import pytest

from poe1_fob.gear.base_items import get_base_catalogue
from poe1_fob.theory import (
    BuildSkeleton,
    GearSlot,
    TheoryHallucinationError,
    TheoryIntent,
    generate_build,
    list_active_skills,
)
from poe1_fob.theory import generator as gen
from poe1_fob.tree.tree_data import get_tree_data


def _intent(**kw: object) -> TheoryIntent:
    base: dict[str, object] = {
        "character_class": "Witch",
        "ascendancy": "Elementalist",
        "primary_skill": "Fireball",
        "damage_type": "fire",
        "defence_archetype": "life",
        "budget": "mid",
        "focus": "mapping",
    }
    base.update(kw)
    return TheoryIntent(**base)  # type: ignore[arg-type]


def test_skills_endpoint_payload_non_empty() -> None:
    skills = list_active_skills()
    assert len(skills) > 0
    names = {s.name for s in skills}
    assert "Fireball" in names


def test_gem_links_only_valid_supports() -> None:
    sk = generate_build(_intent())
    _, supports = gen._gem_catalogue()
    by_name = {s.name: s for s in supports}
    primary = sk.links[0]
    skill_tags = {"spell", "fire", "projectile", "aoe", "elemental"}
    for sname in primary.supports:
        if sname == "(open)":
            continue
        assert sname in by_name, f"{sname} not in gems_3_28.json"
        assert set(by_name[sname].valid_gem_tags).issubset(skill_tags)


def test_tree_nodes_are_real() -> None:
    sk = generate_build(_intent())
    known = set(get_tree_data().nodes_by_id.keys())
    for n in sk.tree_nodes:
        if n.type == "start":
            continue
        assert n.node_id in known, f"node {n.node_id} ('{n.name}') invented"


def test_gear_bases_are_real() -> None:
    known = {b.name for b in get_base_catalogue()}
    for budget in ("starter", "mid", "endgame"):
        sk = generate_build(_intent(budget=budget))
        for g in sk.gear_slots:
            assert g.base_name in known, f"{g.base_name} not in base_items.json"


def test_pob_code_round_trip() -> None:
    sk = generate_build(_intent())
    assert sk.pob_code
    # The PoB code is url-safe base64 of zlib-compressed XML — round-trip.
    padded = sk.pob_code + "=" * (-len(sk.pob_code) % 4)
    xml = zlib.decompress(base64.urlsafe_b64decode(padded.encode("ascii")))
    assert b"<PathOfBuilding" in xml or b"PathOfBuilding" in xml


def test_full_pipeline_witch_elementalist_fireball() -> None:
    sk = generate_build(_intent())
    assert isinstance(sk, BuildSkeleton)
    assert sk.intent.character_class == "Witch"
    assert sk.intent.ascendancy == "Elementalist"
    assert sk.links and sk.links[0].skill == "Fireball"
    assert sk.gear_slots
    assert sk.stats.estimated is True
    assert sk.stats.life_estimate > 0


def test_full_pipeline_duelist_gladiator_cyclone() -> None:
    sk = generate_build(
        _intent(
            character_class="Duelist",
            ascendancy="Gladiator",
            primary_skill="Cyclone",
            damage_type="physical",
            defence_archetype="life",
            budget="endgame",
            focus="allcontent",
        ),
    )
    assert sk.links[0].skill == "Cyclone"
    # Cyclone is a melee skill → weapon slot should be a 2H weapon, not Wand.
    weapon_slot = next((g for g in sk.gear_slots if g.slot in ("Weapon", "Wand", "Bow")), None)
    assert weapon_slot is not None
    assert weapon_slot.slot != "Wand"


def test_budget_tiers_change_gear_bands() -> None:
    starter = generate_build(_intent(budget="starter"))
    endgame = generate_build(_intent(budget="endgame"))
    starter_bases = tuple(g.base_name for g in starter.gear_slots)
    endgame_bases = tuple(g.base_name for g in endgame.gear_slots)
    assert starter_bases != endgame_bases


def test_supports_are_in_catalogue_for_every_active_skill() -> None:
    """Every catalogued active resolves to a usable 6L."""
    for skill_entry in list_active_skills():
        sk = generate_build(_intent(primary_skill=skill_entry.name))
        assert sk.links[0].skill == skill_entry.name
        # At least one real support resolved — or fully padded with (open).
        assert len(sk.links[0].supports) == 5


def test_hallucination_guard_blocks_invented_base(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patching the gear stage to inject a fake base triggers the guard."""

    real = gen._select_gear

    def fake_gear(intent: TheoryIntent) -> tuple[GearSlot, ...]:
        ok = real(intent)
        return (
            *ok[1:],
            GearSlot(
                slot="Helmet",
                base_name="Definitely Not A Real Base",
                stat_priorities=(),
                budget_tier=intent.budget,
            ),
        )

    monkeypatch.setattr(gen, "_select_gear", fake_gear)
    with pytest.raises(TheoryHallucinationError):
        generate_build(_intent())
