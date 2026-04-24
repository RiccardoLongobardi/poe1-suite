"""Canonical enumerations shared across the suite.

All enum values are lowercase snake_case strings. Treat these as the
*stable vocabulary* that every other module, every serialised payload,
and every persisted record must speak.

Changes here are breaking: when adding a value, make sure downstream
mappers (Intent parser dictionaries, PoB classifier, poe.ninja ingestion)
are updated in the same commit.
"""

from __future__ import annotations

from enum import StrEnum


class CharacterClass(StrEnum):
    """PoE 1 base character classes."""

    MARAUDER = "marauder"
    DUELIST = "duelist"
    RANGER = "ranger"
    SHADOW = "shadow"
    WITCH = "witch"
    TEMPLAR = "templar"
    SCION = "scion"


class Ascendancy(StrEnum):
    """All PoE 1 ascendancies grouped implicitly by base class.

    Mapping to :class:`CharacterClass` lives in :func:`ascendancy_to_class`.
    """

    # Marauder
    JUGGERNAUT = "juggernaut"
    BERSERKER = "berserker"
    CHIEFTAIN = "chieftain"
    # Duelist
    SLAYER = "slayer"
    GLADIATOR = "gladiator"
    CHAMPION = "champion"
    # Ranger
    DEADEYE = "deadeye"
    RAIDER = "raider"
    PATHFINDER = "pathfinder"
    # Shadow
    ASSASSIN = "assassin"
    SABOTEUR = "saboteur"
    TRICKSTER = "trickster"
    # Witch
    NECROMANCER = "necromancer"
    OCCULTIST = "occultist"
    ELEMENTALIST = "elementalist"
    # Templar
    INQUISITOR = "inquisitor"
    HIEROPHANT = "hierophant"
    GUARDIAN = "guardian"
    # Scion
    ASCENDANT = "ascendant"


_ASCENDANCY_CLASS: dict[Ascendancy, CharacterClass] = {
    Ascendancy.JUGGERNAUT: CharacterClass.MARAUDER,
    Ascendancy.BERSERKER: CharacterClass.MARAUDER,
    Ascendancy.CHIEFTAIN: CharacterClass.MARAUDER,
    Ascendancy.SLAYER: CharacterClass.DUELIST,
    Ascendancy.GLADIATOR: CharacterClass.DUELIST,
    Ascendancy.CHAMPION: CharacterClass.DUELIST,
    Ascendancy.DEADEYE: CharacterClass.RANGER,
    Ascendancy.RAIDER: CharacterClass.RANGER,
    Ascendancy.PATHFINDER: CharacterClass.RANGER,
    Ascendancy.ASSASSIN: CharacterClass.SHADOW,
    Ascendancy.SABOTEUR: CharacterClass.SHADOW,
    Ascendancy.TRICKSTER: CharacterClass.SHADOW,
    Ascendancy.NECROMANCER: CharacterClass.WITCH,
    Ascendancy.OCCULTIST: CharacterClass.WITCH,
    Ascendancy.ELEMENTALIST: CharacterClass.WITCH,
    Ascendancy.INQUISITOR: CharacterClass.TEMPLAR,
    Ascendancy.HIEROPHANT: CharacterClass.TEMPLAR,
    Ascendancy.GUARDIAN: CharacterClass.TEMPLAR,
    Ascendancy.ASCENDANT: CharacterClass.SCION,
}


def ascendancy_to_class(asc: Ascendancy) -> CharacterClass:
    """Return the base :class:`CharacterClass` for a given ascendancy."""

    return _ASCENDANCY_CLASS[asc]


class DamageProfile(StrEnum):
    """The high-level *flavour* of damage a build deals.

    Hit vs DoT is encoded here rather than as a separate axis because
    downstream (ranking, planner) always wants to reason about them together.
    """

    PHYSICAL = "physical"
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    CHAOS = "chaos"

    # DoT variants
    FIRE_DOT = "fire_dot"
    COLD_DOT = "cold_dot"
    CHAOS_DOT = "chaos_dot"
    PHYSICAL_DOT = "physical_dot"

    # Ailment-based damage
    IGNITE = "ignite"
    BLEED = "bleed"
    POISON = "poison"

    # Minion damage
    MINION_PHYSICAL = "minion_physical"
    MINION_ELEMENTAL = "minion_elemental"
    MINION_CHAOS = "minion_chaos"

    # Mixed / hybrid
    ELEMENTAL_HYBRID = "elemental_hybrid"
    HYBRID = "hybrid"


class Playstyle(StrEnum):
    """How the player actually *plays* the build — independent of damage type."""

    MELEE = "melee"
    RANGED_ATTACK = "ranged_attack"  # bow, wand
    SELF_CAST = "self_cast"
    TOTEM = "totem"
    TRAP = "trap"
    MINE = "mine"
    MINION = "minion"
    BRAND = "brand"
    CAST_WHILE_CHANNELLING = "cast_while_channelling"
    CAST_WHEN_DAMAGE_TAKEN = "cast_when_damage_taken"
    DEGEN_AURA = "degen_aura"  # RF, PConc-style auto-damage
    HYBRID = "hybrid"


class ContentFocus(StrEnum):
    """What content a build is designed for."""

    MAPPING = "mapping"
    BOSSING = "bossing"
    UBERS = "ubers"
    DELVE = "delve"
    SANCTUM = "sanctum"
    SIMULACRUM = "simulacrum"
    HEIST = "heist"
    RACING = "racing"
    LEAGUE_START = "league_start"
    GENERALIST = "generalist"


