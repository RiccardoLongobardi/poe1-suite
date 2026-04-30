"""Extract Trade-API-ready stat filters from a PoB rare item.

Two concerns live here:

1. **Cleaning** — PoB's serialised item text leaks metadata into the
   parsed mod lists: ``"Item Level: 85"``, ``"Sockets: B-B-B-R"``,
   influence tags (``"Searing Exarch Item"``), the ``"Implicits: 2"``
   marker, ``"Fractured Item"``, etc. Those aren't real mods — feeding
   them to the Trade API would return zero results. :func:`clean_mods`
   strips them out so the rest of the planner can treat what remains
   as actual rolls.

2. **Pattern matching** — for each surviving mod line we want to recover
   ``(stat_id, numeric value)`` so we can build a
   :class:`poe1_pricing.StatFilter` and search for similar items on the
   GGG Trade API. The :data:`MOD_PATTERNS` table covers ~30 of the
   highest-value mods seen on rares: life, ES, suppression, resistances,
   +# to skill gems, gem tags, crit, cast/attack speed, movement speed.

   The stat IDs come from the public PoE community datasets (RePoE /
   awakened-poe-trade) and are stable across leagues. We deliberately
   don't ship every mod in the game — for a build planner we want to
   query on the **valuable** mods only; including a forgettable
   ``"+5 to Strength"`` would over-constrain the search and starve the
   percentile calculator of comparable listings.

The output is a list of :class:`StatFilter`. Callers (the planner)
combine those with the item's ``base_type`` into a
:class:`poe1_pricing.TradeQuery`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from poe1_pricing import StatFilter

from .models import PobItem

# ---------------------------------------------------------------------------
# Metadata filtering
# ---------------------------------------------------------------------------

# Lines emitted by PoB that aren't actual mods. We exclude them from
# the explicit/implicit pools before pattern matching. The match is
# case-insensitive and prefix-style: any line starting with one of these
# tokens is dropped.
_PREFIX_METADATA: frozenset[str] = frozenset(
    {
        "item level:",
        "level: ",
        "quality:",
        "quality (",
        "sockets:",
        "levelreq:",
        "implicits:",
        "rarity:",
        "unique id:",
        "shaper item",
        "elder item",
        "warlord item",
        "hunter item",
        "redeemer item",
        "crusader item",
        "searing exarch item",
        "eater of worlds item",
        "synthesised item",
        "fractured item",
        "corrupted",
        "split",
        "unidentified",
        "mirrored",
    }
)

# Anything wrapped in {…} at the start of a line is a PoB annotation,
# not a mod. Same for {…}{…} stacks.
_ANNOTATION_RE = re.compile(r"^\{[^}]*\}\s*")


def _is_metadata(line: str) -> bool:
    stripped = line.strip().casefold()
    if not stripped:
        return True
    return any(stripped.startswith(needle) for needle in _PREFIX_METADATA)


def _strip_annotations(line: str) -> str:
    """Remove leading PoB ``{…}`` annotation tags from a mod line.

    Leaves the actual mod text untouched. Used so a fractured / crafted
    mod still matches the same pattern as its non-annotated sibling.
    """

    out = line
    while True:
        m = _ANNOTATION_RE.match(out)
        if m is None:
            return out.strip()
        out = out[m.end() :]


def _clean(lines: tuple[str, ...]) -> tuple[str, ...]:
    """Two-pass filter: drop metadata lines, strip annotations, drop blanks.

    Order matters. ``_is_metadata`` runs against the *raw* line so it
    catches ``"Item Level: 85"``, ``"Searing Exarch Item"`` etc.
    ``_strip_annotations`` then peels ``{crafted}`` / ``{fractured}``
    off legitimate mods so pattern matching sees the bare stat text.
    A line that's *only* annotation (e.g. ``"{crafted}"`` alone) ends up
    empty after stripping and is dropped here.
    """

    out: list[str] = []
    for line in lines:
        if _is_metadata(line):
            continue
        cleaned = _strip_annotations(line)
        if cleaned:
            out.append(cleaned)
    return tuple(out)


def clean_mod_lines(lines: Iterable[str]) -> tuple[str, ...]:
    """Public string-input variant of :func:`_clean`.

    Used by routers / API endpoints that get raw mod text from the
    frontend (rather than from a parsed :class:`PobItem`) and need
    metadata-free, annotation-free lines before pattern matching.
    """

    return _clean(tuple(lines))


def clean_mods(item: PobItem) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(implicits, explicits)`` with PoB metadata stripped.

    Annotation tags like ``{crafted}`` / ``{fractured}`` are removed
    from the front of each mod line so pattern matching works on the
    raw stat text.
    """

    return _clean(item.implicits), _clean(item.explicits)


