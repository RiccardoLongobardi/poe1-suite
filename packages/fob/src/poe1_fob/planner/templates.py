"""Build-archetype templates for the 6-stage planner.

The 6-stage plan needs **timeline content** (gem progression, lab
order, tree milestones, "what to wear", trigger-to-advance) for every
stage. That content is build-specific: a Righteous Fire Juggernaut's
day-1 looks nothing like a Vortex Occultist's day-1.

This module ships:

* :class:`StagePlanContent` — the per-stage payload a template
  produces (gem changes, tree changes, rationale, next trigger).
* :class:`BuildTemplate` Protocol — the callable shape any template
  must satisfy.
* :class:`GenericTemplate` — sane fallback for any build, derived
  from the build's main skill + support gems. Always works.
* :class:`RfPohxTemplate` — fully detailed reference template for
  Righteous Fire Juggernaut (Pohx-style). Demonstrates how a
  hand-tuned template produces guidance that's accurate enough for
  a real day-0-to-day-100 run.
* :func:`pick_template` — the registry dispatch: matches a
  :class:`Build` against known templates, falls back to
  :class:`GenericTemplate` when nothing matches.

Adding a new template
---------------------
Templates are designed to be small and readable. Subclass
:class:`GenericTemplate` and override only the per-stage methods you
need; the base produces sensible Italian copy for everything else.
Register the new class in :data:`TEMPLATE_REGISTRY` keyed by a
matcher function that accepts a :class:`Build` and returns a bool.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from poe1_core.models import Build

from .stages import (
    EARLY_CAMPAIGN,
    EARLY_MAPPING,
    END_CAMPAIGN,
    END_MAPPING,
    HIGH_INVESTMENT,
    MID_CAMPAIGN,
    StageSpec,
)


@dataclass(frozen=True)
class StagePlanContent:
    """Per-stage template output consumed by :class:`PlannerService`.

    All fields are lists of short Italian copy strings the planner
    drops directly into the corresponding :class:`PlanStage` fields.
    Templates may override the spec defaults (rationale, trigger) when
    they have build-specific advice; keeping them ``None`` falls back
    to the static :class:`StageSpec` text.
    """

    gem_changes: list[str] = field(default_factory=list)
    tree_changes: list[str] = field(default_factory=list)
    rationale_override: str | None = None
    trigger_override: str | None = None


class BuildTemplate(Protocol):
    """Callable that produces stage content for one build archetype."""

    name: str

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent: ...


# ---------------------------------------------------------------------------
# Generic fallback — derives content from the Build's main_skill text
# ---------------------------------------------------------------------------


class GenericTemplate:
    """Default template: works for any build, no archetype knowledge.

    Generates per-stage gem advice from ``build.main_skill`` and
    ``build.support_gems``. Tree changes stay empty (we'd need PoB
    passive-tree decoding to do better). The rationale falls through
    to the spec default.
    """

    name: str = "generic"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        skill = build.main_skill or "(skill principale)"
        first_supports = ", ".join(build.support_gems[:3]) or "(supports dalle quest)"

        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    f"Setup levelling: usa {skill} appena disponibile.",
                    f"Supports iniziali: {first_supports}.",
                    "Usa Quicksilver flask + Movement skill (Leap Slam / Frostblink / Flame Dash).",
                ]
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    f"Conferma {skill} come main DPS.",
                    "Aggiungi i support gem dalla Library Trial / Siosa quest reward.",
                    "Primo lab a level ~33 → ascendancy iniziale.",
                ]
            )
        if stage.key == "end_campaign":
            return StagePlanContent(
                gem_changes=[
                    f"Tutti i support gem di {skill} a level 18-20.",
                    "Pre-Kitava: re-sista 75% (Kitava taglia 30%).",
                    "Cruel + Merciless lab: ascendancy completa.",
                ]
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L (Tabula come stop-gap, poi 6L craftato/comprato).",
                    "Quality 20% su tutti i gem core.",
                    "Atlas tree: Maven Awakening + Eldritch Altars priorità.",
                ]
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Porta i support gem core a 20/20 (level 20 + quality 20).",
                    "Compra le versioni 21/20 corrupted dei support più importanti.",
                    "Inizia a sostituire con awakened gem dove esistono.",
                ]
            )
        if stage.key == "high_investment":
            gem_list: list[str] = [
                "Awakened support gem level 5 (mirror-tier su level 6).",
                "+1/+2 to Level of Socketed Gems su body / helmet / weapon.",
            ]
            if build.support_gems:
                gem_list.append("Vaal corrupted dei tuoi support per double-corrupted upgrade.")
            return StagePlanContent(gem_changes=gem_list)
        return StagePlanContent()


# ---------------------------------------------------------------------------
# RF Pohx — fully detailed reference template
# ---------------------------------------------------------------------------


class RfPohxTemplate(GenericTemplate):
    """Righteous Fire Juggernaut (Pohx-style) reference template.

    The signature day-0-to-day-100 RF Jugg path:

    * **Early Campaign** — Holy Flame Totem dalla quest atto 1 +
      Frostblink per movement. No RF prima del lab.
    * **Mid Campaign** — Holy Flame Totem regge fino al primo lab,
      poi switch a RF appena hai Endurance Charges (Unflinching).
      Springleaf shield essenziale.
    * **End Campaign** — RF è main DPS. Brightbeak + Springleaf +
      Karui Ward + Rise of the Phoenix dopo Kitava.
    * **Early Mapping** — Kaom's Heart sostituisce il body craftato,
      Sin Trek per movement speed, primi cluster fire.
    * **End Mapping** — Awakened Burning Damage 4-5, Hands of the
      High Templar custom-corrupted, body 6L con Awakened Empower.
    * **High Investment** — Mageblood, body Mirror-tier con +2
      socketed gems, Forbidden Flame+Flesh per Soul of Steel
      raddoppiato.

    See https://www.pohx.net for the full guide.
    """

    name: str = "rf_pohx"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        # ``build`` is intentionally unused: the RF Pohx path is the
        # same regardless of the build's specific support gem list.
        # Future per-build tweaks can read it.
        del build
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: prendi Holy Flame Totem dalla quest 'Breaking Some Eggs'.",
                    "Atto 2-3: aggiungi Multiple Totems + Combustion + Faster Casting.",
                    "Frostblink come movement skill (gratis dalla quest).",
                    "**NON** usare Righteous Fire prima del lab.",
                ],
                rationale_override=(
                    "Fase Holy Flame Totem. RF non è ancora viable senza Endurance "
                    "Charges - useresti più HP del life regen sostenibile e moriresti "
                    "subito. Holy Flame Totem ti porta fino al primo lab senza problemi."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab (level ~33): prendi **Unflinching** (Endurance Charges + max).",
                    "Subito dopo il lab: switch a Righteous Fire come main DPS.",
                    "Aggiungi Determination + Purity of Fire come aura.",
                    "Holy Flame Totem rimane come DPS supplementare per i boss.",
                ],
                tree_changes=[
                    "Cluster di Burning Damage attorno alla Templar Fire area.",
                    "Life clusters: Heart of Flame + Tireless dal Marauder start.",
                ],
                rationale_override=(
                    "Switch a RF dopo Unflinching. Springleaf shield è obbligatorio: "
                    "+50% life regen cura praticamente tutto il danno auto-inflitto di RF "
                    "in questa fase. Karui Ward amulet + Goldrim per i res."
                ),
                trigger_override=(
                    "Quando il second lab (Cruel) è morto e hai Brightbeak + Springleaf "
                    "+ res cap a 75 + Eldritch Battery se serve, sei pronto per Kitava."
                ),
            )
        if stage.key == "end_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Merciless lab: prendi **Unbreakable** (armour scaling massive).",
                    "RF + Awakened Burning Damage non-awakened (cheap) + Concentrated Effect.",
                    "Determination + Purity of Fire + Vitality (low reservation).",
                    "Holy Flame Totem trigger su Vaal Molten Shell per defense layer.",
                ],
                tree_changes=[
                    "Picchetta Soul of Steel (max armour) e Diamond Skin.",
                    "Body 4L craftato (alteration spam life + res) come transition.",
                ],
                rationale_override=(
                    "Post-Kitava. RF + Vaal Molten Shell ti rendono praticamente "
                    "invincibile in mapping. Rise of the Phoenix shield (1-2 div) "
                    "porta fire res over-cap a 89%, incrementando il damage di RF."
                ),
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Aumenta i support gem core a level 18-20.",
                    "Primo cluster fire damage (~3-5 div).",
                    "Vaal Molten Shell come panic button.",
                    "Sin Trek boots (~3-5 div) per movement speed.",
                ],
                tree_changes=[
                    "Body unique: Kaom's Heart appena puoi (~5-15 div). +1000 life flat.",
                    "Atlas: priority a Maven Awakening lvl 3+ → Searing Exarch.",
                ],
                rationale_override=(
                    "Kaom's Heart è il signature di RF Jugg: niente socket ma +500 life "
                    "flat e damage massive da '%life increased'. Da qui in poi RF è "
                    "comodo in T16."
                ),
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Burning Damage **5** (~10-15 div).",
                    "Awakened Empower 4 (~25 div).",
                    "Concentrated Effect 21/20 corrupted (~3-5 div).",
                    "Tutti i Vaal corrupted level 21 dei support core.",
                ],
                tree_changes=[
                    "Hands of the High Templar craftato custom (Curse on Hit + Damage).",
                    "Loreweave (alternativa a Kaom's Heart se vuoi 6L + 80% all res).",
                    "Cluster jewel high-roll: Burning Bright + Sleepless Sentries.",
                ],
                rationale_override=(
                    "Switch da Kaom's Heart a un body 6L (Loreweave per cap 80% res, "
                    "oppure rare 6L con +1 socketed). Hands of High Templar ti "
                    "raddoppia la sopravvivenza con Curse on Hit di Flammability."
                ),
            )
        if stage.key == "high_investment":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Burning Damage **6** corrupted (~80-100 div).",
                    "Awakened Empower **5** (~80 div).",
                    "Vaal corrupted con Awakened gem doppio: + 1 level + tag.",
                ],
                tree_changes=[
                    "Mageblood (~250-300 div): tutti i flask permanenti.",
                    "Body Mirror-tier rare: +2 socketed gems / 20% chaos res / suppression.",
                    "Forbidden Flame + Flesh per Soul of Steel doppio (Jugg ascendancy).",
                ],
                rationale_override=(
                    "Mageblood è il game-changer per RF: Cinderswallow Urn permanente "
                    "= 10% increased life + chance crit. Body mirror con +2 socketed "
                    "gem = +6 levels totali sui 6 link, damage moltiplicato."
                ),
            )
        return StagePlanContent()


# ---------------------------------------------------------------------------
# Slam / Marauder templates
# ---------------------------------------------------------------------------


class BoneshatterTemplate(GenericTemplate):
    """Boneshatter Juggernaut/Berserker — phys melee strike con trauma stack.

    Boneshatter accumula trauma stack che aumentano il danno preso ma anche
    quello inflitto. Levelling con Sunder/Ground Slam fino allo sblocco a
    level 28 (atto 4 reward). Jugg gioca Unstoppable + Unbreakable per
    sopravvivere agli stack alti; Berserker accelera con Crave the Slaughter
    + Aspect of Carnage. Heatshiver helmet + Hatred = variant cold-conversion
    per scalare Hatred + Watcher's Eye.
    """

    name: str = "boneshatter_marauder"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder (quest 'Mercy Mission') o Ground Slam come levelling.",
                    "Atto 4 (level ~28): Boneshatter sblocca; switch su 4L con Multistrike + Melee Phys + Pulverise.",
                    "Leap Slam come movement, Ancestral Protector totem per attack speed.",
                ],
                rationale_override=(
                    "Boneshatter scala con stack di trauma: ogni colpo aumenta il danno "
                    "preso ma anche quello inflitto. In atto 1-3 il setup non c'è ancora "
                    "(servono life regen + armour), quindi Sunder/Ground Slam sono più "
                    "comodi fino al primo lab."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Unflinching (Jugg) o Crave the Slaughter (Berserker).",
                    "Boneshatter + Multistrike + Brutality + Pulverise + Melee Phys + Fortify.",
                    "Pride aura + War Banner per phys taken multi sui mob.",
                ],
                tree_changes=[
                    "Cluster phys melee + life clusters dal Marauder start.",
                    "Brightbeak come transition weapon (1H phys + +50% attack speed).",
                ],
                rationale_override=(
                    "Switch a Boneshatter dopo Unflinching: gli Endurance Charges "
                    "compensano il phys taken multi degli stack. Berserker invece corre "
                    "alti stack con Aspect of Carnage."
                ),
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Boneshatter + Awakened Multistrike + Awakened Melee Phys + Awakened Brutality + Pulverise + Fortify.",
                    "+1 to Strike Skills 1H mace o axe +2 socketed (~10-30 div).",
                    "Heatshiver helmet variant (~3-5 div): chill = cold conversion per Hatred scaling.",
                ],
                tree_changes=[
                    "Cluster jewel: Fuel the Fight + Feed the Fury per attack speed.",
                    "Brass Dome body unique (massive armour) o rare 6L con +1 socketed.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Melee Phys 5 + Awakened Brutality 5 + Awakened Multistrike 5.",
                    "21/20 Boneshatter corrupted + Awakened Fortify 5 (~30 div).",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Unstoppable (Jugg) o Aspect of Carnage (Berserker) raddoppiato.",
                    "Watcher's Eye Pride 'increased phys damage taken' (~80+ div).",
                ],
            )
        return super().for_stage(stage, build)


class EarthshatterJuggTemplate(GenericTemplate):
    """Earthshatter Juggernaut — slam phys con detonazione spikes.

    Earthshatter pianta spikes nel terreno che esplodono al prossimo slam,
    raddoppiando il damage AoE. Scala con slam/warcry tags + Brutality.
    Jugg Unflinching + Unstoppable + Unbreakable = build slam tank classico.
    Tukohama's Coffer body per +X to Slam socketed o craft +2 to Slam Skills.
    """

    name: str = "earthshatter_juggernaut"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder + Ancestral Protector + Leap Slam dalle quest.",
                    "Atto 3 (Library Siosa): Earthshatter sblocca; metti su 4L con Multistrike + Melee Phys + Pulverise.",
                    "Aggiungi Rallying Cry o Ancestral Cry per warcry damage multi.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Unflinching + Endurance Charge generation.",
                    "Earthshatter + Multistrike + Awakened Brutality (cheap) + Pulverise + Melee Phys + Fortify.",
                    "Aggiungi Seismic Cry: warcry → +slam damage al colpo successivo.",
                ],
                tree_changes=[
                    "Resolute Technique area dal tree centrale (zero crit/accuracy needed).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Earthshatter + Awakened Brutality + Awakened Melee Phys + Pulverise + Multistrike + Awakened Fortify.",
                    "+2 to Slam Skills 2H mace craft (~10-30 div) o Marohi Erqi unique 2H.",
                ],
                tree_changes=[
                    "Tukohama's Coffer body o rare 6L con +1 socketed gems.",
                    "Cluster jewel: Fuel the Fight + Quick Getaway + Feed the Fury.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brutality 5 + Awakened Melee Phys 5 + Awakened Fortify 5.",
                    "21/20 Earthshatter corrupted + Pulverise 21/20.",
                ],
                tree_changes=[
                    "Hands of the High Templar custom craft (Curse on Hit + +1 Slam socketed).",
                    "Helmet enchant: Earthshatter increased damage 40%.",
                ],
            )
        return super().for_stage(stage, build)


class TectonicSlamChieftainTemplate(GenericTemplate):
    """Tectonic Slam Chieftain — fire slam consumando Endurance Charges.

    Tectonic Slam consuma Endurance Charges per emettere fissures di fuoco.
    Chieftain Tukohama, War's Herald + Ngamahu, True Flame convertono phys
    → fire e generano EC. The Magnate belt + Kaom's Way ring per charge
    generation infinita; Combustion + Awakened Fire Pen per pen finale.
    """

    name: str = "tectonic_slam_chieftain"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder + Leap Slam + Ancestral Protector.",
                    "Atto 3 reward: Tectonic Slam sblocca; metti su 4L con Multistrike + Combustion + Fire Pen.",
                    "Anger + Herald of Ash low-level per damage scaling.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Tukohama, War's Herald (Endurance Charge gen + life regen).",
                    "Tectonic Slam + Multistrike + Combustion + Fire Pen + Awakened Brutality (cheap) + Pulverise.",
                    "Aspect of the Crab per phys mitigation extra.",
                ],
                tree_changes=[
                    "Marauder area: Tireless + Heart of Flame + Diamond Skin.",
                    "The Magnate belt unique per +1 Endurance Charge from items.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Tectonic + Awakened Fire Pen + Awakened Brutality + Combustion + Awakened Melee Phys + Multistrike.",
                    "+2 to Strike/Slam mace o axe craft (~10-30 div).",
                    "Stampede boots per movement speed indipendente da modificatori.",
                ],
                tree_changes=[
                    "Kaom's Way rings (1-2): +1 Endurance Charge ognuno.",
                    "Cluster jewel: fire damage + slam.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Fire Pen 5 + Awakened Brutality 5 + Awakened Melee Phys 5.",
                    "21/20 Tectonic Slam corrupted + Combustion 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Ngamahu, True Flame doppio (full phys → fire).",
                    "Helmet enchant: Tectonic Slam 30% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class MoltenStrikeChieftainTemplate(GenericTemplate):
    """Molten Strike Chieftain — phys-to-fire melee strike + projectile.

    Molten Strike colpisce localmente e spara projectile fire AoE.
    Chieftain Tukohama, War's Herald + Ngamahu, True Flame convertono
    100% phys → fire. Hrimsorrow / Yoke of Suffering, Avatar of Fire
    keystone per ulteriore conversione. Build classico bossing single-target
    con projectile clear.
    """

    name: str = "molten_strike_chieftain"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Molten Strike disponibile da subito (quest 'Mercy Mission').",
                    "Setup 4L: Molten Strike + Ancestral Call + Multistrike + Combustion.",
                    "Leap Slam come movement, Anger come aura.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Tukohama, War's Herald (Endurance Charge gen + life regen).",
                    "Molten Strike + Multistrike + Awakened Fire Pen + Elemental Damage with Attacks + Combustion + Ancestral Call.",
                    "Aspect of the Crab + Herald of Ash low-level.",
                ],
                tree_changes=[
                    "Avatar of Fire keystone: 100% phys → fire conversion.",
                    "Templar fire area: Heart of Flame + Diamond Skin.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Molten Strike + Awakened Multistrike + Awakened Fire Pen + Awakened Elemental Damage with Attacks + Combustion + Inspiration.",
                    "Hrimsorrow gloves o Yoke of Suffering amulet per ele conversion.",
                    "Ngamahu's Flame mace (~3-5 div) come transition weapon.",
                ],
                tree_changes=[
                    "Ngamahu's Sign ring per chance per Endurance Charge on hit.",
                    "Cluster jewel: Fuel the Fight + Burning Bright per fire damage.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Multistrike 5 + Awakened Fire Pen 5 + Awakened Elemental Damage with Attacks 5.",
                    "21/20 Molten Strike corrupted + Inspiration 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Ngamahu, True Flame doppio.",
                    "Watcher's Eye Anger 'Increased Fire Damage' (~30-60 div).",
                    "Helmet enchant: Molten Strike +2 projectiles.",
                ],
            )
        return super().for_stage(stage, build)


class GroundSlamJuggTemplate(GenericTemplate):
    """Ground Slam Juggernaut — slam phys signature Marauder.

    Ground Slam (e la transfigured Ground Slam of Earthshaking) è la
    skill Marauder day-1 più rappresentativa. Jugg Unflinching +
    Unbreakable scala armour + life regen massivamente. Marohi Erqi
    2H mace per damage flat enorme; transition a +2 to Slam Skills
    crafted 2H per endgame. Resolute Technique area centrale.
    """

    name: str = "ground_slam_juggernaut"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Ground Slam dalla quest 'Mercy Mission' — skill day-1 Marauder.",
                    "Setup 4L: Ground Slam + Ruthless + Melee Phys + Pulverise.",
                    "Leap Slam come movement, Ancestral Protector totem.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Unflinching (Endurance Charges + max).",
                    "Ground Slam + Ruthless + Awakened Brutality (cheap) + Pulverise + Melee Phys + Fortify.",
                    "Pride aura + War Banner per phys taken multi.",
                ],
                tree_changes=[
                    "Resolute Technique area centrale (zero accuracy needed).",
                    "Marauder area: Tireless + Heart of the Warrior + Diamond Skin.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Ground Slam + Awakened Melee Phys + Awakened Brutality + Pulverise + Ruthless + Awakened Fortify.",
                    "Marohi Erqi 2H mace (~1-3 div) come transition; +2 to Slam Skills 2H mace endgame.",
                    "Considera Ground Slam of Earthshaking (transfigured) per AoE permanente raddoppiata.",
                ],
                tree_changes=[
                    "Cluster jewel: Quick Getaway + Fuel the Fight + Feed the Fury.",
                    "Brass Dome body unique o rare 6L con +1 socketed.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Melee Phys 5 + Awakened Brutality 5 + Awakened Fortify 5.",
                    "21/20 Ground Slam (o Earthshaking) corrupted + Pulverise 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Unbreakable raddoppiato (Jugg).",
                    "Helmet enchant: Ground Slam 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class VolcanicFissureJuggTemplate(GenericTemplate):
    """Volcanic Fissure Jugg/Berserker — slam fire con fissure travelling.

    Volcanic Fissure è una slam che crea una fissure di fuoco che viaggia
    e detona ripetutamente. Scala con slam tag + fire damage + AoE.
    Viable sia Jugg (tank) sia Berserker (damage). Avatar of Fire opzionale
    se vuoi pure fire conversion + Anger/Determination aura. Combustion
    per fire pen extra sui boss.
    """

    name: str = "volcanic_fissure_juggernaut"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder o Ground Slam come levelling.",
                    "Atto 3 reward: Volcanic Fissure sblocca; metti su 4L con Multistrike + Combustion + Fire Pen.",
                    "Leap Slam + Anger low-level.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Unflinching (Jugg) o Crave the Slaughter (Berserker).",
                    "Volcanic Fissure + Multistrike + Combustion + Fire Pen + Awakened Brutality (cheap) + Pulverise.",
                    "Anger + Determination + Herald of Ash.",
                ],
                tree_changes=[
                    "Avatar of Fire opzionale: 100% phys → fire (libera scaling fire-only).",
                    "Cluster phys/fire damage area sotto Marauder start.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Volcanic Fissure + Awakened Fire Pen + Awakened Brutality + Combustion + Awakened Melee Phys + Multistrike.",
                    "+2 to Strike/Slam 2H mace o axe craft (~10-30 div).",
                ],
                tree_changes=[
                    "Cluster jewel: Burning Bright + Fuel the Fight per fire damage + attack speed.",
                    "Stampede boots per movement consistente sui terrain difficili.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Fire Pen 5 + Awakened Brutality 5 + Awakened Melee Phys 5.",
                    "21/20 Volcanic Fissure corrupted + Combustion 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Unflinching (Jugg) o Aspect of Carnage (Berserker) doppio.",
                    "Watcher's Eye Anger 'Increased Fire Damage' (~30-60 div).",
                ],
            )
        return super().for_stage(stage, build)


# ---------------------------------------------------------------------------
# Caster spell DPS templates
# ---------------------------------------------------------------------------


class VortexOccultistTemplate(GenericTemplate):
    """Vortex / Cold DoT Occultist — comfy mapper signature build.

    Cold DoT applied via Cold Snap + Vortex with Bonechill / Hypothermia
    multipliers. Occultist's Profane Bloom + Frigid Wake give chill +
    explode + freeze immunity. Levels with Cold Snap + Frostblink before
    Vortex unlocks.
    """

    name: str = "vortex_occultist"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Freezing Pulse + Frostblink dalla quest 'The Caged Brute'.",
                    "Atto 3: Cold Snap diventa la skill principale del levelling.",
                    "Vortex sblocca a level 28 (atto 4); switch a Vortex + Bonechill.",
                    "Aura: Hatred (level ~24).",
                ],
                rationale_override=(
                    "Cold DoT è la più scriptbile in atto. Freezing Pulse → Cold Snap "
                    "→ Vortex porta da level 1 a Kitava senza switching dolorosi."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Profane Bloom (explode + chill).",
                    "Cold Snap come main DPS, Vortex per chill on-cast.",
                    "Aggiungi Bonechill + Hypothermia + Efficacy.",
                ],
                tree_changes=[
                    "Lifesprig come wand levelling (cheap, +1 cold gems implicit).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L con Vortex + Bonechill + Hypothermia + Efficacy + Controlled Destruction + Empower.",
                    "+2/+3 cold spell wand (~5-15 div) come main weapon.",
                    "Atlas: Maven Awakening + Eldritch Altars priority.",
                ],
                tree_changes=[
                    "Body Cospri's Will (auto-curse on hit) o Inpulsa's per pack clear.",
                    "Watcher's Eye Hatred 'Adds Cold Damage' (~20-50 div).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Burning Damage non si applica al cold; usa Awakened Hextouch + Awakened Cold Penetration.",
                    "21/20 Vortex corrupted + 21/20 Cold Snap.",
                ],
                tree_changes=[
                    "Cluster jewel cold DoT multi (Sadist + Wicked Pall).",
                    "Forbidden Flame + Flesh per Profane Bloom doppio.",
                ],
            )
        return super().for_stage(stage, build)


class SparkInquisitorTemplate(GenericTemplate):
    """Spark Inquisitor — bouncing lightning projectiles, big screen clear.

    Spark scales with cast speed + projectile count + lightning damage.
    Inquisitor's Inevitable Judgment ignores enemy lightning res entirely.
    Levels with Storm Brand or Arc before Spark becomes viable around lvl 10.
    """

    name: str = "spark_inquisitor"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Storm Brand (quest 'Mercy Mission') per il levelling iniziale.",
                    "Atto 1 boss reward: Spark + Faster Casting + Onslaught.",
                    "Wand+shield setup con Lifesprig.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Inevitable Judgment (ignore lightning res).",
                    "Spark + Lightning Penetration + Pierce + Faster Casting.",
                    "Wrath aura, Herald of Thunder.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Spark + Lightning Pen + Slower Projectiles + Spell Echo + Inspiration + Awakened Added Lightning (cheap).",
                    "+1 Spell Skill / +1 Lightning Spell sceptre o staff.",
                ],
                tree_changes=[
                    "Cluster jewel: Storm Drinker / Wandslinger.",
                    "Watcher's Eye Wrath 'Lightning Penetration' (~30-60 div).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Lightning Penetration **5** + Awakened Spell Echo **5**.",
                    "Slower Projectiles 21/20 (~5 div) — boss DPS x2.",
                ],
                tree_changes=[
                    "Replica Conqueror's Efficiency (mana cost reduction) jewel.",
                    "+1 power charge / +2 power charge body craft per crit cap.",
                ],
            )
        return super().for_stage(stage, build)


class PenanceBrandInquisitorTemplate(GenericTemplate):
    """Penance Brand Inquisitor — brand caster lightning/phys.

    Penance Brand attacca un brand al nemico che accumula stack di phys
    damage e poi esplode rilasciando energy pulse lightning. Inquisitor
    Inevitable Judgment ignora lightning res; Pious Path / Augury of
    Penitence per damage multi consacrated. Build by Cold Iron Point /
    +1/+2 spell skill weapon, Awakened Brand Recall + Awakened Lightning
    Pen endgame.
    """

    name: str = "penance_brand_inquisitor"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Storm Brand (quest 'Mercy Mission') per il levelling iniziale.",
                    "Atto 4 reward: Penance Brand sblocca; setup 4L con Brand Recall + Combustion + Faster Casting.",
                    "Wand+shield setup con Lifesprig.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Inevitable Judgment (ignore lightning res).",
                    "Penance Brand + Brand Recall + Awakened Lightning Pen (cheap) + Concentrated Effect + Awakened Spell Echo + Empower.",
                    "Wrath aura + Herald of Thunder + Skitterbots low-level.",
                ],
                tree_changes=[
                    "Pious Path (Inq) per area damage consacrato.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Penance Brand + Awakened Brand Recall + Awakened Lightning Pen + Concentrated Effect + Awakened Spell Echo + Empower 3.",
                    "+1 Spell Skill / +1 Lightning Spell sceptre o staff (~10-30 div).",
                ],
                tree_changes=[
                    "Cluster jewel: Brand Loyalty + Storm Drinker + Wandslinger.",
                    "Watcher's Eye Wrath 'Lightning Penetration' (~30-60 div).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brand Recall 5 + Awakened Lightning Pen 5 + Awakened Spell Echo 5.",
                    "Concentrated Effect 21/20 corrupted + Empower 4.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Inevitable Judgment doppio.",
                    "+2 spell skill staff custom craft (~50-100 div).",
                    "Helmet enchant: Penance Brand 25% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class CracklingLanceInquisitorTemplate(GenericTemplate):
    """Crackling Lance Inquisitor — lightning beam multistage hit.

    Crackling Lance lancia un raggio lightning che colpisce a stadi
    multipli (ogni stadio aumenta il danno). Inquisitor Inevitable
    Judgment + Augury of Penitence per consacrated ground damage multi.
    Scala con cast speed + spell crit + lightning pen. Replica Conqueror's
    Efficiency per cost reduction; +1 power charge body.
    """

    name: str = "crackling_lance_inquisitor"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Storm Brand come levelling pre-Crackling Lance.",
                    "Atto 4 reward: Crackling Lance sblocca; setup 4L con Faster Casting + Added Lightning + Spell Echo.",
                    "Wand+shield Lifesprig per +1 spell skill.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Inevitable Judgment (ignore lightning res).",
                    "Crackling Lance + Awakened Spell Echo (cheap) + Lightning Penetration + Inspiration + Slower Projectiles + Awakened Added Lightning (cheap).",
                    "Wrath + Herald of Thunder + Skitterbots.",
                ],
                tree_changes=[
                    "Augury of Penitence per damage consacrated.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Crackling Lance + Awakened Spell Echo + Awakened Lightning Pen + Inspiration + Slower Projectiles + Awakened Added Lightning.",
                    "+1 Spell Skill / +1 Lightning Spell staff o sceptre+focus (~10-30 div).",
                ],
                tree_changes=[
                    "Replica Conqueror's Efficiency jewel (mana cost reduction).",
                    "+1 power charge / +2 power charge body craft per crit cap.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Spell Echo 5 + Awakened Lightning Pen 5 + Awakened Added Lightning 5.",
                    "Slower Projectiles 21/20 corrupted (boss DPS x2).",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Augury of Penitence doppio.",
                    "+2 spell skill staff custom craft + +1 power charge.",
                    "Helmet enchant: Crackling Lance 25% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class ArcHierophantTemplate(GenericTemplate):
    """Arc Hierophant — chain lightning spell con Conviction of Power.

    Arc è il chain lightning iconico Templar. Hierophant Conviction of
    Power dà permanent power+endurance charges; Sign of the Sin Eater /
    Sanctuary of Thought per mana scaling. Viable con Mind Over Matter
    keystone + Arcane Cloak guard skill. Build di mana stacking endgame
    via Battlemage's Cry o The Agnostic keystone.
    """

    name: str = "arc_hierophant"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Arc dalla quest 'Breaking Some Eggs' — main skill day-1 Templar.",
                    "Setup 4L: Arc + Faster Casting + Added Lightning + Onslaught.",
                    "Wand+shield Lifesprig, Wrath aura.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Conviction of Power (permanent power + endurance charges).",
                    "Arc + Awakened Spell Echo (cheap) + Awakened Lightning Pen (cheap) + Awakened Chain (cheap) + Inspiration + Empower 3.",
                    "Wrath + Discipline + Herald of Thunder + Arcane Cloak.",
                ],
                tree_changes=[
                    "Mind Over Matter keystone + mana clusters.",
                    "Sanctuary of Thought ascendancy per mana → spell damage.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Arc + Awakened Spell Echo + Awakened Lightning Pen + Awakened Chain + Inspiration + Empower.",
                    "+1 Spell Skill / +1 Lightning Spell staff endgame (~30-50 div).",
                    "Battlemage's Cry warcry trigger su Mind Over Matter.",
                ],
                tree_changes=[
                    "Watcher's Eye Wrath 'Lightning Penetration' (~30-60 div).",
                    "Cluster jewel: Storm Drinker + Wandslinger + Pure Power.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Spell Echo 5 + Awakened Lightning Pen 5 + Awakened Chain 5.",
                    "21/20 Arc corrupted + Empower 4.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Conviction of Power doppio.",
                    "Cospri's Will / Inpulsa's Broken Heart body per shock + explode.",
                    "Helmet enchant: Arc 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class SmiteGuardianTemplate(GenericTemplate):
    """Smite Guardian — lightning melee strike + aura buff radius.

    Smite colpisce un nemico in melee e crea un'aura nearby che buffa il
    party (lightning damage + chance to shock). Guardian Radiant Crusade
    (minion damage aura propagata) + Time of Need (+life regen) + Unwavering
    Crusade (life on hit). Aegis Aurora shield + Sublime Vision per ulteriore
    aura scaling. Build party-friendly + viable solo a budget medio.
    """

    name: str = "smite_guardian"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder o Frost Blades come levelling pre-Smite.",
                    "Atto 4 reward: Smite sblocca; setup 4L con Multistrike + Added Lightning + Inspiration.",
                    "Wrath aura + Herald of Thunder low-level.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Radiant Crusade (Guardian aura propagation).",
                    "Smite + Multistrike + Awakened Added Lightning (cheap) + Trinity + Inspiration + Awakened Elemental Damage with Attacks (cheap).",
                    "Wrath + Determination + Herald of Thunder + Skitterbots.",
                ],
                tree_changes=[
                    "Aura cluster sotto Templar start: Charisma + aura effect.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Smite + Awakened Multistrike + Awakened Added Lightning + Trinity + Awakened Elemental Damage with Attacks + Inspiration.",
                    "Aegis Aurora shield (~1-3 div): es-on-block massive sustain.",
                    "+1 Lightning Spell sceptre o +1/+2 socketed Foil.",
                ],
                tree_changes=[
                    "Sublime Vision unique amulet (~5-15 div): aura scaling triplo.",
                    "Time of Need ascendancy per +life regen tank.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Multistrike 5 + Awakened Added Lightning 5 + Awakened Elemental Damage with Attacks 5.",
                    "21/20 Smite corrupted + Inspiration 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Unwavering Crusade doppio (Guardian).",
                    "Watcher's Eye Wrath 'Lightning Pen' + Determination 'phys reduction'.",
                    "Helmet enchant: Smite 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class AurabotGuardianTemplate(GenericTemplate):
    """Aurabot Guardian — support build aura stacking party.

    L'Aurabot non è un build DPS: è un personaggio support per group play
    con 8-12 auras attive contemporaneamente. Guardian Unwavering Crusade
    + Radiant Crusade + Time of Need per buff aura propagati. Items chiave:
    Sublime Vision (single aura tripled), Aegis Aurora, Crown of the Tyrant
    (helmet aura effect), Skin of the Lords con Pain Attunement / Eldritch
    Battery.
    """

    name: str = "aurabot_guardian"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Smite o un attack qualunque come throwaway DPS.",
                    "Da subito: Wrath / Anger / Hatred / Determination — 3-4 auras low-level.",
                    "Discipline + Clarity per ES + mana sustain.",
                ],
                rationale_override=(
                    "Aurabot non è un build solo. È un support per party che gioca "
                    "in gruppo. In campaign si livella con uno qualsiasi attack/spell, "
                    "le auras sono il vero contenuto del build."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Radiant Crusade (aura propagation a alleati).",
                    "Aggiungi Vitality + Skitterbots + Pride + Malevolence (mana costs gestiti).",
                    "Generosity Support su tutte le auras non-self (massimizza buff agli alleati).",
                ],
                tree_changes=[
                    "Aura cluster massivo sotto Templar: Charisma + Sovereignty + aura effect notable.",
                    "Mind Over Matter keystone se vai life-stacking.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body Skin of the Lords con keystone utile (Pain Attunement / Eldritch Battery).",
                    "Aegis Aurora shield (~1-3 div): ES-on-block sustain.",
                    "Sublime Vision (~5-15 div): single aura scelta tripla effect.",
                ],
                tree_changes=[
                    "Crown of the Tyrant helmet (~10-20 div): aura effect + 35% increased to all auras.",
                    "Time of Need ascendancy per +life regen propagato party.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Generosity Support su tutte le auras → +30% effect agli alleati.",
                    "Tutti gli aura gem 21/20 corrupted (~3-5 div ognuno).",
                    "Empower 4-5 sui slot aura per +level.",
                ],
                tree_changes=[
                    "Unwavering Crusade ascendancy: aura buff durano 100% più sugli alleati.",
                    "Forbidden Flame + Flesh per Unwavering Crusade o Time of Need doppio.",
                    "Cluster jewel: Sovereignty + Pure Power + Veteran Defender (aura effect + reservation).",
                ],
                rationale_override=(
                    "Endgame Aurabot: 12 auras attive simultanee, Crown of the Tyrant + "
                    "Sublime Vision + Awakened Generosity ovunque. I numeri di buff agli "
                    "alleati raddoppiano rispetto al mid-mapping."
                ),
            )
        return super().for_stage(stage, build)


class BoneSpearNecroTemplate(GenericTemplate):
    """Bone Spear / Soulrend hit caster Necromancer.

    Skill scales with chaos+phys conversion. Necromancer Mistress of Sacrifice
    + Commander of Darkness + Mindless Aggression for stat sticks aura buff.
    """

    name: str = "bone_spear_necromancer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Bone Offering + Skeletons setup base.",
                    "Atto 3: Bone Spear sblocca; metti su 4L con Spell Echo + Pierce.",
                    "Aura: Discipline + Clarity.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Mistress of Sacrifice (Bone Offering buff propagato).",
                    "Bone Spear + Pierce + Spell Echo + Added Chaos + Void Manipulation.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L con Bone Spear + Awakened Spell Echo + Pierce + Added Chaos + Void Manipulation + Empower.",
                    "+1 spell skill staff/sceptre o The Whispering Ice.",
                ],
                tree_changes=[
                    "Cluster jewel chaos damage (Wicked Pall, Touch of Cruelty).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Void Manipulation 5 + Awakened Spell Echo 5.",
                    "Vaal corrupted Bone Spear 21/20 per single-target Maven.",
                ],
                tree_changes=[
                    "Doppio curse via Hexblast threshold jewel o ring corruzione.",
                ],
            )
        return super().for_stage(stage, build)


class HexblastMinesTemplate(GenericTemplate):
    """Hexblast Mines Saboteur (or Pathfinder) — chaos curse-detonator.

    Hexblast is a curse-removing nuker that scales hard with mine throw speed
    + Saboteur's Born in the Shadows / Pyromaniac. Pathfinder variant uses
    flask uptime for Master Surgeon.
    """

    name: str = "hexblast_mines"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Explosive Trap (quest 'Breaking Some Eggs') per levelling fino al lab.",
                    "NON Hexblast prima del lab Cruel: ti manca curse + Pyromaniac.",
                ],
                rationale_override=(
                    "Hexblast richiede Withering Step / Bane / Despair per stackare la "
                    "curse. Esplosivo Trap fa il levelling con zero setup."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Pyromaniac (mine throwing + life regen).",
                    "Switch a Hexblast Mine + High-Impact Mine + Trap & Mine Damage + Despair.",
                    "Withering Step come applicatore di Wither stack.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Hexblast Mine + High-Impact Mine + Awakened Trap & Mine Damage + Inspiration + Cluster Traps + Concentrated Effect.",
                    "Cospri's Malice / Bottled Faith per power charge / damage.",
                ],
                tree_changes=[
                    "Cluster mine throwing speed + chaos damage.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Cluster Traps + Awakened Cast On Critical Strike (per Withering Step trigger).",
                    "Vaal Hexblast 21/20 per pinnacle bossing.",
                ],
            )
        return super().for_stage(stage, build)


class PoisonBladeVortexAssassinTemplate(GenericTemplate):
    """Poison Blade Vortex Assassin — chaos blade orbit + poison stacking.

    BV crea fino a 10 blade orbit attorno al personaggio che colpiscono
    in AoE. Assassin Mistwalker + Noxious Strike + Toxic Delivery scalano
    poison + crit + cull strike. Cospri's Will body (double curse on hit
    Despair + Wither). Cold Iron Point dagger (~1 chaos, +30% spell phys).
    Build dei boss-killer chaos signature.
    """

    name: str = "poison_blade_vortex_assassin"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow come levelling pre-BV.",
                    "Atto 3: Blade Vortex sblocca; setup 4L con Unleash + Lesser Poison + Spell Echo.",
                    "Whirling Blades + Quicksilver come movement.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Mistwalker (smoke cloud + crit) + Noxious Strike (cull on poison).",
                    "BV + Awakened Spell Echo (cheap) + Awakened Vile Toxins (cheap) + Awakened Void Manipulation (cheap) + Empower 3 + Withering Step.",
                    "Despair self-cast o Bane low-level per curse.",
                ],
                tree_changes=[
                    "Toxic Delivery ascendancy: chaos damage on poison + culling.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body Cospri's Will (~5-15 div): cursed by Despair + Wither on hit.",
                    "Body 6L: BV + Awakened Spell Echo + Awakened Vile Toxins + Awakened Void Manipulation + Empower + Withering Step.",
                    "Cold Iron Point dagger (~1 chaos) + offhand stat stick.",
                ],
                tree_changes=[
                    "Cluster jewel chaos DoT multi: Wicked Pall + Touch of Cruelty + Sadist.",
                    "Watcher's Eye Malevolence 'DoT damage' (~50+ div).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Vile Toxins 5 + Awakened Void Manipulation 5 + Awakened Spell Echo 5.",
                    "21/20 Blade Vortex corrupted + Empower 4.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Toxic Delivery doppio.",
                    "Mageblood (~250-300 div): Dying Sun + Bottled Faith permanenti.",
                    "Helmet enchant: Blade Vortex 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class CobraLashAssassinTemplate(GenericTemplate):
    """Cobra Lash Assassin — chaos projectile chain + poison.

    Cobra Lash spara un proietto chaos che chain tra i nemici, applicando
    poison massive. Assassin Toxic Delivery + Noxious Strike + Mistwalker.
    Mark of the Elder ring + +1 dex amulet variant; oppure dual-wield daggers
    standard. Endgame con Awakened Chain + Awakened Vile Toxins, Vaal Cobra
    Lash per single-target burst.
    """

    name: str = "cobra_lash_assassin"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow come levelling pre-Cobra Lash.",
                    "Atto 3: Cobra Lash sblocca; setup 4L con Pierce + Lesser Poison + Faster Attacks.",
                    "Whirling Blades come movement, Despair self-cast.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Mistwalker + Noxious Strike (Assassin).",
                    "Cobra Lash + Awakened Chain (cheap) + Awakened Vile Toxins (cheap) + Awakened Void Manipulation (cheap) + Inspiration + Withering Step.",
                    "Bane / Despair / Wither setup curse.",
                ],
                tree_changes=[
                    "Toxic Delivery ascendancy + chaos damage area.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Cobra Lash + Awakened Chain + Awakened Vile Toxins + Awakened Void Manipulation + Inspiration + Withering Step.",
                    "Dual-wield daggers Cold Iron Point (cheap) + +1/+2 socketed dagger craft o Mark of the Elder + +1 dex amulet variant.",
                ],
                tree_changes=[
                    "Cluster jewel: Wicked Pall + Touch of Cruelty + Sadist.",
                    "Cospri's Will body alternativo per double curse on hit.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Chain 5 + Awakened Vile Toxins 5 + Awakened Void Manipulation 5.",
                    "21/20 Cobra Lash corrupted + Vaal Cobra Lash 4L laterale per single-target.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Toxic Delivery doppio.",
                    "Watcher's Eye Malevolence 'DoT damage' (~50+ div).",
                    "Helmet enchant: Cobra Lash +2 projectiles.",
                ],
            )
        return super().for_stage(stage, build)


class PyroclastMinesSaboteurTemplate(GenericTemplate):
    """Pyroclast Mines Saboteur — fire AoE mine bossing burst.

    Pyroclast Mine throws a mine that erupts in fire AoE explosions.
    Saboteur Pyromaniac (life regen + mine throw speed) + Bombardier
    (extra mines per throw) + Demolitions Specialist. Build classico
    bossing single-target — un detonate combo distrugge ogni boss in
    un colpo. Cospri's Malice / +X Fire Spell mines weapon.
    """

    name: str = "pyroclast_mines_saboteur"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Explosive Trap (quest 'Breaking Some Eggs') per levelling iniziale.",
                    "Atto 3+: Pyroclast Mine sblocca; metti su 4L con High-Impact Mine + Trap & Mine Damage + Combustion.",
                    "Smoke Mine come movement skill.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Pyromaniac (mine throw speed + life regen).",
                    "Pyroclast Mine + High-Impact Mine + Awakened Trap & Mine Damage (cheap) + Combustion + Concentrated Effect + Awakened Fire Pen (cheap).",
                    "Skitterbots aura per shock + chill bonus.",
                ],
                tree_changes=[
                    "Demolitions Specialist + Bombardier ascendancy.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Pyroclast Mine + High-Impact Mine + Awakened Trap & Mine Damage + Combustion + Concentrated Effect + Awakened Fire Pen.",
                    "Cospri's Malice (~3-5 div) o +X to Fire Spell mines weapon.",
                ],
                tree_changes=[
                    "Cluster mine throwing speed + fire damage (Sleepless Sentries + Calamitous).",
                    "Bottled Faith flask (~30-50 div): consacrated ground = damage multi.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Trap & Mine Damage 5 + Awakened Fire Pen 5 + Awakened Burning Damage 5.",
                    "21/20 Pyroclast Mine corrupted + High-Impact Mine 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Bombardier doppio (Saboteur).",
                    "Watcher's Eye Anger 'Increased Fire Damage' (~30-60 div).",
                    "Helmet enchant: Pyroclast Mine 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class ColdDotTricksterTemplate(GenericTemplate):
    """Cold Snap DoT Trickster — pure cold DoT alternative al Vortex Occultist.

    Cold Snap (specialmente Cold Snap of Power transfigured) è il main DoT
    skill. Trickster Patient Reaper (kill on hit + life regen) + Soul
    Drinker + One Step Ahead per movement immunity. Differente dal Vortex
    Occultist: niente explode, ma tank tramite ES/EB Trickster + speed.
    Dybella's Heel + The Devouring Diadem variant per dual-DoT.
    """

    name: str = "cold_dot_trickster"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Freezing Pulse + Frostblink dalla quest 'The Caged Brute'.",
                    "Atto 3: Cold Snap diventa la skill principale; setup 4L con Bonechill + Hypothermia + Efficacy.",
                    "Aura: Hatred (level ~24) + Herald of Ice.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Patient Reaper (Trickster: kill = life/ES regen).",
                    "Cold Snap + Bonechill + Hypothermia + Awakened Cold Penetration (cheap) + Efficacy + Empower 3.",
                    "Vortex 4L laterale come chill on-cast.",
                ],
                tree_changes=[
                    "Soul Drinker ascendancy: ES sustain on kill.",
                    "Cluster cold DoT multi sotto Witch start (anche se siamo Shadow, accessibile via routing).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Cold Snap + Awakened Cold Pen + Awakened Hextouch + Bonechill + Empower + Hypothermia.",
                    "Considera Cold Snap of Power transfigured per Hierophant-style scaling (controllo).",
                    "+2/+3 cold spell wand + offhand stat stick.",
                ],
                tree_changes=[
                    "Watcher's Eye Hatred 'Adds Cold Damage' (~20-50 div).",
                    "Cluster cold DoT (Sadist + Wicked Pall) + ES cluster.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Cold Pen 5 + Awakened Hextouch 5 + Awakened Empower 4.",
                    "21/20 Cold Snap corrupted + Vortex 21/20 secondary.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Patient Reaper o Escape Artist doppio (Trickster).",
                    "+1 spell skill staff o The Whispering Ice unique evolved (~30-50 div).",
                    "Helmet enchant: Cold Snap 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class BladeBlastTricksterTemplate(GenericTemplate):
    """Blade Blast Trickster — detona Blade Fall blades for AoE phys/spell.

    Blade Blast detona blade lasciate da Blade Fall, con damage scaling
    aggressivo. Trickster Patient Reaper + Soul Drinker per ES sustain;
    One Step Ahead + Escape Artist per movement immunity. Build hit
    aggressivo con detonate massiccio. Dual-wield daggers + +1/+2 socketed
    spell skill weapon endgame.
    """

    name: str = "blade_blast_trickster"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Freezing Pulse o Frost Blades come levelling pre-Blade Blast.",
                    "Atto 3: Blade Fall + Blade Blast sblocca; setup 4L con Inspiration + Spell Echo + Concentrated Effect.",
                    "Whirling Blades come movement, Hatred aura.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Patient Reaper (Trickster) + Soul Drinker per ES sustain.",
                    "Blade Blast + Awakened Spell Echo (cheap) + Inspiration + Concentrated Effect + Hypothermia + Awakened Added Cold (cheap).",
                    "Blade Fall trigger setup (4L laterale).",
                ],
                tree_changes=[
                    "Cluster spell damage + ES sotto Shadow start.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Blade Blast + Awakened Spell Echo + Inspiration + Concentrated Effect + Hypothermia + Awakened Added Cold.",
                    "Dual-wield +1/+2 socketed spell skill daggers o sceptre+focus craft (~10-30 div).",
                ],
                tree_changes=[
                    "Cluster jewel: Pressure Points + Calamitous + Quick Getaway.",
                    "One Step Ahead + Escape Artist ascendancy per phys → ES.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Spell Echo 5 + Awakened Added Cold 5 + Awakened Cold Pen 5.",
                    "21/20 Blade Blast corrupted + Concentrated Effect 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Patient Reaper doppio (Trickster).",
                    "Watcher's Eye Hatred 'Adds Cold Damage' o Discipline 'ES recharge'.",
                ],
            )
        return super().for_stage(stage, build)


class SoulrendTricksterTemplate(GenericTemplate):
    """Soulrend Trickster — chaos+cold projectile spell DoT.

    Soulrend è uno spell projectile chaos+cold che applica DoT on hit.
    Trickster Patient Reaper + Soul Drinker per ES + life sustain;
    Escape Artist per phys → ES. Niente Bone Spear: questo template è
    distinto dal BoneSpearNecro (che ha Necro ascendancy). Soulrend si
    fa anche su Trickster con scaling chaos+cold ibrido.
    """

    name: str = "soulrend_trickster"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Freezing Pulse come levelling pre-Soulrend.",
                    "Atto 3: Soulrend sblocca; setup 4L con Pierce + Faster Casting + Awakened Added Chaos.",
                    "Whirling Blades come movement, Malevolence + Discipline.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Patient Reaper (Trickster) + Soul Drinker per ES regen.",
                    "Soulrend + Pierce + Awakened Added Chaos (cheap) + Awakened Void Manipulation (cheap) + Empower 3 + Faster Projectiles.",
                    "Wither + Despair self-cast o Bane setup curse.",
                ],
                tree_changes=[
                    "Cluster chaos DoT multi (Wicked Pall + Touch of Cruelty).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Soulrend + Awakened Added Chaos + Awakened Void Manipulation + Pierce + Empower + Faster Projectiles.",
                    "+1 chaos / +1 spell skill staff o The Whispering Ice unique.",
                ],
                tree_changes=[
                    "Watcher's Eye Malevolence 'DoT damage' (~50+ div).",
                    "Cluster ES + Sadist (DoT multi).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Added Chaos 5 + Awakened Void Manipulation 5 + Awakened Empower 4.",
                    "21/20 Soulrend corrupted + Faster Projectiles 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Escape Artist o Patient Reaper doppio.",
                    "+2 spell skill staff custom craft (~50-100 div).",
                    "Helmet enchant: Soulrend +1 projectile o increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class DetonateDeadNecroTemplate(GenericTemplate):
    """Detonate Dead Necromancer — corpse-based AoE fire.

    Volatile Dead / Detonate Dead scale with corpse life. Mistress of
    Sacrifice + Commander of Darkness baseline.
    """

    name: str = "detonate_dead_necromancer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Skeletons + Raise Zombie come levelling.",
                    "Atto 3: Detonate Dead sblocca; metti su Desecrate per spawnare corpses.",
                    "Volatile Dead da Library di Siosa.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Mistress of Sacrifice.",
                    "Volatile Dead + Spell Cascade + Unleash + Elemental Focus.",
                    "Desecrate come supplemento corpse.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Volatile Dead + Spell Cascade + Unleash + Awakened Elemental Focus + Combustion + Empower.",
                    "The Devouring Diadem helmet (auto-cast Desecrate trigger).",
                ],
                tree_changes=[
                    "Cluster jewel fire damage + Sadist (DoT multi).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Spell Cascade 5 (~30 div) — area boss molto più ampia.",
                    "Awakened Empower 4 + Awakened Elemental Focus 5.",
                ],
            )
        return super().for_stage(stage, build)


class BaneOccultistTemplate(GenericTemplate):
    """Bane / ED+Contagion Occultist — chaos DoT spreader.

    Stacks 3 curses + chaos DoT explosion. Contagion spreads, ED ticks.
    Profane Bloom + Withering Presence make Bane Occultist the king of clear.
    """

    name: str = "bane_occultist"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Contagion + Essence Drain dalle quest reward.",
                    "Atto 3: aggiungi Bane appena lo trovi.",
                    "Aura: Malevolence (level ~24).",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Profane Bloom (explode on chaos kill).",
                    "Bane + 2-3 curses (Despair, Temporal Chains, Punishment).",
                    "ED + Contagion 4L per single target / pack clearing.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Bane + Despair + Temporal Chains + Enfeeble + Awakened Hextouch + Empower.",
                    "+1 chaos / +1 spell skill weapon.",
                ],
                tree_changes=[
                    "Cluster jewel: Wicked Pall + Touch of Cruelty + Sadist.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Hextouch 5 + Awakened Empower 4.",
                    "Doomsday + Whispers of Doom per +1 curse limit.",
                ],
            )
        return super().for_stage(stage, build)


# ---------------------------------------------------------------------------
# Attack-based templates
# ---------------------------------------------------------------------------


class CycloneSlayerTemplate(GenericTemplate):
    """Cyclone Slayer / Berserker / Champion — channel spin damage.

    Cyclone scales with attack speed + impale + AoE. Slayer Headsman gives
    free over-leech, Berserker War Bringer triples warcry effects.
    """

    name: str = "cyclone_slayer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder o Ground Slam per levelling pre-Cyclone.",
                    "Atto 3: Cyclone sblocca; metti su 4L con Fortify + Faster Attacks.",
                    "Leap Slam come movement.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Headsman (Slayer) o Crave the Slaughter (Berserker).",
                    "Cyclone + Pulverise + Brutality + Impale + Faster Attacks.",
                    "Pride aura, War Banner.",
                ],
                tree_changes=[
                    "Brightbeak + Lycosidae shield per Resolute Technique baseline.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Cyclone + Awakened Melee Phys + Awakened Brutality + Pulverise + Impale + Fortify.",
                    "+1/+2 socketed body o axe/sword end-game.",
                ],
                tree_changes=[
                    "Cluster jewel impale (Fuel the Fight) + crit.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Melee Phys 5 + Awakened Brutality 5.",
                    "Cyclone 21/20 corrupted + Awakened Fortify Support 5.",
                ],
                tree_changes=[
                    "Atziri's Disfavour per +2 socketed gems built-in.",
                    "Watcher's Eye Pride 'Increased Phys Damage' (~50+ div).",
                ],
            )
        return super().for_stage(stage, build)


class ReaveSlayerTemplate(GenericTemplate):
    """Reave Slayer — sword strike con phantom blade stacks AoE.

    Reave colpisce localmente e accumula stack che aumentano l'AoE.
    Slayer Headsman dà over-leech + cannot be stunned while leeching;
    Bane of Legends raddoppia il damage on first hit dei rare/unique.
    Paradoxica (1H sword +100% phys as ele) o Foil base + +1/+2 socketed
    sono le weapon endgame. Vaal Reave per single-target burst.
    """

    name: str = "reave_slayer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Frost Blades o Caustic Arrow come levelling pre-Reave.",
                    "Atto 3: Reave sblocca; metti su 4L con Multistrike + Faster Attacks + Added Lightning.",
                    "Whirling Blades come movement, Onslaught Support per attack speed.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Headsman (Slayer over-leech + cull strike).",
                    "Reave + Multistrike + Inspiration + Added Cold/Lightning + Trinity + Elemental Damage with Attacks.",
                    "Wrath + Herald of Ice + Precision low-level.",
                ],
                tree_changes=[
                    "Sword cluster + Resolute Technique area opzionale (zero accuracy needed).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Reave + Awakened Multistrike + Awakened Added Lightning + Trinity + Awakened Elemental Damage with Attacks + Inspiration.",
                    "Paradoxica 1H sword (~10-30 div) o +1/+2 socketed Foil craft.",
                    "Vaal Reave 4L laterale per single-target boss burst.",
                ],
                tree_changes=[
                    "Cluster jewel: Pressure Points + Quick Getaway + Calamitous.",
                    "Saviour shield (mirror minion + crit boost) o Lycosidae per accuracy.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Multistrike 5 + Awakened Added Lightning 5 + Awakened Elemental Damage with Attacks 5.",
                    "21/20 Reave corrupted + Inspiration 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Bane of Legends doppio.",
                    "Watcher's Eye Wrath 'Lightning Pen' + Precision 'crit chance'.",
                    "Helmet enchant: Reave +40 stage maximum.",
                ],
            )
        return super().for_stage(stage, build)


class LacerateGladiatorTemplate(GenericTemplate):
    """Lacerate Gladiator — sword 2H/DW slash + bleed stacking.

    Lacerate spara due onde phys (bleed sui critici). Gladiator Painforged
    + Gratuitous Violence trasforma i corpses in explode chain. Crimson
    Dance keystone permette bleed stack (variante DW). Endgame con +1/+2
    socketed weapon e Awakened Brutality + Awakened Vicious Projectiles
    (sì, anche se è melee, il proj è splitting wave).
    """

    name: str = "lacerate_gladiator"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder o Frost Blades come levelling pre-Lacerate.",
                    "Atto 3 reward: Lacerate sblocca; setup 4L con Melee Phys + Brutality + Multistrike.",
                    "Leap Slam + Blood Rage low-level per attack speed.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Painforged + Gratuitous Violence (corpse explode chain).",
                    "Lacerate + Multistrike + Brutality + Awakened Melee Phys (cheap) + Pulverise + Fortify.",
                    "Pride + Blood and Sand stance on Sand per AoE.",
                ],
                tree_changes=[
                    "Crimson Dance keystone (DW variant) per bleed stacking.",
                    "Cluster phys melee + bleed area sotto Duelist start.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Lacerate + Awakened Brutality + Awakened Melee Phys + Multistrike + Pulverise + Awakened Fortify.",
                    "DW +1/+2 socketed gems sword/axe craft o Paradoxica + Beltimber Blade.",
                ],
                tree_changes=[
                    "Cluster jewel: Master the Fundamentals + Quick Getaway + Feed the Fury.",
                    "The Surrender shield (Gladiator) o rare 6L body con +1 socketed.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brutality 5 + Awakened Melee Phys 5 + Awakened Fortify 5.",
                    "21/20 Lacerate corrupted + Pulverise 21/20.",
                    "Considera Lacerate of Haemorrhage (transfigured) per pure bleed scaling.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Painforged doppio.",
                    "Watcher's Eye Pride 'Increased Phys Damage' (~50+ div).",
                    "Helmet enchant: Lacerate 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class SplittingSteelGladiatorTemplate(GenericTemplate):
    """Splitting Steel Gladiator — phys ranged-melee con secondary projectiles.

    Splitting Steel lancia un proietto phys che si splitta in 2-3 secondari
    on hit, applicando Impale. Gladiator Painforged + Gratuitous Violence
    aggiunge corpse explode; Champion Worthy Foe + Inspirational variant
    è altrettanto popolare. Sword/axe weapon, Steel Skills cluster jewel.
    """

    name: str = "splitting_steel_gladiator"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder o Caustic Arrow come levelling.",
                    "Atto 3 reward: Splitting Steel sblocca; setup 4L con Multistrike + Impale + Brutality.",
                    "Leap Slam + Blood and Sand stance.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Painforged + Gratuitous Violence (Gladiator) o Worthy Foe + Inspirational (Champion).",
                    "Splitting Steel + Multistrike + Impale + Brutality + Awakened Melee Phys (cheap) + Trinity (NO — solo phys).",
                    "Pride + War Banner per impale + phys taken multi.",
                ],
                tree_changes=[
                    "Steel Skills threshold/notable area per +secondary projectiles.",
                    "Cluster phys melee + impale area sotto Duelist.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Splitting Steel + Awakened Brutality + Awakened Melee Phys + Multistrike + Impale + Awakened Vicious Projectiles.",
                    "Paradoxica o +1/+2 socketed sword/axe craft (~20-50 div).",
                ],
                tree_changes=[
                    "Cluster jewel: Fuel the Fight + Master the Fundamentals + Quick Getaway.",
                    "The Surrender shield + Lycosidae per accuracy + block.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brutality 5 + Awakened Melee Phys 5 + Awakened Vicious Projectiles 5.",
                    "21/20 Splitting Steel corrupted + Impale 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Painforged doppio (Gladiator) o Inspirational (Champion).",
                    "Watcher's Eye Pride 'Increased Phys Damage' + Precision 'crit chance'.",
                    "Helmet enchant: Splitting Steel +1 secondary projectile.",
                ],
            )
        return super().for_stage(stage, build)


class SunderChampionTemplate(GenericTemplate):
    """Sunder Champion — slam phys signature Champion build.

    Sunder è il classico league-starter Marauder/Champion: 2H mace,
    Resolute Technique, Brutality. Champion Worthy Foe + Inspirational
    per single-target multi e party damage. Marohi Erqi → +2 to Slam
    Skills 2H mace endgame. Pride aura + War Banner. The Surrender
    shield se vai 1H + scudo (variante Glad).
    """

    name: str = "sunder_champion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Sunder dalla quest 'Mercy Mission' — skill day-1.",
                    "Setup 4L: Sunder + Ruthless + Melee Phys + Pulverise.",
                    "Leap Slam come movement, Ancestral Protector totem per attack speed.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Worthy Foe (Champion single-target multi) + Inspirational.",
                    "Sunder + Ruthless + Awakened Brutality (cheap) + Pulverise + Melee Phys + Fortify.",
                    "Pride + War Banner + Dread Banner per phys taken multi.",
                ],
                tree_changes=[
                    "Resolute Technique area centrale (zero accuracy needed).",
                    "Marauder area: Tireless + Heart of the Warrior + Diamond Skin.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Sunder + Awakened Melee Phys + Awakened Brutality + Ruthless + Pulverise + Awakened Fortify.",
                    "Marohi Erqi 2H mace (~1-3 div) come transition; +2 to Slam Skills 2H mace endgame.",
                ],
                tree_changes=[
                    "Cluster jewel: Quick Getaway + Fuel the Fight + Feed the Fury.",
                    "The Surrender shield (Champion 1H+shield variant) o rare 6L body.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Melee Phys 5 + Awakened Brutality 5 + Awakened Fortify 5.",
                    "21/20 Sunder corrupted + Pulverise 21/20.",
                    "Considera Sunder of Earthbreaking transfigured per AoE permanente.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Worthy Foe (Champion) o First to Strike (Glad) doppio.",
                    "Watcher's Eye Pride 'Increased Phys Damage' (~50+ div).",
                    "Helmet enchant: Sunder 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class StaticStrikeGladiatorTemplate(GenericTemplate):
    """Static Strike Gladiator — lightning melee strike + chained beams.

    Static Strike colpisce localmente e crea beam tra il personaggio e i
    nemici per un breve tempo (chains gratis). Lightning damage scaling +
    crit. Gladiator Versatile Combatant (block spell + attack) + Painforged
    se Sand stance. Champion Inspirational variant è altrettanto valida.
    Saviour shield + Paradoxica/Foil per crit weapon.
    """

    name: str = "static_strike_gladiator"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Frost Blades come levelling pre-Static Strike.",
                    "Atto 3 reward: Static Strike sblocca; setup 4L con Multistrike + Added Lightning + Inspiration.",
                    "Whirling Blades come movement, Wrath aura.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Versatile Combatant (Glad block) o Inspirational (Champion).",
                    "Static Strike + Multistrike + Inspiration + Added Lightning + Trinity + Elemental Damage with Attacks.",
                    "Wrath + Herald of Thunder + Precision low-level.",
                ],
                tree_changes=[
                    "Sword cluster + Resolute Technique area opzionale.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Static Strike + Awakened Multistrike + Awakened Added Lightning + Trinity + Awakened Elemental Damage with Attacks + Inspiration.",
                    "Paradoxica 1H sword (~10-30 div) o +1/+2 socketed Foil craft.",
                ],
                tree_changes=[
                    "Saviour shield (mirror minion + crit boost) per Glad — la stessa scelta del Reave.",
                    "Cluster jewel: Pressure Points + Calamitous + Quick Getaway.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Multistrike 5 + Awakened Added Lightning 5 + Awakened Elemental Damage with Attacks 5.",
                    "21/20 Static Strike corrupted + Inspiration 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Versatile Combatant (Glad) o Worthy Foe (Champion) doppio.",
                    "Watcher's Eye Wrath 'Lightning Pen' + Precision 'crit chance'.",
                ],
            )
        return super().for_stage(stage, build)


class SpectralThrowChampionTemplate(GenericTemplate):
    """Spectral Throw Champion — boomerang projectile sword/axe.

    Spectral Throw lancia una weapon copy phys che torna indietro,
    colpendo doppio sui mob in linea. Champion Worthy Foe + Inspirational
    per boss + party. Paradoxica o +1/+2 socketed Foil/sword craft;
    Saviour shield. Vaal Spectral Throw + Awakened GMP per bossing burst.
    """

    name: str = "spectral_throw_champion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Spectral Throw dalla quest 'Mercy Mission' — skill day-1 Duelist.",
                    "Setup 4L: Spectral Throw + Pierce + Faster Attacks + Brutality.",
                    "Whirling Blades come movement, Onslaught Support.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Worthy Foe (Champion +damage taken multi) + Inspirational.",
                    "Spectral Throw + Awakened Vicious Projectiles (cheap) + Brutality + Awakened GMP (cheap) + Inspiration + Slower Projectiles (boss).",
                    "Pride + War Banner per phys taken multi.",
                ],
                tree_changes=[
                    "Resolute Technique area centrale.",
                    "Cluster phys + projectile area sotto Duelist.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Spectral Throw + Awakened Brutality + Awakened Vicious Projectiles + Awakened GMP + Inspiration + Slower Projectiles.",
                    "Paradoxica o +1/+2 socketed sword/axe craft (~20-50 div).",
                    "Vaal Spectral Throw 4L laterale per bossing burst.",
                ],
                tree_changes=[
                    "Cluster jewel: Master the Fundamentals + Quick Getaway + Calamitous.",
                    "Saviour shield + Lycosidae per accuracy + crit boost.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brutality 5 + Awakened Vicious Projectiles 5 + Awakened GMP 5.",
                    "21/20 Spectral Throw corrupted + Slower Projectiles 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Worthy Foe doppio (Champion).",
                    "Watcher's Eye Pride 'Increased Phys Damage' (~50+ div).",
                    "Helmet enchant: Spectral Throw +20% damage.",
                ],
            )
        return super().for_stage(stage, build)


class LightningStrikeRaiderTemplate(GenericTemplate):
    """Lightning Strike Raider/Champion — ranged melee with projectiles.

    LS strikes locally + shoots projectiles. Scales with attack speed +
    weapon damage + projectiles. Raider gives Avatar of the Slaughter (frenzy
    + onslaught), Champion gives Inspirational + Worthy Foe.
    """

    name: str = "lightning_strike_raider"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Frost Blades dalla quest, fino a level 12.",
                    "Atto 4 (Library): Lightning Strike + Multistrike + Added Lightning + Elemental Damage with Attacks.",
                    "Onslaught Support per movespeed.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Avatar of the Slaughter (Raider) o Inspirational (Champion).",
                    "Lightning Strike + Multistrike + Added Lightning + Inspiration + Trinity / Elemental Damage with Attacks.",
                    "Wrath + Herald of Thunder + Precision low-level.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Lightning Strike + Multistrike + Inspiration + Awakened Added Lightning + Trinity + Awakened Elemental Damage with Attacks.",
                    "Paradoxica / +1 attack staff o Foil con +1/+2 socketed.",
                ],
                tree_changes=[
                    "Saviour shield (mirror minion + crit boost) o Lycosidae.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Added Lightning 5 + Awakened Elemental Damage with Attacks 5.",
                    "21/20 Lightning Strike + 21/20 Multistrike corrupted.",
                ],
                tree_changes=[
                    "Watcher's Eye Wrath 'Lightning Pen' + Precision 'crit chance'.",
                ],
            )
        return super().for_stage(stage, build)


class TornadoShotDeadeyeTemplate(GenericTemplate):
    """Tornado Shot Deadeye — bow projectile screen clear.

    TS shoots a tornado that releases secondary projectiles. Scales with
    projectile count + bow damage. Deadeye Endless Munitions = +2 projectiles.
    """

    name: str = "tornado_shot_deadeye"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow (cheapest bow levelling).",
                    "Atto 4 reward: Tornado Shot + Mirage Archer + Pierce + Onslaught.",
                    "Quill Rain o Storm Cloud bow per attack speed.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Endless Munitions (+2 projectiles).",
                    "Tornado Shot + Mirage Archer + Greater Multiple Projectiles + Pierce + Inspiration.",
                    "Anger + Wrath + Herald of Ice.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Tornado Shot + Awakened GMP + Awakened Elemental Damage with Attacks + Inspiration + Mirage Archer + Slower Projectiles.",
                    "Lioneye's Glare unique bow (level 70 entry, ~3-10 div).",
                ],
                tree_changes=[
                    "Hyrri's Bite o Yoke of Suffering per ele attacks.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened GMP 5 (~50 div) — single-projectile boss conversion.",
                    "Awakened Elemental Damage with Attacks 5 + Awakened Added Cold/Fire/Lightning.",
                ],
                tree_changes=[
                    "+3 bow craft (~50-100 div) o Voltaxic Rift unique.",
                ],
            )
        return super().for_stage(stage, build)


class FrostBladesRaiderTemplate(GenericTemplate):
    """Frost Blades Raider/Trickster — cold melee with projectiles.

    Strike that fires 3 cold projectiles per hit. Raider scales speed +
    frenzy charges. Trickster Patient Reaper / One Step Ahead = movement.
    """

    name: str = "frost_blades_raider"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Frost Blades dalla quest 'Mercy Mission' — main skill day 1.",
                    "Multistrike + Ancestral Call + Hatred low-level.",
                    "Whirling Blades come movement.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Way of the Poacher (frenzy) o Patient Reaper (Trickster).",
                    "Frost Blades + Multistrike + Trinity + Inspiration + Added Cold + Elemental Damage with Attacks.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Frost Blades + Awakened Multistrike + Awakened Added Cold + Trinity + Awakened Elemental Damage with Attacks + Inspiration.",
                    "Paradoxica o +1 ele attack claw/sword.",
                ],
                tree_changes=[
                    "Watcher's Eye Hatred 'Cold Damage as Extra'.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Added Cold 5 (~30 div) + Awakened Multistrike 5.",
                    "21/20 Frost Blades corrupted + Trinity 21.",
                ],
            )
        return super().for_stage(stage, build)


class IceShotDeadeyeTemplate(GenericTemplate):
    """Ice Shot Deadeye — cold projectile bow con conversion phys→cold.

    Ice Shot converte 60% phys → cold + spawna a cone secondary AoE on hit.
    Deadeye Endless Munitions (+2 projectiles) + Far Shot (damage scaling
    con distanza). Classico league-starter Ranger: setup veloce, freeze +
    chill ovunque, scaling con +1/+2 socketed bow craft o Lioneye's Glare
    come budget intermedio.
    """

    name: str = "ice_shot_deadeye"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow come levelling pre-Ice Shot.",
                    "Atto 4 reward: Ice Shot + Mirage Archer + Pierce + Onslaught.",
                    "Quill Rain o Storm Cloud bow come transition.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Endless Munitions (+2 projectiles).",
                    "Ice Shot + Mirage Archer + Greater Multiple Projectiles + Pierce + Inspiration.",
                    "Hatred + Herald of Ice + Precision low-level.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Ice Shot + Awakened GMP + Awakened Elemental Damage with Attacks + Mirage Archer + Inspiration + Hypothermia.",
                    "Lioneye's Glare unique bow (~3-10 div) come transition; +1/+2 socketed bow craft endgame.",
                ],
                tree_changes=[
                    "Hyrri's Bite o Yoke of Suffering per ele attacks.",
                    "Watcher's Eye Hatred 'Cold Damage as Extra' (~30-60 div).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened GMP 5 + Awakened Elemental Damage with Attacks 5 + Awakened Cold Penetration 5.",
                    "21/20 Ice Shot corrupted + Slower Projectiles 21/20 per single-target.",
                ],
                tree_changes=[
                    "+3 bow craft (~50-100 div) o Voltaxic Rift unique.",
                    "Forbidden Flame + Flesh per Far Shot doppio.",
                    "Helmet enchant: Ice Shot 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class PoisonousConcoctionPathfinderTemplate(GenericTemplate):
    """Poisonous Concoction Pathfinder — flask-thrown chaos poison.

    PConc lancia il flask life equipato come AoE chaos hit + applica poison
    massiccio. Scala con flask charge generation + chaos DoT multi + poison.
    Pathfinder Master Surgeon (flask sustain) + Nature's Reprisal (+poison
    multi). Build 'budget' classico: zero weapon richiesta, focus su flask
    + chaos DoT scaling.
    """

    name: str = "poisonous_concoction_pathfinder"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow come levelling pre-PConc.",
                    "Atto 3: Poisonous Concoction sblocca; setup 4L con Greater Multiple Projectiles + Lesser Poison + Void Manipulation.",
                    "Mirage Archer non si applica (PConc non è bow); Quicksilver flask + Movement skill.",
                ],
                rationale_override=(
                    "PConc non usa bow né weapon: lancia il flask life equipato come "
                    "AoE chaos. Liberi gli slot weapon per stat sticks o shield + 1H "
                    "spell skill. Levelling Caustic Arrow finché PConc non sblocca."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Master Surgeon (flask charge sustain).",
                    "Poisonous Concoction + Greater Multiple Projectiles + Awakened Vile Toxins (cheap) + Awakened Void Manipulation (cheap) + Empower + Withering Step trigger.",
                    "Despair self-cast o Bane low-level per curse multi.",
                ],
                tree_changes=[
                    "Nature's Reprisal ascendancy (poison damage multi + duration).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: PConc + Awakened GMP + Awakened Vile Toxins + Awakened Void Manipulation + Empower + Damage on Full Life.",
                    "Stat stick weapons: Cold Iron Point dagger (~1 chaos) o +1 chaos / +1 spell skill weapons.",
                ],
                tree_changes=[
                    "Cluster jewel chaos DoT multi (Wicked Pall + Touch of Cruelty).",
                    "Dying Sun + Cinderswallow per +2 projectiles + life.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Vile Toxins 5 + Awakened Void Manipulation 5 + Awakened GMP 5.",
                    "21/20 Poisonous Concoction corrupted + Empower 4.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh per Master Surgeon o Nature's Reprisal doppio.",
                    "Mageblood (~250-300 div): tutti i flask permanenti = PConc damage flat raddoppiato.",
                    "Helmet enchant: Poisonous Concoction +1 projectile o increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class ToxicRainPathfinderTemplate(GenericTemplate):
    """Toxic Rain Pathfinder — bow chaos DoT cloud.

    TR pods deal chaos DoT + ground tick. Scales with bow damage + chaos
    over time multi + projectile count. Pathfinder gives 100% flask uptime
    (Master Surgeon) and Mistress of Sacrifice-tier staying alive.
    """

    name: str = "toxic_rain_pathfinder"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow per levelling.",
                    "Atto 3: Toxic Rain sblocca; switch immediato.",
                    "Mirage Archer + Despair + Vile Toxins low-level.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Master Surgeon (flask uptime) — pathfinder essenziale.",
                    "Toxic Rain + Mirage Archer + Vile Toxins + Damage on Full Life + Empower + Swift Affliction.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: TR + Mirage Archer + Awakened Vile Toxins + Damage on Full Life + Awakened Swift Affliction + Empower.",
                    "+1 socketed gem helmet con Toxic Rain enchant.",
                ],
                tree_changes=[
                    "Quill Rain → Death's Harp → +2 bow craft.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Vile Toxins 5 + Awakened Empower 4.",
                    "21/20 Toxic Rain corrupted (~10 div).",
                ],
                tree_changes=[
                    "Bow craft +1 socketed gems / chaos DoT multi.",
                ],
            )
        return super().for_stage(stage, build)


# ---------------------------------------------------------------------------
# Minion templates
# ---------------------------------------------------------------------------


class SpectreNecroTemplate(GenericTemplate):
    """Spectre Necromancer — premium minion build.

    Scales with minion damage / minion life / +X to minion level. Uses
    specific spectres (Carnage Chieftain, Slave Driver, Soul Eater Tukohama).
    """

    name: str = "spectre_necromancer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Skeletons + Raise Zombie come levelling.",
                    "Atto 3 (Solaris Temple Lvl 2): Raise Spectre sblocca.",
                    "Spectre iniziali: Solar Guards (atto 8) o Frost Sentinels.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Mistress of Sacrifice (Bone Offering propagato).",
                    "Spectre + Minion Damage + Elemental Damage + Spell Echo + Pierce.",
                    "Aura: Anger / Wrath / Hatred (a seconda dello spectre).",
                ],
                tree_changes=[
                    "Wand levelling: Lifesprig per +1 spell skill (sale anche minion gem).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Spectre + Minion Damage + Elemental Damage + Awakened Greater Multiple Projectiles + Awakened Empower 3 + Pierce.",
                    "+3 minion gem helm (Bone Helmet base, ~3-10 div).",
                ],
                tree_changes=[
                    "Convocation per pull spectre-pack on cooldown.",
                    "Animate Guardian con Garb of the Ephemeral / Kingmaker.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Empower 4 + Awakened Spell Echo 5.",
                    "Awakened Greater Multiple Projectiles 5 (~80 div).",
                ],
                tree_changes=[
                    "+3 minion gem helm con Hatred efficacy o Curse on Hit.",
                    "The Squire (4-link auto-effect + Animate Guardian gear room).",
                ],
            )
        return super().for_stage(stage, build)


class SkeletonMagesTemplate(GenericTemplate):
    """Skeleton Mages Necromancer — Dark Ascetic notable + Mages of Caer Doan."""

    name: str = "skeleton_mages_necromancer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Summon Raging Spirit + Raise Zombie.",
                    "Atto 3: Summon Skeletons (regular fino al threshold jewel).",
                    "Aura: Discipline + Clarity.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Mages of Caer Doan threshold jewel: Skeleton → Skeleton Mage cold/fire/lightning.",
                    "Primo lab: Mistress of Sacrifice.",
                    "Skeletons + Spell Echo + Minion Damage + Concentrated Effect.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Skeletons + Awakened Spell Echo + Minion Damage + Concentrated Effect + Predator + Empower.",
                    "Skin of the Lords con keystone utile (Crimson Dance / Pain Attunement).",
                ],
                tree_changes=[
                    "Dead Reckoning jewel per spawn skeleton senza casting.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Spell Echo 5 + Awakened Empower 4.",
                    "Predator 21/20 corrupted.",
                ],
            )
        return super().for_stage(stage, build)


class AnimateWeaponNecroTemplate(GenericTemplate):
    """Animate Weapon Necromancer — Earendel's Embrace + scrappy weapons."""

    name: str = "animate_weapon_necromancer"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Skeletons + Zombie + Raise Spectre baseline.",
                    "Atto 3+: Animate Weapon sblocca; usa weapon vendor scraps.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Mindless Aggression + Mistress of Sacrifice.",
                    "Animate Weapon + Minion Damage + Multistrike + Melee Phys + Brutality + Impale.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: AW + Awakened Multistrike + Awakened Melee Phys + Brutality + Impale + Empower.",
                    "Earendel's Embrace per +Spell skill animation.",
                ],
                tree_changes=[
                    "Wings of Entropy / Aukuna's Will ring per evocation gratis.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Melee Phys 5 + Awakened Multistrike 5.",
                    "Animate Weapon 21/20 corrupted.",
                ],
            )
        return super().for_stage(stage, build)


