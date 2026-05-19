"""Tests for the GGG Trade stat resolver (poe1_fob.trade_stats)."""

from __future__ import annotations

from poe1_fob.trade_stats import (
    first_number,
    normalize_mod_text,
    resolve_mod,
    resolve_mods,
)


def test_normalize_collapses_numbers_and_plus() -> None:
    # A PoB mod line and a GGG `#`-template collapse to the same key.
    assert normalize_mod_text("+85 to maximum Life") == normalize_mod_text("# to maximum Life")


def test_first_number() -> None:
    assert first_number("+85 to maximum Life") == 85.0
    assert first_number("Adds 12 to 23 Physical Damage") == 12.0
    assert first_number("Corrupted") is None


def test_resolve_exact_match() -> None:
    r = resolve_mod("+42% to Cold Resistance")
    assert r.stat_id is not None
    assert r.stat_id.startswith("explicit.")
    assert r.value == 42.0


def test_resolve_implicit_picks_implicit_domain() -> None:
    """An implicit mod resolves to the implicit-domain stat id.

    The same text exists as both an explicit and an implicit GGG stat;
    `implicit=True` must pick the implicit one or the Trade search of a
    corrupted implicit returns nothing.
    """

    expl = resolve_mod("+15% to Cold Resistance", implicit=False)
    impl = resolve_mod("+15% to Cold Resistance", implicit=True)
    assert expl.stat_id is not None
    assert expl.stat_id.startswith("explicit.")
    assert impl.stat_id is not None
    assert impl.stat_id.startswith("implicit.")


def test_resolve_fuzzy_plural_count_mod() -> None:
    """A count mod GGG stores singular resolves via the fuzzy fallback.

    Mageblood's signature mod renders plural in PoB ("Flasks … apply
    their … Effects") while GGG's stat template is singular.
    """

    r = resolve_mod("Leftmost 4 Magic Utility Flasks constantly apply their Flask Effects to you")
    assert r.stat_id is not None
    assert r.stat_id.startswith("explicit.")


def test_fuzzy_does_not_collide_distinct_mods() -> None:
    # Fire and Cold resistance must resolve to *different* stat ids —
    # the fuzzy cutoff is high enough they never cross-match.
    fire = resolve_mod("+15% to Fire Resistance")
    cold = resolve_mod("+15% to Cold Resistance")
    assert fire.stat_id is not None
    assert cold.stat_id is not None
    assert fire.stat_id != cold.stat_id


def test_resolve_unrelated_line_returns_none() -> None:
    assert resolve_mod("xyzzy not a real mod line at all qwerty").stat_id is None


def test_resolve_mods_dedupes_and_drops_blanks() -> None:
    rows = resolve_mods(["+85 to maximum Life", "+85 to maximum Life", "   "])
    assert len(rows) == 1