# ---------------------------------------------------------------------------
# Stat ID database — Trade API stat tokens for the valuable mods
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModPattern:
    """One entry in the rare-item stat database.

    ``regex`` matches the canonical PoB mod text (with values inlined).
    ``stat_id`` is the opaque GGG token; the planner substitutes the
    extracted value into a :class:`StatFilter` keyed by it.

    ``floor_ratio`` gives the lower bound to query for: 0.85 means
    "match listings with at least 85 % of the rolled value", which
    avoids over-fitting to a single roll while still surfacing
    comparable items.
    """

    regex: re.Pattern[str]
    stat_id: str
    label: str  # short human-readable for debugging / UI
    floor_ratio: float = 0.85


def _r(pattern: str) -> re.Pattern[str]:
    """Compile *pattern* with case-insensitive matching."""

    return re.compile(pattern, re.IGNORECASE)


# The patterns table. Order matters only for tie-breaking — we run all
# patterns against every line and aggregate. We capture **one** numeric
# group per pattern; the value extracted there becomes the StatFilter
# minimum (after the floor_ratio multiplier).
#
# Stat IDs are sourced from RePoE / awakened-poe-trade — the canonical
# community datasets that GGG mirrors at /api/trade/data/stats. They're
# stable across leagues for non-experimental mods; we pin only mods that
# have been in the game ≥3 leagues.
MOD_PATTERNS: tuple[ModPattern, ...] = (
    # --- Life & ES ---------------------------------------------------------
    ModPattern(
        _r(r"^\+(\d+) to maximum Life$"),
        "explicit.stat_3299347043",
        label="+# to maximum Life",
    ),
    ModPattern(
        _r(r"^(\d+)% increased maximum Life$"),
        "explicit.stat_983749596",
        label="#% increased maximum Life",
    ),
    ModPattern(
        _r(r"^\+(\d+) to maximum Energy Shield$"),
        "explicit.stat_3489782002",
        label="+# to maximum Energy Shield",
    ),
    ModPattern(
        _r(r"^(\d+)% increased maximum Energy Shield$"),
        "explicit.stat_2482852589",
        label="#% increased maximum Energy Shield",
    ),
    ModPattern(
        _r(r"^\+(\d+) to maximum Mana$"),
        "explicit.stat_1050105434",
        label="+# to maximum Mana",
    ),
    # --- Resistances --------------------------------------------------------
    ModPattern(
        _r(r"^\+(\d+)% to Fire Resistance$"),
        "explicit.stat_3372524247",
        label="+#% to Fire Resistance",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Cold Resistance$"),
        "explicit.stat_4220027924",
        label="+#% to Cold Resistance",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Lightning Resistance$"),
        "explicit.stat_1671376347",
        label="+#% to Lightning Resistance",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Chaos Resistance$"),
        "explicit.stat_2923486259",
        label="+#% to Chaos Resistance",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to all Elemental Resistances$"),
        "explicit.stat_2901986750",
        label="+#% to all Elemental Resistances",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Fire and Cold Resistances$"),
        "explicit.stat_3441501978",
        label="+#% to Fire and Cold Resistances",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Fire and Lightning Resistances$"),
        "explicit.stat_4277795662",
        label="+#% to Fire and Lightning Resistances",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Cold and Lightning Resistances$"),
        "explicit.stat_4277795662",
        label="+#% to Cold and Lightning Resistances",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Fire and Chaos Resistances$"),
        "explicit.stat_378817135",
        label="+#% to Fire and Chaos Resistances",
    ),
    # --- Suppression -------------------------------------------------------
    ModPattern(
        _r(r"^\+(\d+)% chance to Suppress Spell Damage$"),
        "explicit.stat_3015578834",
        label="+#% chance to Suppress Spell Damage",
    ),
    # --- Movement -----------------------------------------------------------
    ModPattern(
        _r(r"^(\d+)% increased Movement Speed$"),
        "explicit.stat_2250533757",
        label="#% increased Movement Speed",
    ),
    # --- Skill levels (the chase mods) ------------------------------------
    ModPattern(
        _r(r"^\+(\d+) to Level of Socketed Gems$"),
        "explicit.stat_2152491486",
        label="+# to Level of Socketed Gems",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Level of Socketed Spell Gems$"),
        "explicit.stat_4154259475",
        label="+# to Level of Socketed Spell Gems",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Level of Socketed Aura Gems$"),
        "explicit.stat_2452998583",
        label="+# to Level of Socketed Aura Gems",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Level of Socketed Bow Gems$"),
        "explicit.stat_2027269580",
        label="+# to Level of Socketed Bow Gems",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Level of Socketed Minion Gems$"),
        "explicit.stat_3604946673",
        label="+# to Level of Socketed Minion Gems",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Level of all (Cold|Fire|Lightning|Chaos|Physical) Spell Skill Gems$"),
        "explicit.stat_2974417149",  # cold-only ID — placeholder; per-element IDs differ
        label="+# to Level of all <element> Spell Skill Gems",
    ),
    # --- Spell offence ----------------------------------------------------
    ModPattern(
        _r(r"^(\d+)% increased Spell Damage$"),
        "explicit.stat_2974417149",
        label="#% increased Spell Damage",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Critical Strike Multiplier for Spells$"),
        "explicit.stat_737908626",
        label="+#% to Critical Strike Multiplier for Spells",
    ),
    ModPattern(
        _r(r"^(\d+)% increased Critical Strike Chance for Spells$"),
        "explicit.stat_737908626",  # similar prefix; placeholder
        label="#% increased Critical Strike Chance for Spells",
    ),
    ModPattern(
        _r(r"^(\d+)% increased Cast Speed$"),
        "explicit.stat_2891184298",
        label="#% increased Cast Speed",
    ),
    # --- Attack offence ---------------------------------------------------
    ModPattern(
        _r(r"^(\d+)% increased Attack Speed$"),
        "explicit.stat_210067635",
        label="#% increased Attack Speed",
    ),
    ModPattern(
        _r(r"^\+(\d+)% to Global Critical Strike Multiplier$"),
        "explicit.stat_3556824919",
        label="+#% to Global Critical Strike Multiplier",
    ),
    # --- Misc useful ------------------------------------------------------
    ModPattern(
        _r(r"^(\d+)% increased Stun and Block Recovery$"),
        "explicit.stat_2511217560",
        label="#% increased Stun and Block Recovery",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Strength$"),
        "explicit.stat_4080418644",
        label="+# to Strength",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Dexterity$"),
        "explicit.stat_3261801346",
        label="+# to Dexterity",
    ),
    ModPattern(
        _r(r"^\+(\d+) to Intelligence$"),
        "explicit.stat_328541901",
        label="+# to Intelligence",
    ),
    # --- Watcher's Eye (aura-conditional) ---------------------------------
    #
    # Watcher's Eye is a Prismatic Jewel unique that rolls 1-3 mods,
    # each gated by a specific aura the player has running. The mod
    # text always starts with "While affected by <Aura>, ...". The
    # stat ids below pin the highest-traded combos: cold/fire/lightning
    # damage conversion under Hatred/Anger/Wrath, ES recharge under
    # Discipline, crit under Precision, DoT multi under Malevolence,
    # etc. Coverage is intentionally partial — the cheap mods (e.g.
    # "while affected by clarity, mana regen") aren't worth pinning
    # because Watcher's Eyes priced on those alone are the cheapest
    # bucket and the planner is happy to ignore the variant.
    #
    # Stat ids verified against awakened-poe-trade's bundled
    # ``trade-stats.json`` snapshot. Floor ratio sits at 0.85 like the
    # rest of the rare-mod table — the actual rolled value matters
    # more for Trade matching than the relative quality.
    ModPattern(
        _r(r"^While affected by Hatred, (\d+)% of Physical Damage Converted to Cold Damage$"),
        "explicit.stat_2233437671",
        label="While affected by Hatred, #% Phys to Cold",
    ),
    ModPattern(
        _r(r"^While affected by Hatred, (\d+)% increased Cold Damage$"),
        "explicit.stat_3618888098",
        label="While affected by Hatred, #% increased Cold Damage",
    ),
    ModPattern(
        _r(r"^While affected by Hatred, Adds (\d+) to \d+ Cold Damage$"),
        "explicit.stat_2611224062",
        label="While affected by Hatred, Adds Cold Damage",
    ),
    ModPattern(
        _r(r"^While affected by Anger, (\d+)% of Physical Damage Converted to Fire Damage$"),
        "explicit.stat_4231842891",
        label="While affected by Anger, #% Phys to Fire",
    ),
    ModPattern(
        _r(r"^While affected by Anger, (\d+)% increased Fire Damage$"),
        "explicit.stat_3551025193",
        label="While affected by Anger, #% increased Fire Damage",
    ),
    ModPattern(
        _r(r"^While affected by Anger, Adds (\d+) to \d+ Fire Damage$"),
        "explicit.stat_2818854203",
        label="While affected by Anger, Adds Fire Damage",
    ),
    ModPattern(
        _r(r"^While affected by Wrath, (\d+)% of Physical Damage Converted to Lightning Damage$"),
        "explicit.stat_3683243800",
        label="While affected by Wrath, #% Phys to Lightning",
    ),
    ModPattern(
        _r(r"^While affected by Wrath, (\d+)% increased Lightning Damage$"),
        "explicit.stat_3848282610",
        label="While affected by Wrath, #% increased Lightning Damage",
    ),
    ModPattern(
        _r(r"^While affected by Wrath, Adds (\d+) to \d+ Lightning Damage$"),
        "explicit.stat_3759663284",
        label="While affected by Wrath, Adds Lightning Damage",
    ),
    ModPattern(
        _r(r"^While affected by Discipline, (\d+)% increased Energy Shield Recharge Rate$"),
        "explicit.stat_4267315121",
        label="While affected by Discipline, #% inc. ES Recharge Rate",
    ),
    ModPattern(
        _r(
            r"^While affected by Discipline, (\d+)% chance to Gain Onslaught for 4 seconds when Hit$"
        ),
        "explicit.stat_1474337958",
        label="While affected by Discipline, Onslaught on Hit",
    ),
    ModPattern(
        _r(
            r"^While affected by Discipline, (\d+)% increased Energy Shield from Equipped Body Armour$"
        ),
        "explicit.stat_4078194209",
        label="While affected by Discipline, #% inc. ES from Body",
    ),
    ModPattern(
        _r(r"^While affected by Precision, (\d+)% increased Critical Strike Chance$"),
        "explicit.stat_775081860",
        label="While affected by Precision, #% inc. Crit Chance",
    ),
    ModPattern(
        _r(r"^While affected by Precision, \+(\d+)% to Critical Strike Multiplier$"),
        "explicit.stat_3032420365",
        label="While affected by Precision, +#% Crit Multi",
    ),
    ModPattern(
        _r(r"^While affected by Malevolence, (\d+)% increased Damage Over Time$"),
        "explicit.stat_3759021413",
        label="While affected by Malevolence, #% inc. DoT",
    ),
    ModPattern(
        _r(r"^While affected by Malevolence, (\d+)% chance to Avoid Cold Damage from Hits$"),
        "explicit.stat_3163738488",
        label="While affected by Malevolence, % Avoid Cold",
    ),
    ModPattern(
        _r(r"^While affected by Determination, (\d+)% increased Armour$"),
        "explicit.stat_2618394336",
        label="While affected by Determination, #% increased Armour",
    ),
    ModPattern(
        _r(r"^While affected by Determination, (\d+)% additional Physical Damage Reduction$"),
        "explicit.stat_2734168507",
        label="While affected by Determination, #% Phys Damage Reduction",
    ),
    ModPattern(
        _r(r"^While affected by Grace, (\d+)% chance to Dodge Attack Hits$"),
        "explicit.stat_4181072906",
        label="While affected by Grace, % Dodge Attacks",
    ),
    ModPattern(
        _r(r"^While affected by Grace, \+(\d+) to maximum Energy Shield$"),
        "explicit.stat_3151397056",
        label="While affected by Grace, +# max ES",
    ),
    ModPattern(
        _r(r"^While affected by Vitality, (\d+)% of Damage Leeched as Life$"),
        "explicit.stat_3656301437",
        label="While affected by Vitality, #% Life Leech",
    ),
    ModPattern(
        _r(r"^While affected by Haste, (\d+)% increased Cooldown Recovery Rate$"),
        "explicit.stat_2784545195",
        label="While affected by Haste, #% inc. Cooldown Recovery",
    ),
    ModPattern(
        _r(r"^While affected by Haste, (\d+)% increased Attack and Cast Speed$"),
        "explicit.stat_1493091477",
        label="While affected by Haste, #% inc. Attack/Cast Speed",
    ),
    ModPattern(
        _r(r"^While affected by Pride, Nearby Enemies take (\d+)% increased Physical Damage$"),
        "explicit.stat_1714175687",
        label="While affected by Pride, #% inc. Phys Taken (enemies)",
    ),
    ModPattern(
        _r(r"^While affected by Zealotry, (\d+)% increased Critical Strike Chance for Spells$"),
        "explicit.stat_2814483053",
        label="While affected by Zealotry, #% inc. Spell Crit",
    ),
    ModPattern(
        _r(r"^While affected by Zealotry, Damaging Ailments deal damage (\d+)% faster$"),
        "explicit.stat_3743910227",
        label="While affected by Zealotry, #% faster Ailment damage",
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractedMod:
    """A successfully matched mod with its captured numeric value."""

    line: str
    stat_id: str
    value: float
    label: str


def extract_mods(lines: Iterable[str]) -> list[ExtractedMod]:
    """Run :data:`MOD_PATTERNS` against *lines*; return matched entries.

    Lines that don't match any pattern are silently dropped — they're
    either low-value mods we deliberately ignore or PoB metadata that
    snuck past :func:`clean_mods`. Multiple patterns matching the same
    line is fine: each match is returned independently so callers can
    decide how to deduplicate.
    """

    out: list[ExtractedMod] = []
    for line in lines:
        text = line.strip()
        for mp in MOD_PATTERNS:
            m = mp.regex.match(text)
            if m is None:
                continue
            try:
                value = float(m.group(1))
            except (IndexError, ValueError):
                continue
            out.append(
                ExtractedMod(
                    line=text,
                    stat_id=mp.stat_id,
                    value=value,
                    label=mp.label,
                )
            )
    return out


def valuable_stat_filters_from_mods(
    explicit_mods: Iterable[str],
    *,
    floor_ratio: float | None = None,
    max_filters: int = 6,
) -> list[StatFilter]:
    """String-input variant of :func:`valuable_stat_filters`.

    Same behaviour but accepts raw mod strings directly so callers
    holding a :class:`poe1_core.Item` (which carries
    :class:`ItemMod` objects, not :class:`PobItem`) can extract the
    text and pass it in without a round-trip through PoB models. The
    metadata cleaner runs unconditionally — passing already-clean
    strings is a no-op.
    """

    cleaned = _clean(tuple(explicit_mods))
    matched = extract_mods(cleaned)
    out: list[StatFilter] = []
    seen_ids: set[str] = set()
    for em in matched:
        if em.stat_id in seen_ids:
            continue
        ratio = floor_ratio if floor_ratio is not None else _floor_for(em.stat_id)
        floor = max(1.0, em.value * ratio)
        out.append(StatFilter(stat_id=em.stat_id, min=round(floor, 2)))
        seen_ids.add(em.stat_id)
        if len(out) >= max_filters:
            break
    return out


def valuable_stat_filters(
    item: PobItem,
    *,
    floor_ratio: float | None = None,
    max_filters: int = 6,
) -> list[StatFilter]:
    """Pick the most valuable mods on *item* and turn them into Trade
    :class:`StatFilter`s.

    The Trade API performs better with focused queries: too many AND
    filters and the result set drops to zero. We cap at ``max_filters``
    (default 6) — the highest-value mods are kept by virtue of
    :data:`MOD_PATTERNS`'s implicit priority (the table is roughly
    ordered by importance for life builds; callers needing different
    weighting can post-filter).

    Each filter's ``min`` is set to ``value * floor_ratio`` (clamped to
    1) so the search returns items whose roll on that mod is comparable
    or better. ``floor_ratio`` falls back to each pattern's per-mod
    default — usually 0.85.
    """

    return valuable_stat_filters_from_mods(
        item.explicits,
        floor_ratio=floor_ratio,
        max_filters=max_filters,
    )


def _floor_for(stat_id: str) -> float:
    """Look up the pattern's floor_ratio for a stat id (default 0.85)."""

    for mp in MOD_PATTERNS:
        if mp.stat_id == stat_id:
            return mp.floor_ratio
    return 0.85


__all__ = [
    "MOD_PATTERNS",
    "ExtractedMod",
    "ModPattern",
    "clean_mod_lines",
    "clean_mods",
    "extract_mods",
    "valuable_stat_filters",
    "valuable_stat_filters_from_mods",
]