# ---------------------------------------------------------------------------
# Totem templates
# ---------------------------------------------------------------------------


class HolyFlameTotemHieroTemplate(GenericTemplate):
    """Holy Flame Totem Hierophant — non-RF totem caster.

    Pure totem build: 4 totems, Astral Projector ring or proximity, Soul
    Mantle for +1 totem. Hierophant Conviction of Power + Pursuit of Faith.
    """

    name: str = "holy_flame_totem_hierophant"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Holy Flame Totem dalla quest 'Breaking Some Eggs'.",
                    "Multiple Totems + Combustion + Faster Casting low-level.",
                    "Aura: Anger + Determination.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Pursuit of Faith (+1 totem).",
                    "HFT + Multiple Totems + Awakened Burning Damage (cheap) + Combustion + Empower.",
                    "Aspect of the Spider per slow + chill.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body Soul Mantle (~5-10 div): +1 totem total.",
                    "Body 6L: HFT + Multiple Totems + Awakened Burning Damage + Combustion + Empower + Awakened Elemental Focus.",
                    "Astramentis amulet o +1 spell skill amulet.",
                ],
                tree_changes=[
                    "Astral Projector ring: totem casting target ranged.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Burning Damage 5 + Awakened Empower 4.",
                    "21/20 HFT corrupted (~3 div).",
                ],
                tree_changes=[
                    "+1 socketed body craft per +9 levels totali sui 6 link.",
                ],
            )
        return super().for_stage(stage, build)


