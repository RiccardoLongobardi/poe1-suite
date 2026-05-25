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
    skill = gen._find_active(primary.skill)
    skill_tags = set(skill.tags)
    for sname in primary.supports:
        if sname == "(open)":
            continue
        assert sname in by_name, f"{sname} not in gems_3_28.json"
        s = by_name[sname]
        # PoB semantics: no excluded tag present; require empty OR shares
        # at least one tag with the skill (any-of, not subset).
        assert not (set(s.exclude_tags) & skill_tags), f"{sname} excluded for {primary.skill}"
        if s.valid_gem_tags:
            assert set(s.valid_gem_tags) & skill_tags, f"{sname} requires unmet tag"


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


def test_stat_priorities_are_slot_aware() -> None:
    """Per-slot priorities reflect the build AND only show stats that can
    actually roll on the slot (Step 45d + Step 48 rollable filter).

    Spell builds get cast speed on gloves (spell damage is filtered out —
    it can't roll on gloves); attack builds get attack speed + accuracy on
    the weapon; rings carry mana + attributes; flasks render as MAGIC.
    """
    spell = generate_build(
        _intent(
            character_class="Witch",
            ascendancy="Elementalist",
            primary_skill="Arc",
            damage_type="lightning",
            defence_archetype="es",
            budget="endgame",
            focus="allcontent",
        )
    )
    by_slot = {g.slot: g for g in spell.gear_slots}
    assert "increased Cast Speed" in by_slot["Gloves"].stat_priorities
    # Spell damage does NOT roll on gloves → must be filtered out.
    assert "increased Spell Damage" not in by_slot["Gloves"].stat_priorities
    assert "to Mana" in by_slot["Ring"].stat_priorities
    assert "to all Attributes" in by_slot["Ring"].stat_priorities

    attack = generate_build(
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
    weapon = next(g for g in attack.gear_slots if g.slot in ("Weapon", "Bow", "Wand"))
    assert "increased Attack Speed" in weapon.stat_priorities
    assert "Accuracy" in weapon.stat_priorities
    assert weapon.slot != "Wand"

    # No item carries the old "Theorycrafted" placeholder name.
    assert "Theorycrafted" not in _decode_pob_xml(spell.pob_code)
    # Flasks are MAGIC with a suffix.
    assert "of Staunching" in _decode_pob_xml(
        attack.pob_code
    ) or "Rarity: MAGIC" in _decode_pob_xml(attack.pob_code)


def test_items_use_real_mod_tiers() -> None:
    """Step 47: generated item affixes are real RePoE tiers, gated by what
    can actually roll on the slot — not invented numbers."""
    import re

    from poe1_core.models.enums import ItemSlot
    from poe1_fob.gear.base_items import base_for_name, bases_for_slot
    from poe1_fob.theory.realmods import real_affix_line

    # A real top-tier life roll on a body armour exceeds the old simulated
    # cap of 120 (real T1 goes to ~189).
    body = base_for_name("Astral Plate") or next(iter(bases_for_slot(ItemSlot.BODY_ARMOUR)))
    line = real_affix_line("to maximum Life", frozenset(body.tags), "endgame")
    assert line is not None
    value = int(re.search(r"\d+", line).group())  # type: ignore[union-attr]
    assert value > 120, f"life line {line!r} is not a real high tier"

    # Spawn gating: Critical Strike Multiplier rolls on amulets, NOT gloves.
    gloves = next(iter(bases_for_slot(ItemSlot.GLOVES)))
    amulet = next(iter(bases_for_slot(ItemSlot.AMULET)))
    assert real_affix_line("Critical Strike Multiplier", frozenset(gloves.tags), "endgame") is None
    assert real_affix_line("Critical Strike Multiplier", frozenset(amulet.tags), "endgame")

    # The end-to-end export carries real mod lines (no invented "Generated"
    # placeholder values like the old +90 simulated life).
    sk = generate_build(
        _intent(
            character_class="Marauder",
            ascendancy="Juggernaut",
            primary_skill="Cyclone",
            damage_type="physical",
            defence_archetype="life",
            budget="endgame",
            focus="allcontent",
        )
    )
    xml = _decode_pob_xml(sk.pob_code)
    assert "to maximum Life" in xml


def test_weapon_has_flat_added_damage() -> None:
    """Step 52: attack builds get 'Adds X to Y Physical Damage' on the
    weapon (the #1 DPS mod); spell builds get '... to Spells' on the wand.
    Both resolve to real RePoE tiers."""
    from poe1_core.models.enums import ItemSlot
    from poe1_fob.gear.base_items import bases_for_slot
    from poe1_fob.theory.realmods import real_affix_line

    # Attack weapon (2H sword) → flat physical.
    weapons = bases_for_slot(ItemSlot.WEAPON_MAIN)
    sword = next(b for b in weapons if b.item_class == "Two Hand Sword")
    line = real_affix_line("Adds Physical Damage", frozenset(sword.tags), "endgame")
    assert line is not None and line.startswith("Adds ") and "Physical Damage" in line

    # Spell weapon (wand) → flat element to spells.
    wand = next(b for b in weapons if b.item_class == "Wand")
    spell_line = real_affix_line("Adds Fire Damage to Spells", frozenset(wand.tags), "endgame")
    assert spell_line is not None and "to Spells" in spell_line

    # The generated attack build's weapon body carries the flat damage line.
    sk = generate_build(
        _intent(
            character_class="Marauder",
            ascendancy="Juggernaut",
            primary_skill="Cyclone",
            damage_type="physical",
            defence_archetype="life",
            budget="endgame",
            focus="allcontent",
        )
    )
    weapon = next(g for g in sk.gear_slots if g.slot in ("Weapon", "Bow"))
    assert "Adds Physical Damage" in weapon.stat_priorities


def test_es_build_rolls_es_on_armour_and_spreads_resistances() -> None:
    """Step 54: an ES build must pick pure ES (int_armour) bases so the
    `local_energy_shield_+%` mod actually rolls on every armour slot — the
    old `energy_shield` base tag matched nothing, so helmet/gloves/boots
    showed no ES and the pool sat at ~3k. Resistances must also spread
    across slots so lightning (previously on a single slot) caps too."""
    es = generate_build(
        _intent(
            character_class="Witch",
            ascendancy="Occultist",
            primary_skill="Vortex",
            damage_type="cold",
            defence_archetype="es",
            budget="endgame",
            focus="allcontent",
        )
    )
    by_slot = {g.slot: g for g in es.gear_slots}
    # ES now resolves on the armour slots (real `local_energy_shield_+%`).
    for slot in ("Helmet", "Body Armour", "Gloves", "Boots"):
        assert "to maximum Energy Shield" in by_slot[slot].stat_priorities, (
            f"{slot} should carry an ES roll, got {by_slot[slot].stat_priorities}"
        )
    # All three elemental resistances are spread over multiple slots.
    for res in ("to Fire Resistance", "to Cold Resistance", "to Lightning Resistance"):
        slots_with = sum(1 for g in es.gear_slots if res in g.stat_priorities)
        assert slots_with >= 3, f"{res} only on {slots_with} slot(s) — under-spread"


def test_generator_never_auto_allocates_keystones() -> None:
    """Step 57: the live generator must not auto-allocate keystones — the
    keyword scorer can't tell a build-defining keystone from a build-breaker
    (it was picking Chaos Inoculation on a life build → Life 1, and ES-
    killing keystones on an ES trapper → ES 0). A life build in particular
    must never carry Chaos Inoculation."""
    for cls, asc, skill, dmg, defence in (
        ("Shadow", "Raider", "Frost Blades", "cold", "life"),
        ("Shadow", "Saboteur", "Lightning Trap", "lightning", "es"),
        ("Marauder", "Juggernaut", "Cyclone", "physical", "life"),
    ):
        sk = generate_build(
            _intent(
                character_class=cls,
                ascendancy=asc,
                primary_skill=skill,
                damage_type=dmg,
                defence_archetype=defence,
                budget="endgame",
                focus="allcontent",
            )
        )
        keystones = [n for n in sk.tree_nodes if n.type == "keystone"]
        assert not keystones, f"{cls}/{skill} auto-allocated keystones: {keystones}"
        names = {n.name for n in sk.tree_nodes}
        assert "Chaos Inoculation" not in names


def test_minion_build_gets_minion_supports_and_tree() -> None:
    """Step 55: a minion skill must be supported by the `createsminion`
    supports (Minion Damage, Feeding Frenzy, …) — NOT caster supports like
    Spell Echo, which are socketable but do nothing for the minion's DPS —
    and the tree must allocate minion-scaling notables (which the old
    physical/spell keyword scoring valued at 0)."""
    sk = generate_build(
        _intent(
            character_class="Witch",
            ascendancy="Necromancer",
            primary_skill="Summon Skeletons",
            damage_type="physical",
            defence_archetype="es",
            budget="endgame",
            focus="allcontent",
        )
    )
    body = next(link for link in sk.links if link.slot == "Body Armour")
    assert body.skill == "Summon Skeletons"
    assert "Minion Damage" in body.supports
    # Caster supports that don't buff minions must not crowd the link.
    for useless in ("Spell Echo", "Unleash", "Concentrated Effect"):
        assert useless not in body.supports, f"{useless} should not support a minion skill"
    # The tree now allocates minion-scaling nodes.
    minion_nodes = sum(1 for n in sk.tree_nodes if "minion" in n.name.lower())
    assert minion_nodes >= 5, f"expected minion tree nodes, got {minion_nodes}"


def test_spectre_build_warns_to_select_spectre() -> None:
    """Step 55: a Raise Spectre build ships with no spectre chosen (PoB
    needs a monster pick), so viability flags the manual step."""
    sk = generate_build(
        _intent(
            character_class="Witch",
            ascendancy="Necromancer",
            primary_skill="Raise Spectre",
            damage_type="physical",
            defence_archetype="es",
            budget="endgame",
            focus="allcontent",
        )
    )
    codes = {i.code for i in sk.viability.issues}
    assert "spectre_needs_selection" in codes


def test_elemental_attack_uses_attack_stats_and_bow() -> None:
    """Step 53: an elemental *attack* (Ranger Lightning Strike, lightning)
    is classified by tags as an attack — not a spell. Its weapon carries
    'Adds Lightning Damage' (attack flat), never the spell variant or
    'increased Spell Damage', and the weapon slot is not a Wand."""
    sk = generate_build(
        _intent(
            character_class="Ranger",
            ascendancy="Raider",
            primary_skill="Lightning Strike",
            damage_type="lightning",
            defence_archetype="life",
            budget="endgame",
            focus="allcontent",
        )
    )
    weapon = next(g for g in sk.gear_slots if g.slot in ("Weapon", "Bow", "Wand"))
    assert weapon.slot != "Wand"
    assert "Adds Lightning Damage" in weapon.stat_priorities
    assert "Adds Lightning Damage to Spells" not in weapon.stat_priorities
    assert "increased Spell Damage" not in weapon.stat_priorities
    assert "increased Attack Speed" in weapon.stat_priorities

    # Ice Shot is a bow attack whose PoB data lacks a "bow" tag — Step 53's
    # tag heuristic must still route it to a Bow, not a Wand.
    ice = generate_build(
        _intent(
            character_class="Ranger",
            ascendancy="Deadeye",
            primary_skill="Ice Shot",
            damage_type="cold",
            defence_archetype="life",
            budget="endgame",
            focus="allcontent",
        )
    )
    ice_weapon = next(g for g in ice.gear_slots if g.slot in ("Weapon", "Bow", "Wand"))
    assert ice_weapon.slot == "Bow"
    assert "Adds Cold Damage" in ice_weapon.stat_priorities
