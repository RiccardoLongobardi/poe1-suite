"""Step 17 — Dynamic gear progression derived from the user's PoB.

Replaces the hand-curated :data:`GEAR_REGISTRY` for any build where we
have an actual :class:`PobSnapshot` to read from. The registry stays as
a fallback for the no-PoB case.

Algorithm:

1. **Tier-classify** every item in ``snapshot.items_by_slot``:

   * ``mirror`` — rare with 4+ T1 mods (Mageblood-tier replacement craft).
   * ``mageblood`` — unique with chaos-equivalent > 100 div.
   * ``high``     — unique 20-100 div.
   * ``mid``      — unique 5-20 div.
   * ``cheap``    — unique < 5 div.
   * ``leveling`` — unique < 1 div *or* one of the canonical leveling
     uniques (Tabula Rasa, Goldrim, Wanderlust, …).
   * ``cluster``  — Large/Medium/Small Cluster Jewel.
   * ``rare_craft`` — anything else (non-unique non-cluster).

2. **Stage budget thresholds** (divines):

   | Stage              | Max-tier kept       |
   |--------------------|---------------------|
   | early_campaign     | leveling            |
   | mid_campaign       | cheap               |
   | end_campaign       | mid                 |
   | early_mapping      | high                |
   | end_mapping        | mageblood / mirror  |
   | high_investment    | (no cap)            |

3. **Per stage, per slot**:

   * If the user's item fits the stage's tier ceiling → keep it.
   * Otherwise → substitute with a slot-appropriate placeholder:
     - Stage 1-2 prefer the canonical leveling unique for the slot
       (Goldrim → helm, Wanderlust → boots, Tabula → body, …).
     - Stage 3-5 emit a ``rare_craft`` placeholder with the canonical
       base type from the vendored :mod:`poe1_fob.gear.base_items`
       catalogue.

4. **Pricing is optional**. When the caller provides a
   ``prices: dict[str, float]`` mapping ``item_name → divine_value``,
   the tier classifier uses it for unique items. Without it, we fall
   back to a deterministic name-signature heuristic that covers the
   ~30 most common expensive uniques. Pricing is async / network-
   bound; pre-fetching it in the router lets ``derive_gear_progression``
   stay pure & sync (no HTTP from the encode path).
"""

from __future__ import annotations

from typing import Final, Literal

from poe1_core.models.enums import ItemRarity, ItemSlot

from ..pob.models import PobItem, PobSnapshot
from .models import GearKind, GearProgression, StageGearSet, StageGearSlot

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

Tier = Literal[
    "mirror",
    "mageblood",
    "high",
    "mid",
    "cheap",
    "leveling",
    "cluster",
    "rare_craft",
    "skip",
]

# Heuristic fallback tiers when no pricing data is available. These
# names are stable across leagues — they're the famous "always
# expensive" uniques and the famous leveling uniques. A new league
# can shift prices but rarely flips a Mageblood into the leveling
# bucket.
_KNOWN_MAGEBLOOD_TIER: Final[frozenset[str]] = frozenset(
    {
        "Mageblood",
        "Headhunter",
        "The Squire",
        "Original Sin",
        "Forbidden Flame",
        "Forbidden Flesh",
    }
)
_KNOWN_HIGH_TIER: Final[frozenset[str]] = frozenset(
    {
        "Ashes of the Stars",
        "Crown of the Tyrant",
        "Watcher's Eye",
        "Impossible Escape",
        "Brass Dome",
        "Aegis Aurora",
        "Sublime Vision",
        "The Saviour",
        "Crystallised Omniscience",
        "Skin of the Lords",
        "Doryani's Prototype",
        "Loreweave",
    }
)
_KNOWN_MID_TIER: Final[frozenset[str]] = frozenset(
    {
        "Kaom's Heart",
        "Bottled Faith",
        "Rise of the Phoenix",
        "Cospri's Malice",
        "Cospri's Will",
        "Mjolner",
        "Soul Mantle",
        "Cyclopean Coil",
        "Replica Conqueror's Efficiency",
        "Shavronne's Wrappings",
        "Hyrri's Ire",
        "Cloak of Flame",
    }
)
_KNOWN_LEVELING_UNIQUES: Final[frozenset[str]] = frozenset(
    {
        "Goldrim",
        "Wanderlust",
        "Tabula Rasa",
        "Lochtonial Caress",
        "Karui Ward",
        "Meginord's Girdle",
        "Springleaf",
        "Brightbeak",
        "Maligaro's Virtuosity",
        "Praxis",
        "Atziri's Foible",
        "Astramentis",
        "Sin Trek",
        "Veil of the Night",
        "The Pariah",
        "Bramblejack",
    }
)

