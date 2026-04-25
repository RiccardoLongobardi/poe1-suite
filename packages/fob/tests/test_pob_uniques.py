"""Unit tests for PoB unique → poe.ninja variant resolution."""

from __future__ import annotations

from poe1_core.models.enums import ItemRarity
from poe1_fob.pob import PobItem, unique_variant
from poe1_pricing import VariantRegistry, build_default_registry


def _item(
    name: str | None,
    *,
    implicits: tuple[str, ...] = (),
    explicits: tuple[str, ...] = (),
    rarity: ItemRarity = ItemRarity.UNIQUE,
    base_type: str = "Great Crown",
) -> PobItem:
    return PobItem(
        pob_id=1,
        rarity=rarity,
        name=name,
        base_type=base_type,
        implicits=implicits,
        explicits=explicits,
        raw_text="(test fixture)",
    )


class TestUniqueVariantResolution:
    def test_forbidden_shako_avatar_of_fire(self) -> None:
        reg = build_default_registry()
        item = _item(
            "Forbidden Shako",
            explicits=(
                "Has 1 Socketed Support Gem with 50% reduced Mana Reservation",
                "Allocates Avatar of Fire",
            ),
        )
        assert unique_variant(item, reg) == "Avatar of Fire"

    def test_impossible_escape_pain_attunement(self) -> None:
        reg = build_default_registry()
        item = _item(
            "Impossible Escape",
            base_type="Viridian Jewel",
            explicits=(
                "Passives in Radius of Pain Attunement can be Allocated "
                "without being connected to your tree",
            ),
        )
        assert unique_variant(item, reg) == "Pain Attunement"

    def test_forbidden_flame_with_conditional_clause(self) -> None:
        reg = build_default_registry()
        item = _item(
            "Forbidden Flame",
            base_type="Crimson Jewel",
            explicits=("Allocates Magebane if you have the matching modifier on Forbidden Flesh",),
        )
        assert unique_variant(item, reg) == "Magebane"

    def test_unregistered_unique_returns_none(self) -> None:
        reg = build_default_registry()
        # Mageblood isn't registered (it has no variant resolver).
        item = _item(
            "Mageblood",
            base_type="Heavy Belt",
            explicits=("Trigger a Socketed Spell on Use, with a 8 second Cooldown",),
        )
        assert unique_variant(item, reg) is None

    def test_item_without_name_returns_none(self) -> None:
        reg = build_default_registry()
        rare = _item(None, rarity=ItemRarity.RARE, base_type="Heavy Belt")
        assert unique_variant(rare, reg) is None

    def test_resolver_present_but_mods_dont_match_returns_none(self) -> None:
        # Forbidden Shako registered but mods don't include the
        # "Allocates X" line — resolver runs and yields None.
        reg = build_default_registry()
        item = _item(
            "Forbidden Shako",
            explicits=("(unrolled item — mod missing)",),
        )
        assert unique_variant(item, reg) is None

    def test_implicits_are_searched_too(self) -> None:
        # Defensive: the resolver consumes both implicits and explicits.
        reg = VariantRegistry()
        reg.register(
            "Forbidden Shako",
            lambda mods: next(
                (m.split("Allocates ", 1)[1] for m in mods if "Allocates " in m),
                None,
            ),
        )
        item = _item(
            "Forbidden Shako",
            implicits=("Allocates Eldritch Battery",),
            explicits=(),
        )
        assert unique_variant(item, reg) == "Eldritch Battery"

    def test_default_registry_includes_keystone_uniques(self) -> None:
        reg = build_default_registry()
        # Sanity: the four keystone-driven uniques are registered.
        for name in (
            "Forbidden Shako",
            "Forbidden Flame",
            "Forbidden Flesh",
            "Impossible Escape",
        ):
            assert name in reg, f"{name} missing from default registry"