class ShrapnelBallistaDeadeyeTemplate(GenericTemplate):
    """Shrapnel Ballista / Lancing Steel Ballista Deadeye — bow totem."""

    name: str = "ballista_totem_deadeye"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow + Quill Rain bow.",
                    "Atto 3 reward: Shrapnel Ballista + Multiple Totems + Onslaught.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Far Shot + Endless Munitions.",
                    "Shrapnel Ballista + Awakened GMP (cheap) + Inspiration + Elemental Damage with Attacks + Multiple Totems + Trinity.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: SB + Awakened GMP + Trinity + Inspiration + Multiple Totems + Awakened Elemental Damage with Attacks.",
                    "Lioneye's Fall jewel (Resolute Technique area to Iron Grip).",
                ],
                tree_changes=[
                    "Dying Sun + Cinderswallow per +2 projectiles + life.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Elemental Damage with Attacks 5 + Awakened GMP 5.",
                    "+3 bow craft o Voltaxic Rift / Maraketh Bow custom.",
                ],
            )
        return super().for_stage(stage, build)


# ---------------------------------------------------------------------------
# Scion / Hybrid templates
# ---------------------------------------------------------------------------


class CocCospriCycloneScionTemplate(GenericTemplate):
    """Cast on Crit Cospri Cyclone Scion — channel cyclone trigger spells.

    Cyclone canalizzato come crit trigger source per spell socketed in
    Cospri's Malice (sword) e/o Mjolner. Spell tipiche: Frostbolt + Ice
    Nova combo (Frost), Ball Lightning + Lightning Conduit (lightning),
    Spark for clear. Scion Ascendant Champion + Assassin (crit + impale)
    o Inquisitor + Assassin (consecrated). Awakened CoC + +1/+2 socketed
    sword endgame.
    """

    name: str = "coc_cospri_cyclone_scion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Frost Blades come levelling pre-Cyclone.",
                    "Atto 3: Cyclone sblocca; setup 4L con Faster Attacks + Inspiration + Fortify.",
                    "Niente CoC ancora: prima del lab + Cospri's Malice non vale la pena.",
                ],
                rationale_override=(
                    "CoC Cospri richiede crit cap + cooldown reduction + Cospri's Malice. "
                    "In atto 1-3 niente di tutto questo: si livella Cyclone vanilla e si "
                    "switcha a CoC dopo il primo lab + drop o purchase di Cospri's Malice."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Champion + Assassin (Scion Ascendant) per crit + impale + over-leech.",
                    "Cyclone + Awakened Cast on Critical Strike (cheap) + Frostbolt + Ice Nova + Inspiration + Fortify.",
                    "Hatred + Herald of Ice + Precision aura.",
                ],
                tree_changes=[
                    "Cluster crit chance + spell crit + sword damage.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Cyclone + Awakened CoC + Frostbolt + Ice Nova + Inspiration + Fortify.",
                    "Cospri's Malice 1H sword (~3-10 div): trigger gratis Frostbolt + Ice Nova socketed.",
                    "Mjolner (~10-30 div) come offhand alternativo per double trigger lightning.",
                ],
                tree_changes=[
                    "Watcher's Eye Hatred 'Cold Pen' + Precision 'crit chance'.",
                    "Cospri's Malice ha '~10% chance to trigger socketed cold spell on melee crit' + 'Trigger socketed cold spell on melee crit'.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Cast on Critical Strike 5 (~80-120 div).",
                    "Awakened Cold Pen 5 + Awakened Spell Echo NO (CoC non ammette Spell Echo).",
                    "21/20 Cyclone corrupted + Vaal Ice Nova for boss burst.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh: combo Champion + Assassin doppio-ascendancy.",
                    "+1 to socketed gems Cospri's Malice corrupted.",
                    "Helmet enchant: Ice Nova damage o Cyclone crit chance.",
                ],
            )
        return super().for_stage(stage, build)