class DefenseProfile(StrEnum):
    """Defensive archetype."""

    LIFE = "life"
    CHAOS_INOCULATION = "chaos_inoculation"
    LOW_LIFE = "low_life"
    HYBRID = "hybrid"
    EVASION = "evasion"
    ARMOUR = "armour"
    BLOCK = "block"
    MIND_OVER_MATTER = "mind_over_matter"


class ComplexityLevel(StrEnum):
    """Player-perceived complexity: keybinds, flask piano, manual interactions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BudgetTier(StrEnum):
    """Rough budget bands in divines.

    Exact ranges are defined in :func:`budget_tier_range`.
    """

    LEAGUE_START = "league_start"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MIRROR = "mirror"


_BUDGET_RANGES: dict[BudgetTier, tuple[float, float]] = {
    BudgetTier.LEAGUE_START: (0.0, 1.0),
    BudgetTier.LOW: (1.0, 5.0),
    BudgetTier.MEDIUM: (5.0, 25.0),
    BudgetTier.HIGH: (25.0, 100.0),
    BudgetTier.MIRROR: (100.0, float("inf")),
}


def budget_tier_range(tier: BudgetTier) -> tuple[float, float]:
    """Return the (min, max) range in divines for a given budget tier."""

    return _BUDGET_RANGES[tier]


class HardConstraint(StrEnum):
    """Non-negotiable preferences extracted from the player input.

    These are applied as filters *before* scoring in the ranking engine.
    A single violation removes a build from the candidate set entirely.
    """

    NO_MELEE = "no_melee"
    NO_MINION = "no_minion"
    NO_TOTEM = "no_totem"
    NO_TRAP_MINE = "no_trap_mine"
    NO_RF = "no_rf"
    NO_SELF_CAST = "no_self_cast"
    NO_LOW_LIFE = "no_low_life"
    NO_CI = "no_ci"
    HARDCORE_VIABLE = "hardcore_viable"
    SSF_VIABLE = "ssf_viable"


class ItemRarity(StrEnum):
    """PoE item rarity."""

    NORMAL = "normal"
    MAGIC = "magic"
    RARE = "rare"
    UNIQUE = "unique"


class ItemSlot(StrEnum):
    """Equipment slot on a character."""

    HELMET = "helmet"
    BODY_ARMOUR = "body_armour"
    GLOVES = "gloves"
    BOOTS = "boots"
    BELT = "belt"
    AMULET = "amulet"
    RING = "ring"
    WEAPON_MAIN = "weapon_main"
    WEAPON_OFFHAND = "weapon_offhand"
    QUIVER = "quiver"
    FLASK = "flask"
    JEWEL = "jewel"
    CLUSTER_JEWEL = "cluster_jewel"


class PriceSource(StrEnum):
    """Where a price came from.

    The planner will weight observed prices higher than heuristic ones
    when producing a total stage cost.
    """

    POE_NINJA = "poe_ninja"
    TRADE_API = "trade_api"
    HEURISTIC = "heuristic"
    USER = "user"
    UNKNOWN = "unknown"


class BuildSourceType(StrEnum):
    """Type of the :class:`~poe1_core.models.build.Build` provenance."""

    POB = "pob"
    POE_NINJA_BUILDS = "poe_ninja_builds"
    GUIDE = "guide"
    USER_ENTERED = "user_entered"


class Currency(StrEnum):
    """Supported pricing currencies.

    The suite is divine-centric: prices are normalised to divines whenever
    the source reports something else. :class:`Currency.CHAOS` is kept
    because some listings are natively cheap and `divines < 1` hurts UX.
    """

    DIVINE = "divine"
    CHAOS = "chaos"


class ModType(StrEnum):
    """Type of mod on an :class:`~poe1_core.models.item.Item`."""

    IMPLICIT = "implicit"
    EXPLICIT = "explicit"
    CRAFTED = "crafted"
    ENCHANT = "enchant"
    SYNTHESISED = "synthesised"
    FRACTURED = "fractured"
    VEILED = "veiled"
    SCOURGE = "scourge"


class TargetGoal(StrEnum):
    """End-goal of a :class:`~poe1_core.models.plan.BuildPlan`."""

    MAPPING_ONLY = "mapping_only"
    MAPPING_AND_BOSS = "mapping_and_boss"
    UBER_CAPABLE = "uber_capable"


class ParserOrigin(StrEnum):
    """Which parser produced a :class:`BuildIntent`."""

    RULE_BASED = "rule_based"
    LLM = "llm"
    HYBRID = "hybrid"


class ClearSpeedTier(StrEnum):
    """Qualitative clear-speed bucket used by ranking."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class Confidence(StrEnum):
    """Three-band confidence used by prices and heuristic estimates."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


__all__ = [
    "Ascendancy",
    "BudgetTier",
    "BuildSourceType",
    "CharacterClass",
    "ClearSpeedTier",
    "ComplexityLevel",
    "Confidence",
    "ContentFocus",
    "Currency",
    "DamageProfile",
    "DefenseProfile",
    "HardConstraint",
    "ItemRarity",
    "ItemSlot",
    "ModType",
    "ParserOrigin",
    "Playstyle",
    "PriceSource",
    "TargetGoal",
    "ascendancy_to_class",
    "budget_tier_range",
]
