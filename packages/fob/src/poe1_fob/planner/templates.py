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
# Registry & dispatch
# ---------------------------------------------------------------------------


def _matches_rf(build: Build) -> bool:
    skill = (build.main_skill or "").casefold()
    return "righteous fire" in skill or skill == "rf"


# Each registry entry pairs a matcher with its template instance. Order
# matters: the first matching entry wins. Put more specific matchers
# first.
TEMPLATE_REGISTRY: list[tuple[Callable[[Build], bool], BuildTemplate]] = [
    (_matches_rf, RfPohxTemplate()),
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
    "BuildTemplate",
    "GenericTemplate",
    "RfPohxTemplate",
    "StagePlanContent",
    "pick_template",
]
