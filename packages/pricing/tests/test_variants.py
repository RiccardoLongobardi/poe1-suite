"""Unit tests for the variant resolver registry."""

from __future__ import annotations

from poe1_pricing import (
    VariantRegistry,
    build_default_registry,
    keystone_allocates_resolver,
    keystone_radius_resolver,
)


class TestKeystoneAllocatesResolver:
    """Forbidden Shako / Forbidden Flame / Forbidden Flesh use ``Allocates X``."""

    def test_extracts_simple_keystone(self) -> None:
        mods = ["Allocates Avatar of Fire"]
        assert keystone_allocates_resolver(mods) == "Avatar of Fire"

    def test_extracts_compound_keystone(self) -> None:
        mods = ["Allocates Mind Over Matter"]
        assert keystone_allocates_resolver(mods) == "Mind Over Matter"

    def test_handles_apostrophe_keystones(self) -> None:
        # Necromantic Aegis has no apostrophe but Acrobatics-style names
        # may have ' in some keystones (unlikely but defended).
        mods = ["Allocates Pain Attunement"]
        assert keystone_allocates_resolver(mods) == "Pain Attunement"

    def test_stops_at_conditional_clause(self) -> None:
        # Forbidden Flame text format: "Allocates X if you have the
        # matching modifier on Forbidden Flesh"
        mods = [
            "Allocates Magebane if you have the matching modifier on Forbidden Flesh",
        ]
        assert keystone_allocates_resolver(mods) == "Magebane"

    def test_returns_none_when_absent(self) -> None:
        mods = ["+50 to maximum Life", "20% increased Movement Speed"]
        assert keystone_allocates_resolver(mods) is None

    def test_returns_first_when_multiple(self) -> None:
        # Defensive: a Shako should never have two Allocates lines, but
        # the resolver should pick the first deterministically.
        mods = [
            "Allocates Acrobatics",
            "Allocates Eldritch Battery",
        ]
        assert keystone_allocates_resolver(mods) == "Acrobatics"

    def test_empty_iterable(self) -> None:
        assert keystone_allocates_resolver([]) is None


class TestKeystoneRadiusResolver:
    """Impossible Escape uses ``Passives in Radius of <Keystone>``."""

    def test_extracts_keystone(self) -> None:
        mods = [
            "Passives in Radius of Pain Attunement can be Allocated "
            "without being connected to your tree",
        ]
        assert keystone_radius_resolver(mods) == "Pain Attunement"

    def test_extracts_compound_keystone(self) -> None:
        mods = [
            "Passives in Radius of Eldritch Battery can be Allocated "
            "without being connected to your tree",
        ]
        assert keystone_radius_resolver(mods) == "Eldritch Battery"

    def test_returns_none_when_absent(self) -> None:
        mods = ["+25% to all Elemental Resistances"]
        assert keystone_radius_resolver(mods) is None


class TestVariantRegistry:
    def test_register_and_lookup(self) -> None:
        reg = VariantRegistry()
        reg.register("Test Item", lambda _mods: "test-variant", note="dummy")
        resolver = reg.resolver_for("Test Item")
        assert resolver is not None
        assert resolver([]) == "test-variant"

    def test_lookup_case_insensitive(self) -> None:
        reg = VariantRegistry()
        reg.register("Forbidden Shako", keystone_allocates_resolver)
        # Both lookups should hit the same resolver.
        assert reg.resolver_for("forbidden shako") is not None
        assert reg.resolver_for("FORBIDDEN SHAKO") is not None

    def test_unregistered_returns_none(self) -> None:
        reg = VariantRegistry()
        assert reg.resolver_for("Mageblood") is None

    def test_resolve_one_shot(self) -> None:
        reg = VariantRegistry()
        reg.register("Forbidden Shako", keystone_allocates_resolver)
        out = reg.resolve("Forbidden Shako", ["Allocates Avatar of Fire"])
        assert out == "Avatar of Fire"

    def test_resolve_no_resolver_returns_none(self) -> None:
        reg = VariantRegistry()
        assert reg.resolve("Mageblood", ["any mod"]) is None

    def test_resolve_resolver_returns_none(self) -> None:
        # Resolver is registered but the mods don't match — we propagate None.
        reg = VariantRegistry()
        reg.register("Forbidden Shako", keystone_allocates_resolver)
        assert reg.resolve("Forbidden Shako", ["unrelated mod"]) is None

    def test_register_replaces_existing(self) -> None:
        reg = VariantRegistry()
        reg.register("X", lambda _mods: "v1")
        reg.register("X", lambda _mods: "v2")
        resolver = reg.resolver_for("X")
        assert resolver is not None
        assert resolver([]) == "v2"

    def test_contains(self) -> None:
        reg = VariantRegistry()
        reg.register("Forbidden Shako", keystone_allocates_resolver)
        assert "Forbidden Shako" in reg
        assert "forbidden shako" in reg  # case-insensitive
        assert "Mageblood" not in reg


class TestDefaultRegistry:
    def test_includes_known_keystone_uniques(self) -> None:
        reg = build_default_registry()
        assert "Forbidden Shako" in reg
        assert "Forbidden Flame" in reg
        assert "Forbidden Flesh" in reg
        assert "Impossible Escape" in reg

    def test_excludes_unregistered_complex_uniques(self) -> None:
        # Watcher's Eye needs a live catalogue capture (milestone 9.3).
        # Until then we don't ship a half-broken resolver for it.
        reg = build_default_registry()
        assert "Watcher's Eye" not in reg

    def test_default_resolves_forbidden_shako(self) -> None:
        reg = build_default_registry()
        out = reg.resolve("Forbidden Shako", ["Allocates Avatar of Fire"])
        assert out == "Avatar of Fire"

    def test_default_resolves_impossible_escape(self) -> None:
        reg = build_default_registry()
        out = reg.resolve(
            "Impossible Escape",
            [
                "Passives in Radius of Pain Attunement can be Allocated "
                "without being connected to your tree",
            ],
        )
        assert out == "Pain Attunement"
