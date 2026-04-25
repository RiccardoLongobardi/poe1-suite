"""Per-dimension scoring functions for the Ranking Engine.

Each function maps a :class:`RemoteBuildRef` + :class:`BuildIntent` pair to a
score in ``[0.0, 1.0]``.  A score of ``0.5`` means "no signal" — the intent
or the ref doesn't carry enough information to discriminate on this axis.

The public entry-point is :func:`score_ref`, which assembles all dimensions
into a :class:`ScoreBreakdown` with the weighted total.

Weights (must sum to 1.0):
    damage    0.30
    playstyle 0.25
    budget    0.20
    content   0.15
    defense   0.05
    complexity 0.05
"""

from __future__ import annotations

import bisect

from poe1_builds.models import DefenseType, RemoteBuildRef
from poe1_core.models.build_intent import BuildIntent
from poe1_core.models.enums import (
    BudgetTier,
    ComplexityLevel,
    DamageProfile,
    DefenseProfile,
    Playstyle,
)

from .models import ScoreBreakdown

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NEUTRAL: float = 0.5

_WEIGHTS: dict[str, float] = {
    "damage": 0.30,
    "playstyle": 0.25,
    "budget": 0.20,
    "content": 0.15,
    "defense": 0.05,
    "complexity": 0.05,
}

# Keywords are all lowercase; matching is done against ``skill.casefold()``.
_DAMAGE_KEYWORDS: dict[DamageProfile, frozenset[str]] = {
    DamageProfile.COLD: frozenset(
        {
            "ice",
            "cold",
            "frost",
            "glacial",
            "arctic",
            "freezing",
            "blizzard",
            "hypothermia",
        }
    ),
    DamageProfile.FIRE: frozenset(
        {
            "fire",
            "flame",
            "flaming",
            "infernal",
            "magma",
            "scorching",
            "pyroclast",
            "fireball",
            "flameblast",
            "magma orb",
        }
    ),
    DamageProfile.LIGHTNING: frozenset(
        {
            "lightning",
            "thunder",
            "storm",
            "arc",
            "spark",
            "discharge",
            "ball lightning",
            "tempest",
            "static",
        }
    ),
    DamageProfile.CHAOS: frozenset(
        {
            "chaos",
            "void",
            "soulrend",
            "bane",
            "caustic",
            "dark pact",
            "malevolence",
        }
    ),
    DamageProfile.PHYSICAL: frozenset(
        {
            "earth shatter",
            "ground slam",
            "sunder",
            "lacerate",
            "splitting steel",
            "shrapnel ballista",
            "spectral helix",
            "spectral throw",
            "bladestorm",
        }
    ),
    DamageProfile.FIRE_DOT: frozenset({"righteous fire"}),
    DamageProfile.COLD_DOT: frozenset({"vortex", "cold snap"}),
    DamageProfile.CHAOS_DOT: frozenset(
        {
            "essence drain",
            "blight",
            "caustic arrow",
            "contagion",
        }
    ),
    DamageProfile.PHYSICAL_DOT: frozenset({"puncture", "bleed"}),
    DamageProfile.IGNITE: frozenset(
        {
            "burning arrow",
            "explosive arrow",
            "wave of conviction",
        }
    ),
    DamageProfile.BLEED: frozenset({"puncture", "splitting steel", "lacerate"}),
    DamageProfile.POISON: frozenset(
        {
            "cobra lash",
            "viper strike",
            "herald of agony",
            "poisonous concoction",
        }
    ),
    DamageProfile.MINION_PHYSICAL: frozenset(
        {
            "skeleton",
            "zombie",
            "spectre",
            "animate weapon",
            "animate guardian",
        }
    ),
    DamageProfile.MINION_ELEMENTAL: frozenset(
        {
            "raging spirit",
            "absolution",
            "carrion golem",
            "lightning golem",
            "stone golem",
            "chaos golem",
            "fire golem",
            "ice golem",
        }
    ),
    DamageProfile.MINION_CHAOS: frozenset({"reaper", "summon reaper", "spiders"}),
    DamageProfile.ELEMENTAL_HYBRID: frozenset(
        {
            "discharge",
            "shockwave totem",
            "inquisitor",
        }
    ),
    DamageProfile.HYBRID: frozenset(),
}