class PowerSiphonScionTemplate(GenericTemplate):
    """Power Siphon Scion — wand attack skill con Power Charges + crit.

    Power Siphon spara projectile con power charge generation on hit
    (e crit con Power Charge stack). Scion Ascendant Deadeye + Assassin
    (crit + projectile) o Pathfinder per flask uptime. Dual-wield wand
    +2/+3 ele wand. Awakened GMP + Awakened Added Lightning + Inspiration.
    Vaal Power Siphon per single-target burst.
    """

    name: str = "power_siphon_scion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Caustic Arrow / Storm Brand come levelling pre-Power Siphon.",
                    "Atto 3 reward: Power Siphon sblocca; setup 4L con Faster Attacks + Added Lightning + Onslaught.",
                    "Wand + shield Lifesprig come transition.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Deadeye + Assassin (Scion Ascendant) per +projectile + crit.",
                    "Power Siphon + Awakened Greater Multiple Projectiles (cheap) + Awakened Added Lightning (cheap) + Inspiration + Trinity + Elemental Damage with Attacks.",
                    "Wrath + Herald of Thunder + Precision.",
                ],
                tree_changes=[
                    "Wand cluster: Wandslinger + Storm Drinker + Pure Power.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Power Siphon + Awakened GMP + Awakened Added Lightning + Trinity + Inspiration + Awakened Elemental Damage with Attacks.",
                    "Dual-wield +2 lightning wand craft (~20-40 div) o Doryani's Catalyst variant.",
                    "Vaal Power Siphon 4L laterale per boss burst.",
                ],
                tree_changes=[
                    "Watcher's Eye Wrath 'Lightning Pen' + Precision 'crit chance'.",
                    "Cluster jewel: Replica Conqueror's Efficiency + Pure Power.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened GMP 5 + Awakened Added Lightning 5 + Awakened Elemental Damage with Attacks 5.",
                    "21/20 Power Siphon corrupted + Inspiration 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh: combo Deadeye + Assassin doppio-ascendancy.",
                    "Mageblood (~250-300 div): Diamond + Sulphur + Quartz permanenti.",
                    "Helmet enchant: Power Siphon +1 chain o increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class StormBrandScionTemplate(GenericTemplate):
    """Storm Brand Scion — chain lightning brand caster.

    Storm Brand è un brand caster che chain tra nemici emettendo beam
    lightning. Scion Ascendant Inquisitor + Elementalist (ele pen +
    shaper of storms) o Inquisitor + Hierophant (charge generation).
    Awakened Brand Recall + Awakened Lightning Pen + +1 power charge body.
    Build versatile mappable + bossable.
    """

    name: str = "storm_brand_scion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Storm Brand dalla quest 'Mercy Mission' — main skill day-1.",
                    "Setup 4L: Storm Brand + Brand Recall + Added Lightning + Faster Casting.",
                    "Wand + shield Lifesprig, Wrath low-level.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Inquisitor + Elementalist (Scion Ascendant): Inevitable Judgment + Shaper of Storms.",
                    "Storm Brand + Brand Recall + Awakened Lightning Pen (cheap) + Concentrated Effect + Awakened Spell Echo (cheap) + Empower 3.",
                    "Wrath + Herald of Thunder + Skitterbots.",
                ],
                tree_changes=[
                    "Brand area: Brand Loyalty cluster + Storm Drinker.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Storm Brand + Awakened Brand Recall + Awakened Lightning Pen + Concentrated Effect + Awakened Spell Echo + Empower.",
                    "+1 Spell Skill / +1 Lightning Spell sceptre o staff (~10-30 div).",
                ],
                tree_changes=[
                    "Cluster jewel: Brand Loyalty + Storm Drinker + Wandslinger.",
                    "Watcher's Eye Wrath 'Lightning Penetration' (~30-60 div).",
                    "+1 power charge / +2 power charge body craft per crit cap.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brand Recall 5 + Awakened Lightning Pen 5 + Awakened Spell Echo 5.",
                    "Concentrated Effect 21/20 corrupted + Empower 4.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh: combo Inquisitor + Elementalist doppio.",
                    "+2 spell skill staff custom craft (~50-100 div).",
                    "Helmet enchant: Storm Brand 25% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class MjolnerDischargeScionTemplate(GenericTemplate):
    """Mjolner Discharge Scion — channel + Mjolner trigger Discharge.

    Mjolner unique mace triggera spell socketed on melee hit. Build classico:
    Cyclone (o Static Strike) + Mjolner trigger Discharge + Ball Lightning.
    Genera Power+Endurance+Frenzy charges via CWDT setup. Scion Ascendant
    Inquisitor + Champion. Endgame con +1/+2 socketed Mjolner corrupted
    (~150-300 div).
    """

    name: str = "mjolner_discharge_scion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Storm Brand o Frost Blades come levelling pre-Mjolner.",
                    "Atto 3: Cyclone sblocca; vanilla Cyclone con Faster Attacks + Inspiration.",
                    "Niente Mjolner ancora: serve level 60+ per equiparlo (str+int requirements alti).",
                ],
                rationale_override=(
                    "Mjolner ha requirements stat alti (200 str + 200 int) e cooldown "
                    "reduction needed. In atto si livella vanilla Cyclone fino a level 60+, "
                    "poi switch a Mjolner trigger setup."
                ),
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Inquisitor + Champion (Scion Ascendant) per ele pen + impale.",
                    "Cyclone + Awakened Cast When Damage Taken (low level CWDT setup) + Discharge + Ball Lightning + Inspiration.",
                    "Wrath + Herald of Thunder + Discipline aura.",
                ],
                tree_changes=[
                    "Cluster: Charge generation (Voices of the Vaal / Doryani's Lesson).",
                    "Resolute Technique area se vuoi semplicità accuracy.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Mjolner mace (~30-60 div): trigger socketed lightning spell on melee hit.",
                    "Body 6L: Cyclone + CWDT + Inspiration + Fortify + supporto charge gen.",
                    "Mjolner socketato 6S: Discharge + Ball Lightning + Awakened Lightning Pen + Concentrated Effect + Power Charge On Critical + Endurance Charge On Melee Stun.",
                ],
                tree_changes=[
                    "Watcher's Eye Wrath 'Lightning Pen' + Discipline 'ES recharge'.",
                    "+1 power charge body craft per crit cap.",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Lightning Pen 5 + Awakened Added Lightning 5.",
                    "21/20 Discharge corrupted + 21/20 Ball Lightning.",
                    "Mjolner +1/+2 socketed gems corrupted (~150-300 div).",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh: combo Inquisitor + Champion doppio-ascendancy.",
                    "Romira's Banquet ring (gain power charge on hit no crit) + The Saviour shield.",
                    "Helmet enchant: Discharge 40% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


class SpectralHelixScionTemplate(GenericTemplate):
    """Spectral Helix Scion — sword/axe boomerang projectile con curva.

    Spectral Helix lancia una weapon copy che curva e torna con AoE
    massive. Distinto da Spectral Throw: traiettoria sinusoidale + multi-
    hit. Scion Ascendant Slayer + Deadeye (over-leech + projectile)
    o Slayer + Champion (impale). Paradoxica + Saviour shield endgame.
    """

    name: str = "spectral_helix_scion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Spectral Throw o Frost Blades come levelling pre-Spectral Helix.",
                    "Atto 4 reward: Spectral Helix sblocca; setup 4L con Brutality + Faster Attacks + Pierce.",
                    "Whirling Blades come movement, Pride aura.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Slayer + Deadeye (Scion Ascendant): over-leech + Endless Munitions.",
                    "Spectral Helix + Awakened Brutality (cheap) + Awakened Vicious Projectiles (cheap) + Pierce + Inspiration + Slower Projectiles (boss).",
                    "Pride + War Banner + Dread Banner.",
                ],
                tree_changes=[
                    "Cluster jewel sword + projectile damage.",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Spectral Helix + Awakened Brutality + Awakened Vicious Projectiles + Pierce + Inspiration + Slower Projectiles.",
                    "Paradoxica 1H sword (~10-30 div) o +1/+2 socketed Foil craft.",
                    "Saviour shield (~30-50 div) per mirror minion + crit boost.",
                ],
                tree_changes=[
                    "Cluster: Master the Fundamentals + Quick Getaway + Calamitous.",
                    "Lycosidae shield budget alternativo (accuracy gratis).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Brutality 5 + Awakened Vicious Projectiles 5 + Awakened Fortify 5.",
                    "21/20 Spectral Helix corrupted + Slower Projectiles 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh: combo Slayer + Deadeye doppio-ascendancy.",
                    "Watcher's Eye Pride 'Increased Phys Damage' (~50+ div).",
                    "Helmet enchant: Spectral Helix +20% damage.",
                ],
            )
        return super().for_stage(stage, build)


