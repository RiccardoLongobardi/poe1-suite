"""Tests for precomputed PoB-optimised build serving (Step 56).

The vendored ``data/theory/precomputed_3_28.json`` holds PoB-exact-optimised
builds for a curated archetype matrix. ``lookup`` serves them; everything
else falls back to live generation.
"""

from __future__ import annotations

from poe1_fob.theory import TheoryIntent, lookup_precomputed, precomputed_count


def _endgame(cls: str, asc: str, skill: str, dmg: str, defence: str) -> TheoryIntent:
    return TheoryIntent(
        character_class=cls,
        ascendancy=asc,
        primary_skill=skill,
        damage_type=dmg,  # type: ignore[arg-type]
        defence_archetype=defence,  # type: ignore[arg-type]
        budget="endgame",
        focus="allcontent",
    )


def test_precomputed_file_has_builds() -> None:
    """The vendored optima file is committed and non-empty."""
    assert precomputed_count() >= 1


def test_lookup_returns_optimised_build() -> None:
    """A matrix archetype resolves to a PoB-optimised build with real stats."""
    sk = lookup_precomputed(_endgame("Marauder", "Juggernaut", "Cyclone", "physical", "life"))
    assert sk is not None
    assert sk.optimised is True
    assert sk.stats.estimated is False
    assert sk.stats.full_dps > 0
    assert sk.stats.total_ehp > 0
    assert sk.pob_code
    assert sk.intent.primary_skill == "Cyclone"


def test_lookup_misses_unknown_archetype() -> None:
    """An archetype not in the matrix returns None (live-generation fallback)."""
    # Same class but a budget that was never precomputed.
    intent = TheoryIntent(
        character_class="Marauder",
        ascendancy="Juggernaut",
        primary_skill="Cyclone",
        damage_type="physical",
        defence_archetype="life",
        budget="starter",
        focus="mapping",
    )
    assert lookup_precomputed(intent) is None
    # And a skill that isn't in the matrix at all.
    assert lookup_precomputed(_endgame("Witch", "Elementalist", "Fireball", "fire", "life")) is None


def test_precomputed_builds_fit_point_budget() -> None:
    """Step 68: every served build must be allocatable at level 100 — a build
    needing more than the realistic ~123 passive points (99 levels + 22 quest
    + 2 bandit) is fictional and must never be vendored. Points spent = regular
    tree nodes (the free class start excluded) + masteries; ascendancy is free
    via the lab."""
    from poe1_fob.theory.precomputed import _load

    for skeleton in _load().values():
        regular = sum(1 for n in skeleton.tree_nodes if n.type in ("keystone", "notable", "travel"))
        masteries = sum(1 for n in skeleton.tree_nodes if n.type == "mastery")
        points = regular + masteries
        assert points <= 123, (
            f"{skeleton.intent.primary_skill} spends {points} passive points (> 123)"
        )


def test_chest_forbidding_helmet_sockets_primary_in_helmet() -> None:
    """Step 70: a helmet that forbids body armour (The Bringer of Rain) voids
    the body, so the primary 6L must be socketed in the helmet (legal) and the
    unequippable body must not be served. Builds with a normal helmet keep the
    6L in the body."""
    from poe1_fob.gear.uniques import unique_by_name
    from poe1_fob.theory.precomputed import _load

    for sk in _load().values():
        primary = sk.links[0]
        body_shown = any(g.slot == "Body Armour" for g in sk.gear_slots)
        helmet = next((g for g in sk.gear_slots if g.slot == "Helmet"), None)
        forbids = False
        if helmet is not None:
            u = unique_by_name(helmet.base_name)
            forbids = u is not None and any("Can't use Chest armour" in m for m in u.mods)
        if forbids:
            assert primary.slot == "Helmet", (
                f"{sk.intent.primary_skill}: 6L not in the chest-forbidding helmet"
            )
            assert not body_shown, (
                f"{sk.intent.primary_skill}: unequippable body served with a no-chest helmet"
            )
        else:
            assert primary.slot == "Body Armour", (
                f"{sk.intent.primary_skill}: 6L should be in the body with a normal helmet"
            )


def test_expanded_matrix_archetypes_are_served() -> None:
    """Step 71: the matrix grew beyond the original 5 — the new archetypes
    (incl. a Shadow build) resolve to optimised builds."""
    cases = [
        ("Marauder", "Juggernaut", "Boneshatter", "physical", "life"),
        ("Templar", "Inquisitor", "Spark", "lightning", "life"),
        ("Shadow", "Assassin", "Blade Vortex", "chaos", "life"),
    ]
    for cls, asc, skill, dmg, defence in cases:
        sk = lookup_precomputed(_endgame(cls, asc, skill, dmg, defence))
        assert sk is not None, f"{skill} not served"
        assert sk.optimised is True
        assert sk.intent.primary_skill == skill
        assert sk.stats.full_dps > 0 or sk.stats.total_ehp > 0


def test_builds_use_unique_flasks_keeping_a_sustain_flask() -> None:
    """Step 78: every served build runs powerful unique flasks (Bottled Faith /
    Vessel of Vinktar / The Wise Oak / Replica Rumi's Concoction / …) — a clean
    DPS+EHP lever with no passive-point cost — while keeping the first flask
    slot as a life/mana base for sustain (never replaced by a damage unique)."""
    from poe1_fob.gear.uniques import unique_by_name
    from poe1_fob.theory.precomputed import _load

    for sk in _load().values():
        flasks = [g for g in sk.gear_slots if g.slot.startswith("Flask")]
        assert len(flasks) >= 2, f"{sk.intent.primary_skill}: too few flask slots"
        # Slot 1 stays a sustain base (not a unique).
        assert unique_by_name(flasks[0].base_name) is None, (
            f"{sk.intent.primary_skill}: first flask should be a life/mana base for sustain"
        )
        # At least one of the remaining slots is a real unique flask.
        assert any(unique_by_name(g.base_name) is not None for g in flasks[1:]), (
            f"{sk.intent.primary_skill}: no unique flask found"
        )
