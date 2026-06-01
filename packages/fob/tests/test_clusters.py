"""Tests for the vendored cluster-jewel catalogue (Step 76, Fase 2)."""

from __future__ import annotations

from poe1_fob.gear import clusters as cl


def test_cluster_catalogue_loaded() -> None:
    """The vendored cluster data has all 3 sizes, the damage themes, and the
    notable pool."""
    themes = cl.get_themes()
    assert set(themes) >= {cl.LARGE, cl.MEDIUM, cl.SMALL}
    large = cl.themes_for_size(cl.LARGE)
    assert len(large) >= 15  # 17 damage themes
    notables = cl.get_notables()
    assert len(notables) >= 200  # ~308 cluster notables


def test_large_has_damage_themes_with_enchants() -> None:
    """A Large cluster carries the real per-element damage themes, each with the
    exact 'Added Small Passive Skills grant: …' enchant PoB recognises."""
    by_tag = {t.tag: t for t in cl.themes_for_size(cl.LARGE)}
    assert "affliction_spell_damage" in by_tag
    assert "affliction_cold_damage" in by_tag
    spell = by_tag["affliction_spell_damage"]
    assert spell.enchant.startswith("Added Small Passive Skills grant:")
    assert "Spell Damage" in spell.enchant
    # Large = up to 12 passives.
    assert cl.size_passive_count(cl.LARGE) == 12


def test_notable_stats_present() -> None:
    """A known cluster notable resolves to its stat text (used for relevance
    scoring)."""
    notables = cl.get_notables()
    # Arcane Adept is a real Spell-Damage Large cluster notable.
    assert "Arcane Adept" in notables
    assert notables["Arcane Adept"].strip() != ""