class ForbiddenRiteScionTemplate(GenericTemplate):
    """Forbidden Rite Scion — chaos+ele self-cast spell con life cost.

    Forbidden Rite spara projectile ele+chaos che passano oltre i target,
    consuma life flat per cast. Build classico Low Life via Pain Attunement
    (50% increased spell damage). Scion Ascendant Pathfinder + Trickster
    (flask uptime + life regen) o Pathfinder + Inquisitor. Endgame con
    Awakened Spell Echo + Awakened Added Chaos + +2 spell skill staff.
    """

    name: str = "forbidden_rite_scion"

    def for_stage(self, stage: StageSpec, build: Build) -> StagePlanContent:
        if stage.key == "early_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Atto 1: Storm Brand come levelling pre-Forbidden Rite.",
                    "Atto 4 reward: Forbidden Rite sblocca; setup 4L con Pierce + Faster Casting + Awakened Added Chaos (cheap).",
                    "Wand+shield Lifesprig per +1 spell skill.",
                ],
            )
        if stage.key == "mid_campaign":
            return StagePlanContent(
                gem_changes=[
                    "Primo lab: Pathfinder + Trickster (Scion Ascendant): flask uptime + ES sustain.",
                    "Forbidden Rite + Pierce + Awakened Spell Echo (cheap) + Awakened Added Chaos (cheap) + Awakened Void Manipulation (cheap) + Inspiration.",
                    "Malevolence + Discipline + Skitterbots.",
                ],
                tree_changes=[
                    "Pain Attunement keystone (Low Life setup, 50% increased spell damage).",
                ],
            )
        if stage.key == "early_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Body 6L: Forbidden Rite + Awakened Spell Echo + Awakened Added Chaos + Awakened Void Manipulation + Inspiration + Pierce.",
                    "+1 Spell Skill / +1 Chaos Spell staff (~10-30 div).",
                    "Shavronne's Wrappings body (Low Life setup) o Solaris Lorica.",
                ],
                tree_changes=[
                    "Cluster jewel: Wicked Pall + Touch of Cruelty + Sadist.",
                    "Watcher's Eye Discipline 'ES recharge' (Low Life sustain).",
                ],
            )
        if stage.key == "end_mapping":
            return StagePlanContent(
                gem_changes=[
                    "Awakened Spell Echo 5 + Awakened Added Chaos 5 + Awakened Void Manipulation 5.",
                    "21/20 Forbidden Rite corrupted + Inspiration 21/20.",
                ],
                tree_changes=[
                    "Forbidden Flame + Flesh: combo Pathfinder + Trickster doppio.",
                    "+2 spell skill staff custom craft (~50-100 div).",
                    "Helmet enchant: Forbidden Rite 25% increased damage.",
                ],
            )
        return super().for_stage(stage, build)