# Stage budget ceilings in divines. None on stage 6 = no cap.
_STAGE_BUDGETS_DIV: Final[dict[str, float | None]] = {
    "early_campaign": 0.5,
    "mid_campaign": 2.0,
    "end_campaign": 10.0,
    "early_mapping": 50.0,
    "end_mapping": 200.0,
    "high_investment": None,
}

_STAGE_KEYS: Final[tuple[str, ...]] = (
    "early_campaign",
    "mid_campaign",
    "end_campaign",
    "early_mapping",
    "end_mapping",
    "high_investment",
)

# Tier ordering: lower numeric = cheaper. Used to compare item tier
# against the stage's ceiling.
_TIER_RANK: Final[dict[Tier, int]] = {
    "leveling": 0,
    "cheap": 1,
    "mid": 2,
    "rare_craft": 3,  # rare crafts sit between mid and high in practice
    "high": 4,
    "cluster": 5,  # cluster jewels always endgame
    "mageblood": 6,
    "mirror": 7,
    "skip": -1,
}

_STAGE_TIER_CEILING: Final[dict[str, Tier]] = {
    "early_campaign": "leveling",
    "mid_campaign": "cheap",
    "end_campaign": "mid",
    "early_mapping": "high",
    "end_mapping": "mirror",  # full unique + rare endgame allowed
    "high_investment": "mirror",
}


# ---------------------------------------------------------------------------
# Canonical leveling-unique placeholders per slot
# ---------------------------------------------------------------------------

# Stage 1-2 substitutions: well-known cheap uniques per slot. Stage 3+
# substitutions use generic rare-craft placeholders pulled from the
# base_items catalogue (so they pick a real base type).
_LEVELING_PLACEHOLDER: Final[dict[ItemSlot, tuple[str, str]]] = {
    # (item_name, notes)
    ItemSlot.HELMET: ("Goldrim", "Leveling helm: +35-40% all elemental resistances."),
    ItemSlot.BODY_ARMOUR: (
        "Tabula Rasa",
        "Leveling 6L (~1 chaos): zero life but every link in atto.",
    ),
    ItemSlot.GLOVES: (
        "Lochtonial Caress",
        "Leveling gloves: random charge on hit + ele res (~1 alch).",
    ),
    ItemSlot.BOOTS: (
        "Wanderlust",
        "Leveling boots: movement speed + cannot be frozen (~1 alch).",
    ),
    ItemSlot.BELT: (
        "Meginord's Girdle",
        "Leveling belt: +50 strength + 20% increased life (~1 alch).",
    ),
    ItemSlot.AMULET: (
        "Karui Ward",
        "Leveling amulet: +20-30 dex/str/int + life (~1 chaos).",
    ),
    ItemSlot.RING: ("Praxis", "Leveling ring: mana cost reduction + life regen + life."),
    ItemSlot.WEAPON_MAIN: (
        "Brightbeak",
        "Leveling weapon: +50% increased attack speed (~1 chaos).",
    ),
    ItemSlot.WEAPON_OFFHAND: (
        "Springleaf",
        "Leveling shield: 50%+ life regen low-life (~1 alch).",
    ),
}


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------


def _is_cluster_jewel(item: PobItem) -> bool:
    """Cluster jewel detection via base type name (works without pricing)."""

    base = (item.base_type or "").lower()
    return base in {
        "large cluster jewel",
        "medium cluster jewel",
        "small cluster jewel",
    }