# All minion-related damage profiles
_MINION_PROFILES: frozenset[DamageProfile] = frozenset(
    {
        DamageProfile.MINION_PHYSICAL,
        DamageProfile.MINION_ELEMENTAL,
        DamageProfile.MINION_CHAOS,
    }
)

# Keywords that indicate any minion build
_MINION_KEYWORDS: frozenset[str] = frozenset(
    {
        "summon",
        "skeleton",
        "zombie",
        "spectre",
        "animate",
        "raging spirit",
        "absolution",
        "carrion",
        "golem",
        "reaper",
    }
)

_PLAYSTYLE_KEYWORDS: dict[Playstyle, frozenset[str]] = {
    Playstyle.TOTEM: frozenset({"totem", "ballista"}),
    Playstyle.TRAP: frozenset({"trap"}),
    Playstyle.MINE: frozenset({"mine"}),
    Playstyle.MINION: frozenset(
        {
            "summon",
            "skeleton",
            "zombie",
            "spectre",
            "animate",
            "raging spirit",
            "golem",
            "carrion",
            "absolution",
            "reaper",
        }
    ),
    Playstyle.BRAND: frozenset({"brand"}),
    Playstyle.RANGED_ATTACK: frozenset(
        {
            "arrow",
            "barrage",
            "tornado shot",
            "rain of",
            "shrapnel",
            "caustic arrow",
            "burning arrow",
            "explosive arrow",
            "galvanic arrow",
            "splitting steel",
            "spectral helix",
        }
    ),
    Playstyle.MELEE: frozenset(
        {
            "strike",
            "slam",
            "cyclone",
            "blade flurry",
            "flicker",
            "ground slam",
            "cleave",
            "reave",
            "consecrated path",
            "earthquake",
            "lacerate",
            "bladestorm",
        }
    ),
    Playstyle.DEGEN_AURA: frozenset({"righteous fire"}),
    Playstyle.CAST_WHILE_CHANNELLING: frozenset({"cast while channelling", "cwc"}),
    Playstyle.CAST_WHEN_DAMAGE_TAKEN: frozenset({"cast when damage taken", "cwdt"}),
    Playstyle.SELF_CAST: frozenset(),  # inferred by absence of other markers
    Playstyle.HYBRID: frozenset(),
}

# Union of all non-self-cast, non-hybrid playstyle markers (pre-computed)
_NON_SELF_CAST_MARKERS: frozenset[str] = frozenset(
    kw
    for ps, kws in _PLAYSTYLE_KEYWORDS.items()
    for kw in kws
    if ps not in (Playstyle.SELF_CAST, Playstyle.HYBRID)
)

_HIGH_COMPLEXITY_SKILLS: frozenset[str] = frozenset({"flicker", "discharge"})
_LOW_COMPLEXITY_SKILLS: frozenset[str] = frozenset(
    {
        "summon",
        "skeleton",
        "zombie",
        "totem",
        "brand",
        "raging spirit",
        "righteous fire",
        "golem",
    }
)