# ---------------------------------------------------------------------------
# Registry & dispatch
# ---------------------------------------------------------------------------


def _matches_skill(*needles: str) -> Callable[[Build], bool]:
    """Build a matcher that hits when any *needles* appears in main_skill.

    Case-insensitive substring match. Used for templates that map cleanly
    to a single skill name; templates that need to differentiate between
    ascendancies (e.g. Cyclone Slayer vs Cyclone Berserker) can ignore
    that distinction at this layer — the per-stage advice is mostly the
    same and the registry only keys on the skill.
    """

    folded = tuple(n.casefold() for n in needles)

    def matcher(build: Build) -> bool:
        skill = (build.main_skill or "").casefold()
        return any(needle in skill for needle in folded)

    return matcher


def _matches_rf(build: Build) -> bool:
    skill = (build.main_skill or "").casefold()
    return "righteous fire" in skill or skill == "rf"


# Aura gem names (low-cased) used to identify Aurabot builds.
# An Aurabot doesn't have a damage main_skill — it's identified by
# carrying 5+ aura supports. Reservation auras are listed here; Vaal
# variants share the base name (matched via casefold-substring below).
_AURA_GEMS: frozenset[str] = frozenset(
    {
        "anger",
        "wrath",
        "hatred",
        "determination",
        "grace",
        "vitality",
        "purity of fire",
        "purity of cold",
        "purity of lightning",
        "purity of elements",
        "discipline",
        "clarity",
        "haste",
        "malevolence",
        "pride",
        "zealotry",
        "skitterbots",
        "summon skitterbots",
        "envy",
    }
)


