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
