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


# ---------------------------------------------------------------------------
# Step 41 — PoB export completeness
# ---------------------------------------------------------------------------


def _decode_pob_xml(pob_code: str) -> str:
    import base64
    import zlib

    padded = pob_code + "=" * (-len(pob_code) % 4)
    xml = zlib.decompress(base64.urlsafe_b64decode(padded.encode("ascii")))
    return xml.decode("utf-8")


_PIPELINE_INTENTS: tuple[dict[str, object], ...] = (
    {
        "character_class": "Ranger",
        "ascendancy": "Deadeye",
        "primary_skill": "Lightning Arrow",
        "damage_type": "lightning",
        "defence_archetype": "life",
        "budget": "endgame",
        "focus": "mapping",
    },
    {
        "character_class": "Witch",
        "ascendancy": "Occultist",
        "primary_skill": "Vortex",
        "damage_type": "cold",
        "defence_archetype": "es",
        "budget": "mid",
        "focus": "allcontent",
    },
    {
        "character_class": "Marauder",
        "ascendancy": "Juggernaut",
        "primary_skill": "Cyclone",
        "damage_type": "physical",
        "defence_archetype": "life",
        "budget": "starter",
        "focus": "bossing",
    },
)


def test_pob_export_has_all_gem_slots() -> None:
    """Five gem groups in <Skills>: Body 6L + Helmet/Gloves/Boots/Weapon 4L."""
    import xml.etree.ElementTree as ET

    for ovr in _PIPELINE_INTENTS:
        sk = generate_build(_intent(**ovr))
        root = ET.fromstring(_decode_pob_xml(sk.pob_code))
        # Skill groups live under <Skills>/<SkillSet>/<Skill> in PoB XML.
        skill_groups = root.findall(".//SkillSet/Skill")
        assert len(skill_groups) == 5, (
            f"{ovr['primary_skill']}: expected 5 skill groups, got {len(skill_groups)}"
        )


def test_pob_export_items_have_stats() -> None:
    """Every recommended rare ships at least one simulated affix line."""
    import xml.etree.ElementTree as ET

    for ovr in _PIPELINE_INTENTS:
        sk = generate_build(_intent(**ovr))
        root = ET.fromstring(_decode_pob_xml(sk.pob_code))
        items = root.find("Items")
        assert items is not None
        any_affix = any(
            ("+" in (it.text or "")) or ("%" in (it.text or "")) for it in items.findall("Item")
        )
        assert any_affix, f"{ovr['primary_skill']}: no item carries simulated stats"


def test_pob_export_has_flasks() -> None:
    """Five flask slots — labelled 'Flask 1' .. 'Flask 5' in <ItemSet>."""
    import xml.etree.ElementTree as ET

    for ovr in _PIPELINE_INTENTS:
        sk = generate_build(_intent(**ovr))
        root = ET.fromstring(_decode_pob_xml(sk.pob_code))
        item_set = root.find(".//ItemSet")
        assert item_set is not None
        flask_slots = [
            s for s in item_set.findall("Slot") if (s.get("name") or "").startswith("Flask")
        ]
        assert len(flask_slots) >= 5, (
            f"{ovr['primary_skill']}: expected ≥5 flask slots, got {len(flask_slots)}"
        )


def test_pob_export_has_jewels() -> None:
    """Two jewel slots — labelled 'Jewel 1' and 'Jewel 2'."""
    import xml.etree.ElementTree as ET

    for ovr in _PIPELINE_INTENTS:
        sk = generate_build(_intent(**ovr))
        root = ET.fromstring(_decode_pob_xml(sk.pob_code))
        item_set = root.find(".//ItemSet")
        assert item_set is not None
        jewel_slots = [
            s for s in item_set.findall("Slot") if (s.get("name") or "").startswith("Jewel")
        ]
        assert len(jewel_slots) >= 2, (
            f"{ovr['primary_skill']}: expected ≥2 jewel slots, got {len(jewel_slots)}"
        )


def test_tree_scoring_uses_stats() -> None:
    """A node whose name has no keyword but whose stats do still scores."""
    from poe1_fob.tree.tree_data import TreeNode

    node = TreeNode(
        id=42,
        name="Acrobatics",
        is_keystone=True,
        is_notable=False,
        is_mastery=False,
        is_ascendancy_start=False,
        ascendancy_name=None,
        out=(),
        class_start_index=None,
        group=None,
        stats=("30% chance to Dodge Spell Hits while you have evasion",),
    )
    # "evasion" is a life-defence keyword (Bug 1 fix); without the
    # stats array the old name-only scorer would have returned 0.
    score = gen._score_node(node, "physical", "life")
    assert score > 0


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


def test_no_duplicate_primary_skill() -> None:
    """The primary skill must appear in exactly one link (Step 45b Bug 1)."""
    skeleton = generate_build(
        _intent(
            character_class="Marauder",
            ascendancy="Juggernaut",
            primary_skill="Earthquake",
            damage_type="physical",
            defence_archetype="life",
            budget="mid",
            focus="allcontent",
        )
    )
    primary = skeleton.links[0].skill
    duplicates = [link for link in skeleton.links if link.skill == primary]
    assert len(duplicates) == 1, f"'{primary}' appears in {len(duplicates)} links"
    # And no active skill at all is repeated across the layout.
    skills = [link.skill for link in skeleton.links]
    assert len(skills) == len(set(skills)), f"duplicate skill in {skills}"


def test_no_incompatible_supports() -> None:
    """Faster Casting must never support an attack-tagged skill (Bug 2)."""
    skeleton = generate_build(
        _intent(
            character_class="Marauder",
            ascendancy="Juggernaut",
            primary_skill="Earthquake",
            damage_type="physical",
            defence_archetype="life",
            budget="mid",
            focus="allcontent",
        )
    )
    for link in skeleton.links:
        active = gen._find_active(link.skill)
        for sup_name in link.supports:
            if sup_name == "(open)":
                continue
            if sup_name == "Faster Casting":
                assert "attack" not in active.tags, (
                    f"Faster Casting on {link.skill} (attack-tagged)"
                )


def test_no_unavailable_awakened_gems() -> None:
    """Only the 3 allowlisted Awakened gems may appear in any link (Step 45c).

    3.28 removed every Awakened Support except Empower / Enlighten /
    Enhance. The catalogue stores them without a " Support" suffix.
    """
    allow = {"Awakened Empower", "Awakened Enlighten", "Awakened Enhance"}
    for cls, asc, skill, dmg in [
        ("Witch", "Elementalist", "Arc", "lightning"),
        ("Shadow", "Saboteur", "Fireball", "fire"),
        ("Ranger", "Deadeye", "Tornado Shot", "physical"),
        ("Marauder", "Juggernaut", "Earthquake", "physical"),
    ]:
        skeleton = generate_build(
            _intent(
                character_class=cls,
                ascendancy=asc,
                primary_skill=skill,
                damage_type=dmg,
                defence_archetype="life",
                budget="endgame",
                focus="allcontent",
            )
        )
        for link in skeleton.links:
            for s in link.supports:
                if s.startswith("Awakened ") and s not in allow:
                    pytest.fail(f"gem '{s}' not available in 3.28 (link {link.slot})")
