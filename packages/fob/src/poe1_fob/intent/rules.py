"""Rule-based intent extractor — deterministic, no network calls.

Scans the raw query text for Italian and English synonyms mapped to
:class:`poe1_core.BuildIntent` fields.  Returns a ``(BuildIntent,
confidence)`` pair where *confidence* ∈ [0, 1].

Confidence formula
------------------
Each matched field contributes a weight to the confidence score.  The
weights are tuned so that two well-matched fields produce ≥ 0.7 (the
threshold above which the LLM fallback is skipped).

    base_confidence = sum(field_weights for matched fields)
    confidence      = min(1.0, base_confidence)

Field weights
~~~~~~~~~~~~~
- damage_profile  0.30
- playstyle       0.25
- content_focus   0.20
- budget          0.15
- complexity_cap  0.05
- defense_profile 0.05
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from poe1_core.models.build_intent import BudgetRange, BuildIntent, ContentFocusWeight
from poe1_core.models.enums import (
    BudgetTier,
    ComplexityLevel,
    ContentFocus,
    DamageProfile,
    DefenseProfile,
    HardConstraint,
    ParserOrigin,
    Playstyle,
)

# ---------------------------------------------------------------------------
# Synonym tables
# ---------------------------------------------------------------------------

_DAMAGE_PROFILE: Final[list[tuple[DamageProfile, list[str]]]] = [
    # DoT first — more specific
    (
        DamageProfile.FIRE_DOT,
        [
            "fuoco dot",
            "ignite dot",
            "dot fuoco",
            "burning",
            "combustione",
            "arson",
        ],
    ),
    (DamageProfile.COLD_DOT, ["freddo dot", "cold dot", "dot freddo", "freezing dot"]),
    (DamageProfile.CHAOS_DOT, ["chaos dot", "dot chaos", "poison dot", "veleno dot"]),
    (
        DamageProfile.PHYSICAL_DOT,
        ["phys dot", "fisico dot", "bleed dot", "sanguinamento dot"],
    ),
    # Ailments
    (DamageProfile.IGNITE, ["ignite", "incendia", "flask ignite", "ignition"]),
    (DamageProfile.BLEED, ["bleed", "sanguinamento", "sanguina", "bleeding"]),
    (DamageProfile.POISON, ["poison", "veleno", "avvelena"]),
    # Minion specific (before generic minion)
    (DamageProfile.MINION_PHYSICAL, ["minion phys", "servitori fisici", "skeleton", "scheletri"]),
    (DamageProfile.MINION_ELEMENTAL, ["minion ele", "servitori elementali"]),
    (DamageProfile.MINION_CHAOS, ["minion chaos", "servitori chaos"]),
    # Elemental hit-based
    (
        DamageProfile.COLD,
        ["cold", "freddo", "ghiaccio", "ice", "freeze", "congelamento", "cryo"],
    ),
    (DamageProfile.FIRE, ["fire", "fuoco", "fiamma", "flame", "pyromanc", "piro"]),
    (
        DamageProfile.LIGHTNING,
        [
            "lightning",
            "fulmine",
            "tuono",
            "thunder",
            "storm",
            "tempesta",
            "arc",
        ],
    ),
    (DamageProfile.CHAOS, ["chaos", "corruzione", "corrupt", "void", "vuoto"]),
    (DamageProfile.PHYSICAL, ["physical", "fisico", "phys", "impatto fisico"]),
    # Minion generic (after specific minion variants)
    (
        DamageProfile.MINION_PHYSICAL,
        [
            "minion",
            "servitor",
            "servitori",
            "spectr",
            "zombie",
            "summoner",
            "evocator",
            "necro",
            "necromancer",
        ],
    ),
    # Hybrid last
    (DamageProfile.HYBRID, ["hybrid", "ibrido", "misto", "mixed"]),
]

_PLAYSTYLE: Final[list[tuple[Playstyle, list[str]]]] = [
    (Playstyle.TOTEM, ["totem", "totemo"]),
    (Playstyle.TRAP, ["trap", "trappola", "traps"]),
    (Playstyle.MINE, ["mine", "mina", "mino"]),
    (
        Playstyle.MINION,
        [
            "minion",
            "servitor",
            "servitori",
            "spectr",
            "zombie",
            "summoner",
            "necro",
            "necromancer",
            "evocator",
        ],
    ),
    (Playstyle.BRAND, ["brand", "sigillo", "marchio"]),
    (
        Playstyle.CAST_WHILE_CHANNELLING,
        [
            "cwc",
            "cast while channelling",
            "incanta mentre canalizza",
        ],
    ),
    (Playstyle.CAST_WHEN_DAMAGE_TAKEN, ["cwdt", "cast when damage taken"]),
    (
        Playstyle.DEGEN_AURA,
        [
            "degen aura",
            "rf",
            "righteous fire",
            "fuoco giusto",
            "aura degen",
        ],
    ),
    (
        Playstyle.RANGED_ATTACK,
        [
            "ranged",
            "distanza",
            "bow",
            "arco",
            "wand",
            "bacchetta",
            "caster ranged",
        ],
    ),
    (Playstyle.MELEE, ["melee", "mischia", "corpo a corpo", "cac"]),
    (Playstyle.SELF_CAST, ["self cast", "lancia", "caster", "casts", "cast spell"]),
    (Playstyle.HYBRID, ["hybrid playstyle", "ibrido playstyle"]),
]

_CONTENT_FOCUS: Final[list[tuple[ContentFocus, list[str]]]] = [
    (
        ContentFocus.UBERS,
        [
            "uber",
            "uber boss",
            "uber elder",
            "uber maven",
            "pinnacle",
            "pinnacolo",
        ],
    ),
    (ContentFocus.BOSSING, ["boss", "bossing", "uccisore di boss", "boss killer"]),
    (ContentFocus.DELVE, ["delve", "profondita", "profondità", "abyss mine"]),
    (ContentFocus.SANCTUM, ["sanctum", "santuario"]),
    (ContentFocus.SIMULACRUM, ["simulacrum", "simul", "simulacro"]),
    (ContentFocus.HEIST, ["heist", "colpo", "rapina"]),
    (ContentFocus.RACING, ["racing", "race", "gara", "speed run"]),
    (
        ContentFocus.LEAGUE_START,
        [
            "league start",
            "inizio lega",
            "starter",
            "parta da zero",
            "from scratch",
        ],
    ),
    (
        ContentFocus.MAPPING,
        [
            "mapping",
            "mapper",
            "map",
            "mappe",
            "mappa",
            "farm",
            "farming",
            "clear",
            "clearspeed",
            "aoe",
            "area",
            "area of effect",
            "zona",
            "grind",
            "grindare",
        ],
    ),
    (
        ContentFocus.GENERALIST,
        ["generalist", "generalista", "tuttofare", "all content", "tutto"],
    ),
]

_BUDGET: Final[list[tuple[BudgetTier, list[str]]]] = [
    (
        BudgetTier.MIRROR,
        [
            "mirror",
            "specchio",
            "illimitato",
            "no budget",
            "no limit",
            "full mirror",
        ],
    ),
    (
        BudgetTier.HIGH,
        [
            "expensive",
            "costoso",
            "costosa",
            "ricco",
            "rich",
            "high budget",
            "alto budget",
            "many div",
            "tanti div",
            "molto investimento",
        ],
    ),
    (
        BudgetTier.MEDIUM,
        [
            "medium budget",
            "budget medio",
            "medio",
            "moderate",
            "moderato",
            "mid budget",
        ],
    ),
    (
        BudgetTier.LOW,
        [
            "low budget",
            "budget basso",
            "cheap",
            "economico",
            "a buon prezzo",
            "poco budget",
        ],
    ),
    (
        BudgetTier.LEAGUE_START,
        [
            "league start",
            "starter",
            "inizio lega",
            "0 div",
            "zero div",
            "niente budget",
            "senza budget",
            "f2p",
            "self found",
            "ssf",
            "povero",
            "poor",
        ],
    ),
]

_COMPLEXITY: Final[list[tuple[ComplexityLevel, list[str]]]] = [
    (
        ComplexityLevel.LOW,
        [
            "semplice",
            "simple",
            "easy",
            "facile",
            "comfy",
            "comodo",
            "rilassante",
            "brain dead",
            "braindead",
            "auto pilot",
            "autopilot",
            "chill",
        ],
    ),
    (ComplexityLevel.MEDIUM, ["medio", "medium complexity", "moderato", "moderate"]),
    (
        ComplexityLevel.HIGH,
        [
            "complesso",
            "complex",
            "hard",
            "difficile",
            "tecnico",
            "technical",
            "high apm",
        ],
    ),
]

_DEFENSE: Final[list[tuple[DefenseProfile, list[str]]]] = [
    (
        DefenseProfile.CHAOS_INOCULATION,
        [
            "ci",
            "chaos inoculation",
            "inoculazione chaos",
            "full es",
            "es pure",
        ],
    ),
    (DefenseProfile.LOW_LIFE, ["low life", "bassa vita", "shav", "shavronnes"]),
    (DefenseProfile.MIND_OVER_MATTER, ["mom", "mind over matter", "mente sulla materia"]),
    (DefenseProfile.BLOCK, ["block", "blocco", "max block", "blocco massimo"]),
    (DefenseProfile.EVASION, ["evasion", "elusione", "dodge", "schivata", "eva"]),
    (DefenseProfile.ARMOUR, ["armour", "armatura", "armor", "phys reduction"]),
    (DefenseProfile.LIFE, ["life build", "life based", "vita", "life regen"]),
    (DefenseProfile.HYBRID, ["hybrid defense", "difesa ibrida", "life es hybrid"]),
]

_CONSTRAINTS: Final[list[tuple[HardConstraint, list[str]]]] = [
    (HardConstraint.NO_MELEE, ["no melee", "no mischia", "niente mischia", "not melee"]),
    (
        HardConstraint.NO_MINION,
        ["no minion", "no servitori", "niente minion", "not minion"],
    ),
    (HardConstraint.NO_TOTEM, ["no totem", "niente totem", "not totem"]),
    (HardConstraint.NO_TRAP_MINE, ["no trap", "no mine", "niente trappole", "no trappola"]),
    (HardConstraint.NO_RF, ["no rf", "no righteous fire", "no fuoco giusto"]),
    (HardConstraint.NO_SELF_CAST, ["no self cast", "no cast", "niente self cast"]),
    (HardConstraint.NO_LOW_LIFE, ["no low life", "no bassa vita"]),
    (HardConstraint.NO_CI, ["no ci", "no chaos inoculation"]),
    (
        HardConstraint.HARDCORE_VIABLE,
        ["hardcore", "hc", "hcssf", "hardcore viable", "hc viable"],
    ),
    (HardConstraint.SSF_VIABLE, ["ssf", "self found", "solo self found", "ssf viable"]),
]

# ---------------------------------------------------------------------------
# Confidence weights per field
# ---------------------------------------------------------------------------

_W_DAMAGE: Final[float] = 0.30
_W_PLAYSTYLE: Final[float] = 0.25
_W_CONTENT: Final[float] = 0.20
_W_BUDGET: Final[float] = 0.15
_W_COMPLEXITY: Final[float] = 0.05
_W_DEFENSE: Final[float] = 0.05

# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    stripped = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped).strip()


def _match_first(norm: str, table: list[tuple[object, list[str]]]) -> object | None:
    """Return the first enum value whose synonym list has a hit in *norm*."""
    for value, synonyms in table:
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", norm):
                return value
    return None


def _match_all(norm: str, table: list[tuple[object, list[str]]]) -> list[object]:
    """Return all enum values with at least one synonym hit (ordered by table position)."""
    results: list[object] = []
    for value, synonyms in table:
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", norm):
                results.append(value)
                break
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def rule_based_extract(raw: str) -> tuple[BuildIntent, float]:
    """Parse *raw* with synonym tables.  Returns ``(intent, confidence)``."""
    norm = _normalise(raw)

    # Strip "no <word>" phrases before playstyle matching so "no trap" doesn't
    # produce Playstyle.TRAP as a false positive.
    norm_no_neg = re.sub(r"\bno\s+\w+", "", norm)

    # --- damage_profile ---
    damage_matches = _match_all(norm_no_neg, _DAMAGE_PROFILE)  # type: ignore[arg-type]
    damage_profile = damage_matches[0] if damage_matches else None
    alt_damage = list(damage_matches[1:3])

    # --- playstyle ---
    playstyle_matches = _match_all(norm_no_neg, _PLAYSTYLE)  # type: ignore[arg-type]
    playstyle = playstyle_matches[0] if playstyle_matches else None
    alt_playstyle = list(playstyle_matches[1:2])

    # --- content_focus ---
    content_matches = _match_all(norm, _CONTENT_FOCUS)  # type: ignore[arg-type]
    content_focus: list[ContentFocusWeight] = []
    if content_matches:
        n = len(content_matches)
        for i, cf in enumerate(content_matches[:3]):
            # linear decay: first match gets highest weight
            w = round(1.0 / (i + 1) / sum(1.0 / (j + 1) for j in range(n)), 3)
            content_focus.append(ContentFocusWeight(focus=cf, weight=w))  # type: ignore[arg-type]

    # --- budget ---
    budget: BudgetRange | None = None
    bt = _match_first(norm, _BUDGET)  # type: ignore[arg-type]
    if bt is not None:
        budget = BudgetRange(tier=bt)  # type: ignore[arg-type]

    # --- complexity ---
    complexity = _match_first(norm, _COMPLEXITY)  # type: ignore[arg-type]

    # --- defense ---
    defense = _match_first(norm, _DEFENSE)  # type: ignore[arg-type]

    # --- hard constraints ---
    constraints = set(_match_all(norm, _CONSTRAINTS))  # type: ignore[arg-type]

    # --- confidence ---
    conf = 0.0
    if damage_profile is not None:
        conf += _W_DAMAGE
    if playstyle is not None:
        conf += _W_PLAYSTYLE
    if content_focus:
        conf += _W_CONTENT
    if budget is not None:
        conf += _W_BUDGET
    if complexity is not None:
        conf += _W_COMPLEXITY
    if defense is not None:
        conf += _W_DEFENSE
    confidence = round(min(1.0, conf), 4)

    intent = BuildIntent(
        damage_profile=damage_profile,  # type: ignore[arg-type]
        alternative_damage_profiles=alt_damage,  # type: ignore[arg-type]
        playstyle=playstyle,  # type: ignore[arg-type]
        alternative_playstyles=alt_playstyle,  # type: ignore[arg-type]
        content_focus=content_focus,
        budget=budget,
        complexity_cap=complexity,  # type: ignore[arg-type]
        defense_profile=defense,  # type: ignore[arg-type]
        hard_constraints=constraints,  # type: ignore[arg-type]
        confidence=confidence,
        raw_input=raw,
        parser_origin=ParserOrigin.RULE_BASED,
    )
    return intent, confidence


__all__ = ["rule_based_extract"]