def _classify_unique(item: PobItem, prices: dict[str, float] | None) -> Tier:
    """Tier a unique by price (if known) or name-signature fallback."""

    name = item.name or ""
    # Price-driven path (preferred).
    if prices is not None and name in prices:
        div = prices[name]
        if div >= 100:
            return "mageblood"
        if div >= 20:
            return "high"
        if div >= 5:
            return "mid"
        if div >= 1:
            return "cheap"
        return "leveling"

    # Heuristic fallback by stable name lists.
    if name in _KNOWN_MAGEBLOOD_TIER:
        return "mageblood"
    if name in _KNOWN_HIGH_TIER:
        return "high"
    if name in _KNOWN_MID_TIER:
        return "mid"
    if name in _KNOWN_LEVELING_UNIQUES:
        return "leveling"
    # Unknown uniques default to "mid" — conservative, keeps them in
    # the build from stage 3 onward.
    return "mid"


def classify_item(item: PobItem, prices: dict[str, float] | None = None) -> Tier:
    """Return the tier bucket *item* belongs to.

    ``prices`` is an optional ``name → divine_value`` map; when set, the
    unique classifier prefers it over the name-signature heuristic.
    """

    if _is_cluster_jewel(item):
        return "cluster"
    if item.rarity == ItemRarity.UNIQUE:
        return _classify_unique(item, prices)
    return "rare_craft"


def _fits_stage_budget(item_tier: Tier, stage_key: str) -> bool:
    """True when *item_tier* is allowed at *stage_key*'s budget."""

    ceiling = _STAGE_TIER_CEILING.get(stage_key, "mirror")
    return _TIER_RANK[item_tier] <= _TIER_RANK[ceiling]


# ---------------------------------------------------------------------------
# Slot substitution picker
# ---------------------------------------------------------------------------


def _substitution_for_slot(slot: ItemSlot, stage_key: str) -> StageGearSlot | None:
    """Return a placeholder for *slot* at *stage_key* when the user's item is over budget.

    Stage 1-2 use canonical leveling uniques where we have one; otherwise
    Stage 3+ uses a rare-craft placeholder describing the base type and
    typical life + resistance roll the player should chase.
    """

    if stage_key in ("early_campaign", "mid_campaign"):
        # Prefer a known leveling unique for the slot.
        placeholder = _LEVELING_PLACEHOLDER.get(slot)
        if placeholder is not None:
            name, notes = placeholder
            return StageGearSlot(
                slot=slot,
                item_name=name,
                kind="leveling",
                notes=notes,
            )
    # Stage 3-6 default: rare craft suggestion.
    rare_text = _rare_craft_description(slot)
    if rare_text is None:
        return None
    item_name, notes = rare_text
    return StageGearSlot(
        slot=slot,
        item_name=item_name,
        kind="rare_craft",
        notes=notes,
    )


