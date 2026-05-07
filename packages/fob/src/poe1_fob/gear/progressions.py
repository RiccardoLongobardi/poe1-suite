"""Hand-curated gear progressions per template.

Step 14 T2 ships RF Pohx Juggernaut as the reference. Each stage
specifies every relevant slot the build cares about with kind +
short notes for the UI.

When a template doesn't ship a gear progression, the planner UI
falls back to the existing KeyItem list (the items extracted from
the user's PoB).
"""

from __future__ import annotations

from poe1_core.models.enums import ItemSlot

from .models import GearProgression, StageGearSet, StageGearSlot

# ---------------------------------------------------------------------------
# RF Pohx Juggernaut — reference 6-stage gear progression
# ---------------------------------------------------------------------------


def _slot(slot: ItemSlot, item_name: str, kind: str, notes: str = "") -> StageGearSlot:
    """Tiny helper for readability — accepts kind as plain str."""

    return StageGearSlot(slot=slot, item_name=item_name, kind=kind, notes=notes)  # type: ignore[arg-type]


RF_POHX_GEAR_PROGRESSION = GearProgression(
    target_name="rf_pohx",
    stages=(
        StageGearSet(
            stage_key="early_campaign",
            overall_notes=(
                "Atto 1-4. Holy Flame Totem dalla quest 'Breaking Some Eggs'. "
                "NON usare Righteous Fire prima del primo lab — RF è "
                "self-damage e in atto non hai abbastanza life regen."
            ),
            slots=(
                _slot(
                    ItemSlot.HELMET,
                    "Goldrim",
                    "unique",
                    "Goldrim levelling helmet (1 alch): +35-40% all res. Fa res cap "
                    "fino a ~atto 6.",
                ),
                _slot(
                    ItemSlot.BODY_ARMOUR,
                    "Tabula Rasa",
                    "unique",
                    "Tabula Rasa 6L (~1 chaos): partire 6L da subito. Zero life ma in atto regge.",
                ),
                _slot(
                    ItemSlot.GLOVES,
                    "Lochtonial Caress",
                    "unique",
                    "Lochtonial Caress (~1 alch): random charge on hit + ele res.",
                ),
                _slot(
                    ItemSlot.BOOTS,
                    "Wanderlust",
                    "unique",
                    "Wanderlust (~1 alch): movement speed + cannot be frozen. "
                    "Drop-in bridge fino al primo set di rare.",
                ),
                _slot(
                    ItemSlot.BELT,
                    "Meginord's Girdle",
                    "unique",
                    "Meginord's Girdle (~1 alch): +50 strength + +20% increased "
                    "life. Cheap life boost.",
                ),
                _slot(
                    ItemSlot.AMULET,
                    "Karui Ward",
                    "unique",
                    "Karui Ward (~1 chaos): +20-30 dex/str/int + life. Bridge amulet completo.",
                ),
                _slot(
                    ItemSlot.RING,
                    "rare ring (life + 2 res)",
                    "leveling",
                    "Qualsiasi rare ring craftato con life + 2 resistance.",
                ),
                _slot(
                    ItemSlot.WEAPON_MAIN,
                    "Brightbeak",
                    "unique",
                    "Brightbeak (~1 chaos): +50% increased attack speed. "
                    "Per Holy Flame Totem cast speed boost.",
                ),
                _slot(
                    ItemSlot.WEAPON_OFFHAND,
                    "Springleaf",
                    "unique",
                    "Springleaf shield (~1 alch): MASSIVE life regen low life. "
                    "Quando swich a RF a level 33, Springleaf è essenziale.",
                ),
            ),
        ),
        StageGearSet(
            stage_key="mid_campaign",
            overall_notes=(
                "Atto 5-7. Primo lab → Unflinching → SWITCH a Righteous Fire. "
                "Springleaf shield è obbligatorio: il +50% life regen low-life "
                "cura il damage di RF in questa fase."
            ),
            slots=(
                _slot(
                    ItemSlot.HELMET,
                    "rare helmet (life + 2 res)",
                    "rare_craft",
                    "Helmet rare craftato: T1 life + 2 resistance + accuracy "
                    "(per Holy Flame Totem).",
                ),
                _slot(
                    ItemSlot.BODY_ARMOUR,
                    "Tabula Rasa",
                    "unique",
                    "Resta Tabula Rasa 6L (gem links matter più del life).",
                ),
                _slot(
                    ItemSlot.GLOVES,
                    "rare gloves (life + 2 res)",
                    "rare_craft",
                    "Gloves rare craftato: life + 2 res.",
                ),
                _slot(
                    ItemSlot.BOOTS,
                    "rare boots (movement + life)",
                    "rare_craft",
                    "Rare boots: 25%+ movement speed + life + 1 res.",
                ),
                _slot(
                    ItemSlot.BELT,
                    "Meginord's Girdle",
                    "unique",
                    "Meginord ancora bene a questo stage.",
                ),
                _slot(
                    ItemSlot.AMULET,
                    "Karui Ward",
                    "unique",
                    "Karui Ward o rare amulet con life + flat res.",
                ),
                _slot(
                    ItemSlot.RING,
                    "rare ring (life + 3 res)",
                    "rare_craft",
                    "Rare ring: life + 3 ele resistance + chaos res. Doppio: 2 ring slot.",
                ),
                _slot(
                    ItemSlot.WEAPON_MAIN,
                    "Brightbeak",
                    "unique",
                    "Brightbeak ancora vincente.",
                ),
                _slot(
                    ItemSlot.WEAPON_OFFHAND,
                    "Springleaf",
                    "unique",
                    "Springleaf OBBLIGATORIO post-RF switch.",
                ),
            ),
        ),
        StageGearSet(
            stage_key="end_campaign",
            overall_notes=(
                "Atto 8-10 + Kitava. Resistenze a 75% (Kitava taglia 30%). "
                "Switch a Rise of the Phoenix per max fire res over-cap."
            ),
            slots=(
                _slot(
                    ItemSlot.HELMET,
                    "rare helmet (life + 2 res + accuracy)",
                    "rare_craft",
                    "Rare helmet craftato. T1 life + 2 res + accuracy.",
                ),
                _slot(
                    ItemSlot.BODY_ARMOUR,
                    "rare body 4L (life + 2 res)",
                    "rare_craft",
                    "Body 4L craftato (alteration spam): T1 life% + 2 resistance. "
                    "Il 6L Tabula non serve più, RF non vuole socket.",
                ),
                _slot(
                    ItemSlot.GLOVES,
                    "rare gloves (life + 2 res)",
                    "rare_craft",
                    "Rare gloves: life + 2 res. Eldritch implicit suppression.",
                ),
                _slot(
                    ItemSlot.BOOTS,
                    "rare boots (30% MS + life)",
                    "rare_craft",
                    "Rare boots: 30% movement speed + life + 1 res + suppression.",
                ),
                _slot(
                    ItemSlot.BELT,
                    "Stygian Vise rare",
                    "rare_craft",
                    "Stygian Vise rare belt (+1 abyss jewel socket): T1 life + 2 res + flat life.",
                ),
                _slot(
                    ItemSlot.AMULET,
                    "rare amulet (+1 fire/spell skill)",
                    "rare_craft",
                    "Rare amulet con +1 fire spell skill o +1 spell skill + life + res.",
                ),
                _slot(
                    ItemSlot.RING,
                    "rare ring (life + 3 res)",
                    "rare_craft",
                    "Rare ring: life + 3 ele resistance + accuracy.",
                ),
                _slot(
                    ItemSlot.WEAPON_MAIN,
                    "Brightbeak",
                    "unique",
                    "Brightbeak fino a Kitava poi switch a +1 fire spell sceptre.",
                ),
                _slot(
                    ItemSlot.WEAPON_OFFHAND,
                    "Rise of the Phoenix",
                    "unique",
                    "Rise of the Phoenix shield (~1-2 div): +8% max fire res. "
                    "Permette over-cap fire res a 89% (boost RF damage).",
                ),
            ),
        ),
        StageGearSet(
            stage_key="early_mapping",
            overall_notes=("T1-T8 maps. Kaom's Heart entry point. Cluster jewel fire damage."),
            slots=(
                _slot(
                    ItemSlot.HELMET,
                    "rare helmet (life + res + Eldritch implicit)",
                    "rare_craft",
                    "Helmet rare con Eldritch implicit suppression + T1 life + 2 res.",
                ),
                _slot(
                    ItemSlot.BODY_ARMOUR,
                    "Kaom's Heart",
                    "unique",
                    "Kaom's Heart (~5-15 div): +500 life flat + massive "
                    "damage da '%life increased'. Niente socket ma RF non li "
                    "vuole.",
                ),
                _slot(
                    ItemSlot.GLOVES,
                    "rare gloves (life + 2 res + suppression)",
                    "rare_craft",
                    "Rare gloves Eldritch crafted: spell suppression + life + 2 res.",
                ),
                _slot(
                    ItemSlot.BOOTS,
                    "Sin Trek",
                    "unique",
                    "Sin Trek boots (~3-5 div): +20-30% movement speed + "
                    "evasion + cannot be frozen/shocked/ignited. RF-friendly.",
                ),
                _slot(
                    ItemSlot.BELT,
                    "Stygian Vise rare (life + abyss jewel)",
                    "rare_craft",
                    "Stygian Vise rare con T1 life + 2 res + flat life. Abyss "
                    "jewel: life + flat res / fire damage.",
                ),
                _slot(
                    ItemSlot.AMULET,
                    "rare amulet (+1 fire skill)",
                    "rare_craft",
                    "Rare amulet con +1 fire spell skill + T1 life + "
                    "Anointment 'Charisma' o 'Whispers of Doom'.",
                ),
                _slot(
                    ItemSlot.RING,
                    "rare ring (life + 3 res + flat fire)",
                    "rare_craft",
                    "Rare ring: T1 life + 3 ele resistance + flat fire damage.",
                ),
                _slot(
                    ItemSlot.WEAPON_MAIN,
                    "+1 fire spell sceptre",
                    "rare_craft",
                    "Rare sceptre/wand con +1 to all fire spell skill gems + "
                    "spell damage + cast speed.",
                ),
                _slot(
                    ItemSlot.WEAPON_OFFHAND,
                    "Rise of the Phoenix",
                    "unique",
                    "Rise of the Phoenix per max fire res over-cap.",
                ),
            ),
        ),
        StageGearSet(
            stage_key="end_mapping",
            overall_notes=(
                "T14-T16 + Conqueror/Sirus/Maven. Awakened gem 4-5, "
                "Hands of the High Templar custom craftato."
            ),
            slots=(
                _slot(
                    ItemSlot.HELMET,
                    "Hands of the High Templar (Curse on Hit Flammability)",
                    "rare_craft",
                    "Hands of the High Templar custom: Curse on Hit "
                    "Flammability + +1 socketed gem level + T1 life. "
                    "Costo ~30-50 div.",
                ),
                _slot(
                    ItemSlot.BODY_ARMOUR,
                    "Loreweave (or Kaom's Heart)",
                    "unique",
                    "Loreweave 6L (~10-20 div) per cap 80% all res. "
                    "Alternativa: Kaom's Heart se preferisci pure life.",
                ),
                _slot(
                    ItemSlot.GLOVES,
                    "rare gloves Eldritch-crafted (suppression + life)",
                    "rare_craft",
                    "Rare gloves con spell suppression + T1 life + 2 res + "
                    "Eldritch implicit (life on kill).",
                ),
                _slot(
                    ItemSlot.BOOTS,
                    "Sin Trek o rare 30%MS",
                    "rare_craft",
                    "Sin Trek a budget, oppure rare boots T1 life + "
                    "movement speed 30%+ + suppression.",
                ),
                _slot(
                    ItemSlot.BELT,
                    "Stygian Vise rare endgame",
                    "rare_craft",
                    "Stygian Vise rare con T1 life + 2 res + flat life + "
                    "fire damage. Doppio abyss jewel non possibile (1 socket).",
                ),
                _slot(
                    ItemSlot.AMULET,
                    "rare amulet +1 fire skill + Anointment",
                    "rare_craft",
                    "Rare amulet con +1 fire spell skill + life + 'Charisma' "
                    "anointment per aura efficiency.",
                ),
                _slot(
                    ItemSlot.RING,
                    "rare ring T1 life + 3 res + leech",
                    "rare_craft",
                    "Rare ring: T1 life + 3 ele resistance + life leech "
                    "(perfetto se hai mancanza di life sustain).",
                ),
                _slot(
                    ItemSlot.WEAPON_MAIN,
                    "+2 fire spell sceptre / staff",
                    "rare_craft",
                    "Rare sceptre/staff con +2 to all fire spell skill gems + "
                    "T1 spell damage. Costo ~30-80 div.",
                ),
                _slot(
                    ItemSlot.WEAPON_OFFHAND,
                    "Rise of the Phoenix",
                    "unique",
                    "Rise of the Phoenix sempre.",
                ),
            ),
        ),
        StageGearSet(
            stage_key="high_investment",
            overall_notes=(
                "Uber pinnacle. Mageblood (250-300 div), body Mirror-tier "
                "+2 socketed gems, Forbidden Flame+Flesh per Soul of Steel "
                "raddoppiato. Investment 800-1500+ div."
            ),
            slots=(
                _slot(
                    ItemSlot.HELMET,
                    "Hands of the High Templar custom (Awakened Curse on Hit)",
                    "rare_craft",
                    "Hands of the High Templar Mirror-tier: Curse on Hit "
                    "Flammability + +2 socketed gems + suppression. ~80-150 div.",
                ),
                _slot(
                    ItemSlot.BODY_ARMOUR,
                    "rare body Mirror-tier (+2 socketed gems)",
                    "rare_craft",
                    "Body 6L Mirror-tier: +2 to Level of Socketed Gems + T1 "
                    "life + 20% chaos res + suppression. Awakener's Orb crafted. "
                    "Costo 200-500 div.",
                ),
                _slot(
                    ItemSlot.GLOVES,
                    "rare gloves Mirror-tier (suppression + life + Eldritch ele)",
                    "rare_craft",
                    "Gloves Mirror-tier: T1 life + 100%+ spell suppression + "
                    "Eldritch ele weakness on hit. ~50-100 div.",
                ),
                _slot(
                    ItemSlot.BOOTS,
                    "rare boots Mirror-tier (35%MS + Tailwind)",
                    "rare_craft",
                    "Boots Mirror-tier: 35%+ movement speed + T1 life + "
                    "Tailwind (Two-Toned implicit) + 2 res. ~100-150 div.",
                ),
                _slot(
                    ItemSlot.BELT,
                    "Mageblood",
                    "unique",
                    "Mageblood (~250-300 div): tutti i flask permanenti. "
                    "Cinderswallow Urn = +10% life + crit, Forbidden Taste "
                    "purification, ecc.",
                ),
                _slot(
                    ItemSlot.AMULET,
                    "Ashes of the Stars",
                    "unique",
                    "Ashes of the Stars (~30-50 div): +1 to Level of Socketed "
                    "Gems su amulet. Combinato con +2 body = +9 levels totali.",
                ),
                _slot(
                    ItemSlot.RING,
                    "rare ring Mirror-tier",
                    "rare_craft",
                    "Rare ring Mirror-tier: T1 life + 3 res + flat fire damage "
                    "+ 2 mod open prefix. ~50-100 div.",
                ),
                _slot(
                    ItemSlot.WEAPON_MAIN,
                    "+2 fire spell staff Mirror-tier",
                    "rare_craft",
                    "Rare staff Mirror-tier: +2 to all fire spell skill gems + "
                    "T1 spell damage + cast speed + critical strike multi. "
                    "~100-300 div.",
                ),
                _slot(
                    ItemSlot.WEAPON_OFFHAND,
                    "(none — 2H staff)",
                    "skip",
                    "Switching a 2H staff per maximum +2 to all fire spell skill "
                    "gems + bigger ele damage.",
                ),
                _slot(
                    ItemSlot.JEWEL,
                    "Forbidden Flame + Flesh (Soul of Steel)",
                    "unique",
                    "Forbidden Flame + Flesh matched pair su 'Soul of Steel'. "
                    "Doppia ascendancy notable = double armour scaling. "
                    "Costo coppia 60-150 div.",
                ),
            ),
        ),
    ),
)


# Registry — extend as more templates ship a gear progression.
GEAR_REGISTRY: dict[str, GearProgression] = {
    "rf_pohx": RF_POHX_GEAR_PROGRESSION,
}


def gear_progression_for(template_name: str) -> GearProgression | None:
    """Look up a gear progression by BuildTemplate.name. None when missing."""

    return GEAR_REGISTRY.get(template_name)