def _matches_coc_cospri(build: Build) -> bool:
    """Match Cast on Crit Cospri builds: any key_item is Cospri's Malice.

    CoC Cospri characters carry main_skill='Cyclone' (the channel skill)
    but the build identity is the unique sword. Skill-keyed dispatch alone
    would route them to CycloneSlayerTemplate; this item-keyed matcher
    intercepts them before that. Same pattern as :func:`_matches_aurabot`.
    """

    return any("cospri's malice" in (ki.item.name or "").casefold() for ki in build.key_items)


def _matches_mjolner(build: Build) -> bool:
    """Match Mjolner Discharge / CoMK builds: any key_item is Mjolner.

    Mjolner triggers socketed lightning spell on melee hit. Build identity
    is the unique mace; main_skill is usually 'Cyclone' or 'Static Strike'
    (the channel/strike that hits). Skill-keyed dispatch alone would route
    to CycloneSlayer/StaticStrikeGladiator.
    """

    return any("mjolner" in (ki.item.name or "").casefold() for ki in build.key_items)


def _matches_aurabot(build: Build) -> bool:
    """Match aurabot builds: 5+ aura gems carried as supports.

    Aurabots don't fit the skill-keyed dispatch — they identify by the
    sheer number of reservation auras stacked. Counts ``support_gems``
    entries whose case-folded form matches a known aura name (substring
    is enough so Vaal variants land too).
    """

    needle_set = _AURA_GEMS
    auras = sum(
        1 for g in build.support_gems if any(needle in g.casefold() for needle in needle_set)
    )
    return auras >= 5


