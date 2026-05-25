"""Viability validation for generated :class:`BuildSkeleton`s (Step 43).

The Build Generator (Step 40-41) produces structurally complete PoB
imports, but a structurally valid build is not the same as a viable
one. A Witch with 1 200 life is "valid" but instantly dies to map
white-pack damage. ``validate_build`` runs a small battery of checks
and returns a :class:`ViabilityReport` the UI surfaces as
warnings / errors so the user knows what to fix.

The pipeline still produces the build — we never refuse to output one.
The report is purely additive feedback.

This step (43) only *checks* what the generator already emits. Step 44
will rewrite the tree-node selector to BFS-path real notables from the
class start, using the same report for post-path validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from .models import BuildSkeleton


_LIFE_FLOOR: dict[str, int] = {"starter": 3_000, "mid": 4_000, "endgame": 5_500}
_ES_FLOOR: dict[str, int] = {"starter": 4_000, "mid": 6_000, "endgame": 9_000}

_MOVEMENT_SKILLS: frozenset[str] = frozenset(
    {
        "Flame Dash",
        "Dash",
        "Leap Slam",
        "Whirling Blades",
        "Blink Arrow",
        "Lightning Warp",
        "Phase Run",
    },
)


class ViabilityIssue(BaseModel):
    """One viability check finding."""

    model_config = ConfigDict(frozen=True)

    severity: Literal["error", "warning"]
    code: str
    message_it: str
    message_en: str


class ViabilityReport(BaseModel):
    """All findings for one generated build."""

    model_config = ConfigDict(frozen=True)

    passed: bool = Field(
        default=True,
        description="True iff no error-severity issue was raised.",
    )
    issues: tuple[ViabilityIssue, ...] = ()


# ---------------------------------------------------------------------------
# Defence-layer detection
# ---------------------------------------------------------------------------


def _defence_layers(skeleton: BuildSkeleton) -> set[str]:
    """Return the set of defence layers detected on *skeleton*."""
    layers: set[str] = set()
    archetype = skeleton.intent.defence_archetype

    if archetype in ("life", "hybrid_life_es"):
        layers.add("life")
    if archetype == "es":
        layers.add("es")

    keystones = {n.name for n in skeleton.tree_nodes if n.type == "keystone" and n.name}
    if keystones & {"Acrobatics", "Phase Acrobatics"}:
        layers.add("evasion")
    if "Iron Reflexes" in keystones:
        layers.add("armour")
    if "Mind Over Matter" in keystones:
        layers.add("mom")
    # Chaos Inoculation collapses life to 1 and grants ES immunity to chaos;
    # only count it as a layer when ES is the explicit defence archetype.
    if "Chaos Inoculation" in keystones and archetype == "es":
        layers.add("ci")

    return layers


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def _check_resistances() -> ViabilityIssue:
    return ViabilityIssue(
        severity="warning",
        code="res_always_gear",
        message_it=(
            "Le resistenze si cappano con l'equipaggiamento, non con l'albero. "
            "Punta a ~135% totale sugli oggetti per coprire la penalita di "
            "Elemental Weakness."
        ),
        message_en=(
            "Resistances are capped through gear, not the tree. Aim for ~135% "
            "total on items to cover the Elemental Weakness map penalty."
        ),
    )


def _check_life_floor(skeleton: BuildSkeleton) -> ViabilityIssue | None:
    if skeleton.intent.defence_archetype == "es":
        return None
    floor = _LIFE_FLOOR[skeleton.intent.budget]
    val = skeleton.stats.life_estimate
    if val >= floor:
        return None
    return ViabilityIssue(
        severity="error",
        code="life_below_floor",
        message_it=(
            f"Vita stimata ({val}) sotto la soglia minima per SC mapping "
            f"({floor}). Aggiungi nodi life sull'albero o aumenta il budget."
        ),
        message_en=(
            f"Estimated life ({val}) is below the SC mapping floor ({floor}). "
            "Add life nodes on the tree or raise budget."
        ),
    )


def _check_es_floor(skeleton: BuildSkeleton) -> ViabilityIssue | None:
    if skeleton.intent.defence_archetype != "es":
        return None
    floor = _ES_FLOOR[skeleton.intent.budget]
    val = skeleton.stats.es_estimate
    if val >= floor:
        return None
    return ViabilityIssue(
        severity="error",
        code="es_below_floor",
        message_it=(
            f"Energy shield stimato ({val}) sotto la soglia minima per SC "
            f"mapping ({floor}). Aggiungi nodi ES sull'albero o aumenta il budget."
        ),
        message_en=(
            f"Estimated energy shield ({val}) is below the SC mapping floor "
            f"({floor}). Add ES nodes on the tree or raise budget."
        ),
    )


def _check_defence_layers(skeleton: BuildSkeleton) -> ViabilityIssue | None:
    if len(_defence_layers(skeleton)) >= 2:
        return None
    return ViabilityIssue(
        severity="warning",
        code="single_defence_layer",
        message_it=(
            "La build ha un solo layer difensivo. In PoE endgame servono "
            "almeno 2 layer (es. life + evasion, ES + block, MoM + armour)."
        ),
        message_en=(
            "The build has only one defence layer. PoE endgame requires at "
            "least 2 layers (e.g. life + evasion, ES + block, MoM + armour)."
        ),
    )


def _check_movement_skill(skeleton: BuildSkeleton) -> ViabilityIssue | None:
    skills = {link.skill for link in skeleton.links}
    if skills & _MOVEMENT_SKILLS:
        return None
    return ViabilityIssue(
        severity="warning",
        code="no_movement_skill",
        message_it=(
            "Nessuna skill di movimento rilevata. Aggiungi Flame Dash, Leap Slam o simile."
        ),
        message_en=("No movement skill detected. Add Flame Dash, Leap Slam, or similar."),
    )


def _check_spectre_selection(skeleton: BuildSkeleton) -> ViabilityIssue | None:
    """Spectre builds need a specific spectre monster selected in PoB.

    Step 55: Raise Spectre summons a *chosen monster*, so PoB (and our
    generated export) reports 0 DPS until the user picks a spectre from
    PoB's dropdown — we can't pick one without vendored monster data. The
    minion supports + minion tree scaling are correct; this just flags the
    one manual step the user must take for the DPS to materialise.
    """
    if "spectre" not in skeleton.intent.primary_skill.lower():
        return None
    return ViabilityIssue(
        severity="warning",
        code="spectre_needs_selection",
        message_it=(
            "Raise Spectre evoca un mostro specifico: in PoB seleziona uno "
            "spettro dal menu della gemma (es. uno spettro meta del momento) "
            "perche il DPS venga calcolato — l'export parte senza spettro scelto."
        ),
        message_en=(
            "Raise Spectre summons a specific monster: in PoB pick a spectre "
            "from the gem's dropdown (e.g. a current meta spectre) for the DPS "
            "to compute — the export ships with no spectre selected."
        ),
    )


def _check_mana_sustain(skeleton: BuildSkeleton) -> ViabilityIssue | None:
    has_mana_flask = any(
        slot.slot.startswith("Flask") and "Mana" in slot.base_name for slot in skeleton.gear_slots
    )
    has_lifetap = any("Lifetap" in support for link in skeleton.links for support in link.supports)
    if has_mana_flask or has_lifetap:
        return None
    return ViabilityIssue(
        severity="warning",
        code="missing_mana_sustain",
        message_it=(
            "Nessun flask di mana ne Lifetap rilevato. La build potrebbe "
            "avere problemi di mana in mapping."
        ),
        message_en=(
            "No mana flask or Lifetap detected. The build may have mana issues in mapping."
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_build(skeleton: BuildSkeleton) -> ViabilityReport:
    """Run every viability check against *skeleton* and aggregate findings."""
    issues: list[ViabilityIssue] = [_check_resistances()]
    for check in (
        _check_life_floor,
        _check_es_floor,
        _check_defence_layers,
        _check_movement_skill,
        _check_mana_sustain,
        _check_spectre_selection,
    ):
        issue = check(skeleton)
        if issue is not None:
            issues.append(issue)
    passed = not any(i.severity == "error" for i in issues)
    return ViabilityReport(passed=passed, issues=tuple(issues))


__all__ = ["ViabilityIssue", "ViabilityReport", "validate_build"]