def _rare_craft_description(slot: ItemSlot) -> tuple[str, str] | None:
    """Generic "rare X with mods" copy per slot. Italian, terse."""

    return {
        ItemSlot.HELMET: (
            "rare helmet (life + 2 res)",
            "Rare craftato: T1 life + 2 resistenze. Eldritch implicit suppression in mapping.",
        ),
        ItemSlot.BODY_ARMOUR: (
            "rare body 6L (life + 2 res)",
            "Rare 6L craftato: T1 life + 2 resistenze. Awakener Orb per gli endgame craft.",
        ),
        ItemSlot.GLOVES: (
            "rare gloves (life + 2 res + suppression)",
            "Rare gloves: T1 life + 2 res + Eldritch suppression in mapping.",
        ),
        ItemSlot.BOOTS: (
            "rare boots (life + 30% MS)",
            "Rare boots: 30%+ movement speed + T1 life + 1 res.",
        ),
        ItemSlot.BELT: (
            "Stygian Vise rare (life + 2 res)",
            "Stygian Vise rare: T1 life + 2 res + flat life. Abyss jewel inside.",
        ),
        ItemSlot.AMULET: (
            "rare amulet (life + +1 spell skill)",
            "Rare amulet: +1 to all spell skill gems o +1 to fire spell skill + life + res.",
        ),
        ItemSlot.RING: (
            "rare ring (life + 3 res)",
            "Rare ring: T1 life + 3 resistenze + chaos res / accuracy / flat damage.",
        ),
        ItemSlot.WEAPON_MAIN: (
            "rare weapon (+1 to socketed gems)",
            "Rare wand/sceptre/staff: +1 to all spell skills + cast speed + spell damage.",
        ),
        ItemSlot.WEAPON_OFFHAND: (
            "rare shield (life + res)",
            "Rare shield: T1 life + 2 res + chance to block / spell suppression.",
        ),
        ItemSlot.QUIVER: (
            "rare quiver (life + crit)",
            "Rare quiver: T1 life + critical strike multi + flat damage.",
        ),
        ItemSlot.FLASK: (
            "utility flask (suffix anti-curse / freeze)",
            "Flask con suffisso 'of Heat' o 'of Warding' per immunità freeze/curse.",
        ),
        ItemSlot.JEWEL: (
            "rare jewel (life + crit)",
            "Crimson/Cobalt Jewel: T1 life + crit multi su skill / damage flat.",
        ),
    }.get(slot)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def derive_gear_progression(
    snapshot: PobSnapshot,
    *,
    target_name: str = "derived",
    prices: dict[str, float] | None = None,
) -> GearProgression | None:
    """Synthesise a 6-stage gear progression from a user PoB snapshot.

    Returns None when the snapshot carries no usable items (empty PoB
    or parser failure).
    """

    if not snapshot.items_by_slot:
        return None

    # Pre-classify every user item once; the per-stage loop just decides
    # whether to keep or substitute.
    user_items: dict[ItemSlot, tuple[PobItem, Tier]] = {}
    for slot, item in snapshot.items_by_slot.items():
        user_items[slot] = (item, classify_item(item, prices))

    stages: list[StageGearSet] = []
    for stage_key in _STAGE_KEYS:
        slot_specs: list[StageGearSlot] = []
        for slot, (item, tier) in user_items.items():
            if _fits_stage_budget(tier, stage_key):
                slot_specs.append(
                    StageGearSlot(
                        slot=slot,
                        item_name=_display_name(item),
                        kind=_kind_for_tier(tier),
                        notes=_keep_note(item, tier),
                    )
                )
            else:
                sub = _substitution_for_slot(slot, stage_key)
                if sub is not None:
                    slot_specs.append(sub)

        if not slot_specs:
            continue

        stages.append(
            StageGearSet(
                stage_key=stage_key,
                slots=tuple(slot_specs),
                overall_notes=_stage_overall_note(stage_key),
            )
        )

    if not stages:
        return None
    return GearProgression(target_name=target_name, stages=tuple(stages))


def _display_name(item: PobItem) -> str:
    """Best-effort label: unique name, or rare/magic base type."""

    if item.name and item.rarity == ItemRarity.UNIQUE:
        return item.name
    if item.name:
        return item.name
    return item.base_type or "Unknown item"


def _kind_for_tier(tier: Tier) -> GearKind:
    if tier in ("mageblood", "high", "mid", "cheap", "leveling"):
        return "unique"
    if tier == "cluster":
        return "unique"
    if tier == "rare_craft":
        return "rare_craft"
    if tier == "mirror":
        return "rare_craft"
    return "leveling"


def _keep_note(item: PobItem, tier: Tier) -> str:
    base = item.base_type or "?"
    if tier in ("mageblood", "high"):
        return f"{base} — endgame tier (~{tier})."
    if tier == "cluster":
        return f"{base} — cluster jewel, alloca i notable nello stage 6."
    if tier == "rare_craft":
        return f"{base} — rare craftato dall'utente."
    return f"{base}"


def _stage_overall_note(stage_key: str) -> str:
    notes = {
        "early_campaign": ("Atto 1-4: leveling uniques + Tabula 6L. Niente di costoso."),
        "mid_campaign": (
            "Atto 5-7: ascendancy 1, unique cheap, Brightbeak/Springleaf se applicabile."
        ),
        "end_campaign": ("Atto 8-10 + Kitava: rare base craftati + primi mid-unique."),
        "early_mapping": ("T1-T8: high-unique entry, Kaom's/Loreweave/Bottled Faith level."),
        "end_mapping": ("T14-T16: endgame rare custom-craft + Mageblood-tier optional."),
        "high_investment": ("Uber pinnacle: tutta la build dell'utente, niente sostituzioni."),
    }
    return notes.get(stage_key, "")


__all__ = [
    "Tier",
    "classify_item",
    "derive_gear_progression",
]