# Each registry entry pairs a matcher with its template instance. Order
# matters: the first matching entry wins. Put more specific matchers
# first — e.g. RF (which contains "fire") is listed before fire-totem
# templates so a Holy Flame Totem RF Jugg still routes to RfPohx.
TEMPLATE_REGISTRY: list[tuple[Callable[[Build], bool], BuildTemplate]] = [
    # Most-specific first.
    (_matches_rf, RfPohxTemplate()),
    # Aurabot must come before any skill matcher: an aurabot might carry
    # a throwaway Smite/Spark/Arc as DPS, but the build identity is the
    # aura stack, not the skill.
    (_matches_aurabot, AurabotGuardianTemplate()),
    # Mjolner — item-keyed, before any cyclone/static-strike skill matcher.
    # Mjolner triggers socketed lightning spell on melee hit; the build
    # identity is the unique mace, not the channel skill.
    (_matches_mjolner, MjolnerDischargeScionTemplate()),
    # CoC Cospri — item-keyed matcher, must come before "cyclone" matcher
    # because CoC Cospri builds carry main_skill='Cyclone'.
    (_matches_coc_cospri, CocCospriCycloneScionTemplate()),
    # Slam / Marauder
    (_matches_skill("boneshatter"), BoneshatterTemplate()),
    (_matches_skill("earthshatter"), EarthshatterJuggTemplate()),
    (_matches_skill("tectonic slam"), TectonicSlamChieftainTemplate()),
    (_matches_skill("molten strike"), MoltenStrikeChieftainTemplate()),
    (_matches_skill("ground slam"), GroundSlamJuggTemplate()),
    (_matches_skill("volcanic fissure"), VolcanicFissureJuggTemplate()),
    # Casters — Blade Vortex must come BEFORE Vortex (substring collision).
    (_matches_skill("blade vortex"), PoisonBladeVortexAssassinTemplate()),
    (_matches_skill("blade blast"), BladeBlastTricksterTemplate()),
    # Cold Snap split off Vortex Occultist: Cold Snap → Trickster, Vortex → Occultist.
    (_matches_skill("cold snap"), ColdDotTricksterTemplate()),
    (_matches_skill("vortex"), VortexOccultistTemplate()),
    (_matches_skill("spark"), SparkInquisitorTemplate()),
    (_matches_skill("penance brand"), PenanceBrandInquisitorTemplate()),
    (_matches_skill("crackling lance"), CracklingLanceInquisitorTemplate()),
    # Storm Brand must come BEFORE Arc (no substring collision but keep
    # all brand templates grouped for readability).
    (_matches_skill("storm brand"), StormBrandScionTemplate()),
    (_matches_skill("arc"), ArcHierophantTemplate()),
    (_matches_skill("smite"), SmiteGuardianTemplate()),
    # Soulrend split off BoneSpearNecro: Soulrend → Trickster, Bone Spear → Necro.
    (_matches_skill("soulrend"), SoulrendTricksterTemplate()),
    (_matches_skill("bone spear"), BoneSpearNecroTemplate()),
    (_matches_skill("hexblast"), HexblastMinesTemplate()),
    (_matches_skill("cobra lash"), CobraLashAssassinTemplate()),
    (_matches_skill("pyroclast"), PyroclastMinesSaboteurTemplate()),
    (_matches_skill("detonate dead", "volatile dead"), DetonateDeadNecroTemplate()),
    (_matches_skill("bane", "essence drain", "contagion"), BaneOccultistTemplate()),
    # Attacks
    (_matches_skill("cyclone"), CycloneSlayerTemplate()),
    (_matches_skill("reave"), ReaveSlayerTemplate()),
    (_matches_skill("lacerate"), LacerateGladiatorTemplate()),
    (_matches_skill("splitting steel"), SplittingSteelGladiatorTemplate()),
    (_matches_skill("sunder"), SunderChampionTemplate()),
    (_matches_skill("static strike"), StaticStrikeGladiatorTemplate()),
    (_matches_skill("spectral throw"), SpectralThrowChampionTemplate()),
    (_matches_skill("spectral helix"), SpectralHelixScionTemplate()),
    (_matches_skill("lightning strike"), LightningStrikeRaiderTemplate()),
    (_matches_skill("tornado shot"), TornadoShotDeadeyeTemplate()),
    (_matches_skill("frost blades"), FrostBladesRaiderTemplate()),
    (_matches_skill("ice shot"), IceShotDeadeyeTemplate()),
    (_matches_skill("poisonous concoction"), PoisonousConcoctionPathfinderTemplate()),
    (_matches_skill("toxic rain"), ToxicRainPathfinderTemplate()),
    (_matches_skill("power siphon"), PowerSiphonScionTemplate()),
    (_matches_skill("forbidden rite"), ForbiddenRiteScionTemplate()),
    # Minions
    (_matches_skill("raise spectre", "spectre"), SpectreNecroTemplate()),
    (
        _matches_skill("summon skeletons", "skeleton"),
        SkeletonMagesTemplate(),
    ),
    (_matches_skill("animate weapon"), AnimateWeaponNecroTemplate()),
    # Totems (after RF so non-RF Holy Flame Totem matches here)
    (_matches_skill("holy flame totem"), HolyFlameTotemHieroTemplate()),
    (
        _matches_skill("shrapnel ballista", "lancing steel"),
        ShrapnelBallistaDeadeyeTemplate(),
    ),
]

GENERIC_TEMPLATE = GenericTemplate()


def pick_template(build: Build) -> BuildTemplate:
    """Pick the most specific template that matches *build*.

    Falls back to :class:`GenericTemplate` when nothing in the
    registry claims the build. The fallback is always safe to call —
    it produces sensible Italian copy from the build's main skill
    and support gem list.
    """

    for matcher, template in TEMPLATE_REGISTRY:
        if matcher(build):
            return template
    return GENERIC_TEMPLATE


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------


__all__ = [
    "EARLY_CAMPAIGN",
    "EARLY_MAPPING",
    "END_CAMPAIGN",
    "END_MAPPING",
    "GENERIC_TEMPLATE",
    "HIGH_INVESTMENT",
    "MID_CAMPAIGN",
    "TEMPLATE_REGISTRY",
    "AnimateWeaponNecroTemplate",
    "ArcHierophantTemplate",
    "AurabotGuardianTemplate",
    "BaneOccultistTemplate",
    "BladeBlastTricksterTemplate",
    "BoneSpearNecroTemplate",
    "BoneshatterTemplate",
    "BuildTemplate",
    "CobraLashAssassinTemplate",
    "CocCospriCycloneScionTemplate",
    "ColdDotTricksterTemplate",
    "CracklingLanceInquisitorTemplate",
    "CycloneSlayerTemplate",
    "DetonateDeadNecroTemplate",
    "EarthshatterJuggTemplate",
    "ForbiddenRiteScionTemplate",
    "FrostBladesRaiderTemplate",
    "GenericTemplate",
    "GroundSlamJuggTemplate",
    "HexblastMinesTemplate",
    "HolyFlameTotemHieroTemplate",
    "IceShotDeadeyeTemplate",
    "LacerateGladiatorTemplate",
    "LightningStrikeRaiderTemplate",
    "MjolnerDischargeScionTemplate",
    "MoltenStrikeChieftainTemplate",
    "PenanceBrandInquisitorTemplate",
    "PoisonBladeVortexAssassinTemplate",
    "PoisonousConcoctionPathfinderTemplate",
    "PowerSiphonScionTemplate",
    "PyroclastMinesSaboteurTemplate",
    "ReaveSlayerTemplate",
    "RfPohxTemplate",
    "ShrapnelBallistaDeadeyeTemplate",
    "SkeletonMagesTemplate",
    "SmiteGuardianTemplate",
    "SoulrendTricksterTemplate",
    "SparkInquisitorTemplate",
    "SpectralHelixScionTemplate",
    "SpectralThrowChampionTemplate",
    "SpectreNecroTemplate",
    "SplittingSteelGladiatorTemplate",
    "StagePlanContent",
    "StaticStrikeGladiatorTemplate",
    "StormBrandScionTemplate",
    "SunderChampionTemplate",
    "TectonicSlamChieftainTemplate",
    "TornadoShotDeadeyeTemplate",
    "ToxicRainPathfinderTemplate",
    "VolcanicFissureJuggTemplate",
    "VortexOccultistTemplate",
    "pick_template",
]