# Maps each DefenseProfile to the set of DefenseType values it is compatible with
_DEFENSE_COMPAT: dict[DefenseProfile, frozenset[DefenseType]] = {
    DefenseProfile.LIFE: frozenset({DefenseType.LIFE, DefenseType.LIFE_ES}),
    DefenseProfile.CHAOS_INOCULATION: frozenset({DefenseType.CI}),
    DefenseProfile.LOW_LIFE: frozenset({DefenseType.LOW_LIFE}),
    DefenseProfile.HYBRID: frozenset({DefenseType.LIFE_ES, DefenseType.HYBRID}),
    DefenseProfile.EVASION: frozenset({DefenseType.LIFE}),
    DefenseProfile.ARMOUR: frozenset({DefenseType.LIFE}),
    DefenseProfile.BLOCK: frozenset({DefenseType.LIFE, DefenseType.LIFE_ES}),
    DefenseProfile.MIND_OVER_MATTER: frozenset({DefenseType.MOM}),
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _skill_contains(skill: str | None, keywords: frozenset[str]) -> bool:
    """Return True if the lowercased skill name contains any keyword."""
    if not skill or not keywords:
        return False
    s = skill.casefold()
    return any(kw in s for kw in keywords)


def _classify_ref_defense(ref: RemoteBuildRef) -> DefenseType:
    """Approximate defence type from the ref's life/ES totals.

    Mirrors :meth:`BuildsService.classify_defense` but accepts a
    :class:`RemoteBuildRef` instead of :class:`DefensiveStats`.
    """
    life, es = ref.life, ref.energy_shield
    if life <= 1 and es > 0:
        return DefenseType.CI if es >= 5000 else DefenseType.LOW_LIFE
    if es >= max(1, life) * 3:
        return DefenseType.ENERGY_SHIELD
    if es >= max(1, life) // 2:
        return DefenseType.LIFE_ES
    return DefenseType.LIFE


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------


def score_damage(ref: RemoteBuildRef, intent: BuildIntent) -> float:
    """Score how well the ref's main skill matches the intent's damage profile."""
    if intent.damage_profile is None:
        return _NEUTRAL

    wanted = intent.damage_profile
    skill = ref.main_skill

    if skill is None:
        return _NEUTRAL

    # --- Primary match ---
    primary_kw = _DAMAGE_KEYWORDS.get(wanted, frozenset())
    if _skill_contains(skill, primary_kw):
        return 1.0

    # --- Alternative damage profiles (partial credit) ---
    for alt in intent.alternative_damage_profiles:
        alt_kw = _DAMAGE_KEYWORDS.get(alt, frozenset())
        if _skill_contains(skill, alt_kw):
            return 0.7

    # --- Minion family partial match ---
    if wanted in _MINION_PROFILES and _skill_contains(skill, _MINION_KEYWORDS):
        return 0.6

    # --- Check if another profile clearly owns this skill ---
    for other, kw in _DAMAGE_KEYWORDS.items():
        if other == wanted or not kw:
            continue
        if _skill_contains(skill, kw):
            return 0.1  # another profile matched → mismatch

    return _NEUTRAL  # no clear signal


def score_playstyle(ref: RemoteBuildRef, intent: BuildIntent) -> float:
    """Score how well the ref's main skill matches the intent's playstyle."""
    if intent.playstyle is None:
        return _NEUTRAL

    wanted = intent.playstyle
    skill = ref.main_skill

    if skill is None:
        return _NEUTRAL

    # --- Primary match ---
    primary_kw = _PLAYSTYLE_KEYWORDS.get(wanted, frozenset())
    if primary_kw and _skill_contains(skill, primary_kw):
        return 1.0

    # --- Alternative playstyles (partial credit) ---
    for alt in intent.alternative_playstyles:
        alt_kw = _PLAYSTYLE_KEYWORDS.get(alt, frozenset())
        if alt_kw and _skill_contains(skill, alt_kw):
            return 0.7

    # --- Self-cast is inferred by absence of other strong markers ---
    if wanted == Playstyle.SELF_CAST:
        if not _skill_contains(skill, _NON_SELF_CAST_MARKERS):
            return 0.8  # no totem / trap / minion / etc. → likely self-cast
        return 0.2

    # --- Check if a competing playstyle clearly owns this skill ---
    for other, kw in _PLAYSTYLE_KEYWORDS.items():
        if other == wanted or not kw:
            continue
        if _skill_contains(skill, kw):
            return 0.1

    return _NEUTRAL


def score_budget(
    ref: RemoteBuildRef,
    intent: BuildIntent,
    *,
    pool_dps_sorted: tuple[int, ...],
) -> float:
    """Score how well the ref's investment level matches the intent's budget tier.

    Uses the ref's DPS as a proxy for investment: high DPS on the ladder
    generally implies expensive gear.  The score is a function of the ref's
    DPS percentile within the current candidate pool.
    """
    if intent.budget is None or intent.budget.tier is None or not pool_dps_sorted:
        return _NEUTRAL

    tier = intent.budget.tier
    n = len(pool_dps_sorted)
    idx = bisect.bisect_left(pool_dps_sorted, ref.dps)
    pct = idx / n  # 0.0 = lowest DPS in pool, 1.0 = highest

    if tier in (BudgetTier.LEAGUE_START, BudgetTier.LOW):
        # Prefer lower-investment (lower DPS) builds
        return 1.0 - pct
    if tier == BudgetTier.MEDIUM:
        return 0.6  # neutral — medium builds can be anywhere on the ladder
    # HIGH or MIRROR: prefer higher-investment builds
    return pct


def score_content(ref: RemoteBuildRef, intent: BuildIntent) -> float:
    """Score content-focus compatibility.

    ``RemoteBuildRef`` carries no content-type tags, so this dimension
    returns a neutral ``0.5`` for all candidates.  A future version can
    use hydrated ``FullBuild`` keystone / item signals to discriminate
    mapper vs bosser vs simulacrum builds.
    """
    # Suppress unused-parameter warnings; the signature is symmetric with the
    # other scorers so callers can treat them uniformly.
    _ = ref, intent
    return _NEUTRAL


def score_defense(ref: RemoteBuildRef, intent: BuildIntent) -> float:
    """Score how well the ref's defence type matches the intent's defense profile."""
    if intent.defense_profile is None:
        return _NEUTRAL

    ref_type = _classify_ref_defense(ref)
    compat = _DEFENSE_COMPAT.get(intent.defense_profile, frozenset())
    return 1.0 if ref_type in compat else 0.1


def score_complexity(ref: RemoteBuildRef, intent: BuildIntent) -> float:
    """Score whether the ref's apparent complexity respects the intent's cap."""
    if intent.complexity_cap is None:
        return _NEUTRAL

    is_high = _skill_contains(ref.main_skill, _HIGH_COMPLEXITY_SKILLS)
    is_low = _skill_contains(ref.main_skill, _LOW_COMPLEXITY_SKILLS)

    if intent.complexity_cap == ComplexityLevel.LOW:
        if is_high:
            return 0.1
        if is_low:
            return 0.9
        return 0.6

    if intent.complexity_cap == ComplexityLevel.MEDIUM:
        if is_high:
            return 0.4
        if is_low:
            return 0.7
        return 0.6

    # HIGH cap — anything goes
    return 0.7


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------


def score_ref(
    ref: RemoteBuildRef,
    intent: BuildIntent,
    *,
    pool_dps_sorted: tuple[int, ...],
) -> ScoreBreakdown:
    """Compute a :class:`ScoreBreakdown` for one ref against one intent."""
    damage = score_damage(ref, intent)
    playstyle = score_playstyle(ref, intent)
    budget = score_budget(ref, intent, pool_dps_sorted=pool_dps_sorted)
    content = score_content(ref, intent)
    defense = score_defense(ref, intent)
    complexity = score_complexity(ref, intent)

    total = (
        _WEIGHTS["damage"] * damage
        + _WEIGHTS["playstyle"] * playstyle
        + _WEIGHTS["budget"] * budget
        + _WEIGHTS["content"] * content
        + _WEIGHTS["defense"] * defense
        + _WEIGHTS["complexity"] * complexity
    )
    total = round(min(1.0, max(0.0, total)), 6)

    return ScoreBreakdown(
        damage=damage,
        playstyle=playstyle,
        budget=budget,
        content=content,
        defense=defense,
        complexity=complexity,
        total=total,
    )


__all__ = [
    "score_budget",
    "score_complexity",
    "score_content",
    "score_damage",
    "score_defense",
    "score_playstyle",
    "score_ref",
]
