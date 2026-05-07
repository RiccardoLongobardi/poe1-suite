"""Hand-curated gem progressions per template.

Step 14 T3 ships RF Pohx Juggernaut as the reference. Each stage
defines every relevant socket group: 6L body (main skill), 4L
helmet/gloves/boots/weapon (CWDT, auras, mobility, defense).

When a template doesn't ship a gem progression the planner UI falls
back to the existing free-form ``gem_changes`` strings emitted by
the BuildTemplate.
"""

from __future__ import annotations

from poe1_core.models.enums import ItemSlot

from .models import GemLink, GemProgression, GemSpec, StageGemLinks


def _g(
    name: str,
    *,
    level: int = 20,
    quality: int = 20,
    is_support: bool = False,
    alt: str | None = None,
    notes: str = "",
) -> GemSpec:
    """Tiny helper for readability."""

    return GemSpec(
        name=name,
        level=level,
        quality=quality,
        is_support=is_support,
        alt_quality=alt,  # type: ignore[arg-type]
        notes=notes,
    )


# ---------------------------------------------------------------------------
# RF Pohx Juggernaut — reference gem progression
# ---------------------------------------------------------------------------


RF_POHX_GEM_PROGRESSION = GemProgression(
    target_name="rf_pohx",
    stages=(
        StageGemLinks(
            stage_key="early_campaign",
            notes=(
                "Atto 1-4. Holy Flame Totem main skill day 1. Frostblink come "
                "movement. NO Righteous Fire ancora — non c'è life regen."
            ),
            links=(
                GemLink(
                    slot=ItemSlot.BODY_ARMOUR,
                    sockets=4,
                    gems=(
                        _g("Holy Flame Totem", level=10, quality=0),
                        _g("Multiple Totems Support", level=10, quality=0, is_support=True),
                        _g("Combustion Support", level=10, quality=0, is_support=True),
                        _g("Faster Casting Support", level=10, quality=0, is_support=True),
                    ),
                    notes="Tabula 4L iniziale, espandere a 6L appena disponibile.",
                ),
                GemLink(
                    slot=ItemSlot.HELMET,
                    sockets=3,
                    gems=(
                        _g("Frostblink", level=8, quality=0),
                        _g("Flame Dash", level=8, quality=0),
                        _g(
                            "Quicksilver Flask",
                            level=1,
                            quality=0,
                            notes="placeholder Decoy/Vaal slot",
                        ),
                    ),
                    notes="Movement skills.",
                ),
                GemLink(
                    slot=ItemSlot.GLOVES,
                    sockets=4,
                    gems=(
                        _g("Cast When Damage Taken Support", level=1, quality=0, is_support=True),
                        _g("Molten Shell", level=10, quality=0, notes="trigger automatico"),
                        _g("Steelskin", level=1, quality=0, notes="defensive"),
                        _g("Enduring Cry", level=8, quality=0, notes="EC + life regen"),
                    ),
                    notes="CWDT 1 setup defensive.",
                ),
            ),
        ),
        StageGemLinks(
            stage_key="mid_campaign",
            notes=(
                "Atto 5-7. Primo lab → Unflinching → SWITCH a Righteous Fire. "
                "Springleaf shield obbligatorio. Holy Flame Totem rimane per i boss."
            ),
            links=(
                GemLink(
                    slot=ItemSlot.BODY_ARMOUR,
                    sockets=6,
                    color_pattern="RRRRRR",
                    gems=(
                        _g("Righteous Fire", level=18, quality=20),
                        _g("Burning Damage Support", level=18, quality=20, is_support=True),
                        _g("Concentrated Effect Support", level=18, quality=20, is_support=True),
                        _g("Combustion Support", level=18, quality=20, is_support=True),
                        _g(
                            "Awakened Burning Damage Support",
                            level=1,
                            quality=0,
                            is_support=True,
                            notes="cheap level 1 entry, ~5 chaos",
                        ),
                        _g(
                            "Empower Support",
                            level=3,
                            quality=0,
                            is_support=True,
                            notes="livella Empower 1→3 progressivo",
                        ),
                    ),
                    notes="Body 6L Tabula ancora. Tutti gem to level 18-20 entro fine atto.",
                ),
                GemLink(
                    slot=ItemSlot.HELMET,
                    sockets=4,
                    gems=(
                        _g("Holy Flame Totem", level=18, quality=20),
                        _g("Multiple Totems Support", level=18, quality=20, is_support=True),
                        _g("Combustion Support", level=18, quality=20, is_support=True),
                        _g("Faster Casting Support", level=18, quality=20, is_support=True),
                    ),
                    notes="Holy Flame Totem ancora utile come single-target boss.",
                ),
                GemLink(
                    slot=ItemSlot.GLOVES,
                    sockets=4,
                    gems=(
                        _g("Cast When Damage Taken Support", level=1, quality=0, is_support=True),
                        _g("Molten Shell", level=10, quality=0),
                        _g("Steelskin", level=1, quality=0),
                        _g("Enduring Cry", level=10, quality=0),
                    ),
                    notes="CWDT 1 setup invariato.",
                ),
                GemLink(
                    slot=ItemSlot.BOOTS,
                    sockets=4,
                    gems=(
                        _g("Determination", level=18, quality=20, notes="aura armour"),
                        _g("Purity of Fire", level=18, quality=20, notes="aura fire res"),
                        _g("Vitality", level=18, quality=20, notes="aura life regen"),
                        _g("Flame Dash", level=18, quality=20, notes="movement"),
                    ),
                    notes="Aura suite + movement.",
                ),
            ),
        ),
        StageGemLinks(
            stage_key="end_campaign",
            notes=(
                "Atto 8-10 + Kitava. Awakened Burning Damage 2-3 (~5-15 div). "
                "Switch a Vaal Molten Shell come panic button. Body 6L craftato."
            ),
            links=(
                GemLink(
                    slot=ItemSlot.BODY_ARMOUR,
                    sockets=6,
                    color_pattern="RRRRRR",
                    gems=(
                        _g("Righteous Fire", level=20, quality=20),
                        _g("Awakened Burning Damage Support", level=2, quality=0, is_support=True),
                        _g("Concentrated Effect Support", level=20, quality=20, is_support=True),
                        _g("Combustion Support", level=20, quality=20, is_support=True),
                        _g("Empower Support", level=3, quality=20, is_support=True),
                        _g(
                            "Elemental Focus Support",
                            level=20,
                            quality=20,
                            is_support=True,
                            notes="alternativa: Efficacy",
                        ),
                    ),
                    notes="Body 6L craftato. Awakened Burning 2 = ~5 div.",
                ),
                GemLink(
                    slot=ItemSlot.HELMET,
                    sockets=4,
                    gems=(
                        _g("Cast When Damage Taken Support", level=1, quality=20, is_support=True),
                        _g(
                            "Vaal Molten Shell",
                            level=10,
                            quality=20,
                            notes="vaal panic + auto-trigger",
                        ),
                        _g("Steelskin", level=1, quality=20),
                        _g("Enduring Cry", level=20, quality=20),
                    ),
                    notes="CWDT setup migliorato con Vaal Molten Shell.",
                ),
                GemLink(
                    slot=ItemSlot.GLOVES,
                    sockets=4,
                    gems=(
                        _g("Holy Flame Totem", level=20, quality=20),
                        _g("Multiple Totems Support", level=20, quality=20, is_support=True),
                        _g("Combustion Support", level=20, quality=20, is_support=True),
                        _g(
                            "Increased Critical Strikes Support",
                            level=20,
                            quality=20,
                            is_support=True,
                        ),
                    ),
                    notes="HFT setup boss-killer.",
                ),
                GemLink(
                    slot=ItemSlot.BOOTS,
                    sockets=4,
                    gems=(
                        _g("Determination", level=20, quality=20),
                        _g("Purity of Fire", level=20, quality=20),
                        _g("Vitality", level=20, quality=20),
                        _g("Flame Dash", level=20, quality=20),
                    ),
                    notes="Aura suite endgame-ready.",
                ),
            ),
        ),
        StageGemLinks(
            stage_key="early_mapping",
            notes=(
                "T1-T8 maps. Kaom's Heart → no socket body. Sposta i 6L gem nel "
                "weapon (+1 fire spell sceptre) o helm con 4 sockets RRRR. "
                "Gem alla level 21/20 corrupted dove possibile."
            ),
            links=(
                GemLink(
                    slot=ItemSlot.WEAPON_MAIN,
                    sockets=4,
                    color_pattern="RRRR",
                    gems=(
                        _g("Righteous Fire", level=21, quality=20, notes="vaal corrupted +1 level"),
                        _g("Awakened Burning Damage Support", level=3, quality=0, is_support=True),
                        _g("Concentrated Effect Support", level=21, quality=20, is_support=True),
                        _g("Empower Support", level=4, quality=0, is_support=True),
                    ),
                    notes="RF in weapon slot perché Kaom's Heart non ha socket.",
                ),
                GemLink(
                    slot=ItemSlot.HELMET,
                    sockets=4,
                    gems=(
                        _g("Holy Flame Totem", level=21, quality=20),
                        _g("Multiple Totems Support", level=21, quality=20, is_support=True),
                        _g("Combustion Support", level=20, quality=20, is_support=True),
                        _g(
                            "Awakened Increased Critical Strikes Support",
                            level=2,
                            quality=0,
                            is_support=True,
                        ),
                    ),
                    notes="HFT bossing single-target.",
                ),
                GemLink(
                    slot=ItemSlot.GLOVES,
                    sockets=4,
                    gems=(
                        _g("Cast When Damage Taken Support", level=1, quality=20, is_support=True),
                        _g("Vaal Molten Shell", level=20, quality=20),
                        _g("Steelskin", level=1, quality=20),
                        _g("Enduring Cry", level=20, quality=20),
                    ),
                    notes="CWDT panic.",
                ),
                GemLink(
                    slot=ItemSlot.BOOTS,
                    sockets=4,
                    gems=(
                        _g("Determination", level=20, quality=20),
                        _g("Purity of Fire", level=20, quality=20),
                        _g("Vitality", level=20, quality=20),
                        _g("Flame Dash", level=20, quality=20),
                    ),
                ),
            ),
        ),
        StageGemLinks(
            stage_key="end_mapping",
            notes=(
                "T14-T16 + Conqueror/Sirus/Maven. Awakened gem 4-5. Hands of "
                "the High Templar Curse on Hit Flammability."
            ),
            links=(
                GemLink(
                    slot=ItemSlot.WEAPON_MAIN,
                    sockets=4,
                    color_pattern="RRRR",
                    gems=(
                        _g("Righteous Fire", level=21, quality=20),
                        _g(
                            "Awakened Burning Damage Support",
                            level=5,
                            quality=20,
                            is_support=True,
                            notes="~10-15 div",
                        ),
                        _g(
                            "Awakened Empower Support",
                            level=4,
                            quality=0,
                            is_support=True,
                            notes="~25 div",
                        ),
                        _g("Concentrated Effect Support", level=21, quality=20, is_support=True),
                    ),
                    notes="+2 fire spell sceptre/staff = +2 levels effettivi sui gem.",
                ),
                GemLink(
                    slot=ItemSlot.HELMET,
                    sockets=4,
                    gems=(
                        _g("Flammability", level=20, quality=20),
                        _g("Awakened Curse on Hit Support", level=4, quality=0, is_support=True),
                        _g("Holy Flame Totem", level=21, quality=20),
                        _g("Multiple Totems Support", level=21, quality=20, is_support=True),
                    ),
                    notes="Hands of HT custom: Curse on Hit Flammability + HFT.",
                ),
                GemLink(
                    slot=ItemSlot.GLOVES,
                    sockets=4,
                    gems=(
                        _g("Cast When Damage Taken Support", level=1, quality=20, is_support=True),
                        _g("Vaal Molten Shell", level=20, quality=20),
                        _g("Increased Duration Support", level=20, quality=20, is_support=True),
                        _g("Enduring Cry", level=21, quality=20),
                    ),
                ),
                GemLink(
                    slot=ItemSlot.BOOTS,
                    sockets=4,
                    gems=(
                        _g("Determination", level=21, quality=20),
                        _g("Purity of Fire", level=21, quality=20),
                        _g("Vitality", level=21, quality=20),
                        _g("Flame Dash", level=21, quality=20),
                    ),
                ),
            ),
        ),
        StageGemLinks(
            stage_key="high_investment",
            notes=(
                "Uber pinnacle. Awakened gem 5/6 corrupted. Body Mirror-tier "
                "+2 socketed gems = +6-9 levels totali. Ashes of the Stars +1."
            ),
            links=(
                GemLink(
                    slot=ItemSlot.BODY_ARMOUR,
                    sockets=6,
                    color_pattern="RRRRRR",
                    gems=(
                        _g(
                            "Righteous Fire",
                            level=21,
                            quality=23,
                            alt="divergent",
                            notes="Divergent 21/23 corrupted",
                        ),
                        _g(
                            "Awakened Burning Damage Support",
                            level=5,
                            quality=23,
                            is_support=True,
                            notes="corrupted ~80-150 div",
                        ),
                        _g(
                            "Awakened Empower Support",
                            level=5,
                            quality=20,
                            is_support=True,
                            notes="~80 div",
                        ),
                        _g(
                            "Awakened Elemental Focus Support", level=5, quality=20, is_support=True
                        ),
                        _g("Concentrated Effect Support", level=21, quality=23, is_support=True),
                        _g("Combustion Support", level=21, quality=23, is_support=True),
                    ),
                    notes=(
                        "Body Mirror-tier +2 to Level of Socketed Gems "
                        "+ Ashes of the Stars +1 = effective level 21+5+5+1+1 = 33+ "
                        "su RF. DPS extreme."
                    ),
                ),
                GemLink(
                    slot=ItemSlot.HELMET,
                    sockets=4,
                    gems=(
                        _g("Flammability", level=21, quality=20),
                        _g("Awakened Curse on Hit Support", level=5, quality=0, is_support=True),
                        _g(
                            "Awakened Hextouch Support",
                            level=5,
                            quality=0,
                            is_support=True,
                            notes="alternativa per pinnacle",
                        ),
                        _g("Vaal Holy Flame Totem", level=21, quality=20),
                    ),
                    notes="Hands of HT Mirror-tier.",
                ),
                GemLink(
                    slot=ItemSlot.GLOVES,
                    sockets=4,
                    gems=(
                        _g("Cast When Damage Taken Support", level=1, quality=20, is_support=True),
                        _g("Vaal Molten Shell", level=20, quality=20),
                        _g(
                            "Awakened Increased Duration Support",
                            level=5,
                            quality=0,
                            is_support=True,
                        ),
                        _g("Enduring Cry", level=21, quality=20),
                    ),
                ),
                GemLink(
                    slot=ItemSlot.BOOTS,
                    sockets=4,
                    gems=(
                        _g("Determination", level=21, quality=23, alt="divergent"),
                        _g("Purity of Fire", level=21, quality=23, alt="divergent"),
                        _g("Vitality", level=21, quality=20),
                        _g(
                            "Awakened Generosity Support",
                            level=5,
                            quality=0,
                            is_support=True,
                            notes="boost aura efficacy",
                        ),
                    ),
                    notes="Aura suite Mirror-tier.",
                ),
            ),
        ),
    ),
)


# Registry — extend as more templates ship a gem progression.
GEM_REGISTRY: dict[str, GemProgression] = {
    "rf_pohx": RF_POHX_GEM_PROGRESSION,
}


def gem_progression_for(template_name: str) -> GemProgression | None:
    """Look up a gem progression by BuildTemplate.name. None when missing."""

    return GEM_REGISTRY.get(template_name)
