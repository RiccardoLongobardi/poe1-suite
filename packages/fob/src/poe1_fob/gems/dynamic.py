"""Step 18 — Dynamic gem progression derived from the user's PoB.

Replaces the hand-curated :data:`GEM_REGISTRY` for any build where we
have an actual :class:`PobSnapshot` to read from. The registry stays as
a fallback for the no-PoB case (e.g. when the user picks a template
from the Finder without pasting their own export).

Algorithm at a glance — per gem in the user's PoB, project six
``GemSpec`` snapshots that span the natural leveling curve from
campaign to high-investment endgame:

* **Stage 1 — Early Campaign** (≈ char lvl 30): level
  ``max(1, user_level - 12)``, quality 0. The user just acquired
  the gem; it hasn't had time to bake.
* **Stage 2 — Mid Campaign** (≈ lvl 55): level ``max(8, user_level - 8)``,
  quality 0.
* **Stage 3 — End Campaign** (≈ lvl 75): level ``max(16, user_level - 4)``,
  quality ``max(0, user_quality - 10)``.
* **Stage 4 — Early Mapping** (≈ lvl 85): level 20, quality 20.
* **Stage 5 — End Mapping** (≈ lvl 95): level ``min(21, user_level)``,
  quality 20. The 21/20 corrupt step.
* **Stage 6 — High Investment**: user's actual level + quality (incl.
  Awakened lvl 5 / Divergent corrupts, etc.).

Two cross-cutting rules layered on top of the level/quality math:

1. **Awakened normalisation** — early stages can't run Awakened
   support gems (they don't exist yet at lvl 30). For stages 1-3 we
   substitute the regular base gem ("Awakened Burning Damage" →
   "Burning Damage Support"); stage 4 emerges Awakened lvl 1, stage 5
   lvl 3, stage 6 the user's actual level. Same idea for Awakened
   active gems (rare but they exist).

2. **Trigger gems stay at their user-set level** — CWDT / Cast on
   Crit / Cast while Channelling break if you scale their level past
   the user's chosen breakpoint (CWDT 1 vs CWDT 20 trigger different
   damage thresholds). Detected by gem name; the level is pinned
   across all six stages.

The output uses the existing :class:`GemProgression` /
:class:`StageGemLinks` / :class:`GemLink` / :class:`GemSpec` models so
the encoder + UI code already know how to render it.
"""

from __future__ import annotations

from typing import Final

from poe1_core.models.enums import ItemSlot

from ..pob.models import PobGem, PobSkillGroup, PobSnapshot
from .models import GemLink, GemProgression, GemSpec, StageGemLinks

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

_STAGE_KEYS: Final[tuple[str, ...]] = (
    "early_campaign",
    "mid_campaign",
    "end_campaign",
    "early_mapping",
    "end_mapping",
    "high_investment",
)

# ---------------------------------------------------------------------------
# Gem classification (deterministic — no per-build hand curation)
# ---------------------------------------------------------------------------

_AWAKENED_PREFIX = "Awakened "
_VAAL_PREFIX = "Vaal "

# Trigger gems whose level affects mechanical thresholds (e.g. CWDT
# trigger damage). Keep their level fixed to whatever the user chose,
# across all six stages. Names lowercased for casefold-comparison.
_TRIGGER_GEMS: Final[frozenset[str]] = frozenset(
    {
        "cast when damage taken support",
        "cast on critical strike support",
        "cast while channelling support",
        "cast on death support",
    }
)

# Active gems that the engine should NOT downscale below level 1 + the
# user's quality (they're auras / utility — the level just bumps the
# numeric reservation a bit, not the mechanic).
_AURA_LIKE: Final[frozenset[str]] = frozenset(
    {
        "clarity",
        "vitality",
        "purity of fire",
        "purity of ice",
        "purity of lightning",
        "purity of elements",
        "determination",
        "discipline",
        "grace",
        "haste",
        "hatred",
        "anger",
        "wrath",
        "malevolence",
        "zealotry",
        "pride",
        "envy",
        "skitterbots",
        "herald of agony",
        "herald of ash",
        "herald of ice",
        "herald of thunder",
        "herald of purity",
    }
)

# ---------------------------------------------------------------------------
# Slot mapping: PoB's slot string → our ItemSlot enum
# ---------------------------------------------------------------------------

_SLOT_MAP: Final[dict[str, ItemSlot]] = {
    "Body Armour": ItemSlot.BODY_ARMOUR,
    "Helmet": ItemSlot.HELMET,
    "Gloves": ItemSlot.GLOVES,
    "Boots": ItemSlot.BOOTS,
    "Belt": ItemSlot.BELT,
    "Amulet": ItemSlot.AMULET,
    "Ring 1": ItemSlot.RING,
    "Ring 2": ItemSlot.RING,
    "Ring": ItemSlot.RING,
    "Weapon 1": ItemSlot.WEAPON_MAIN,
    "Weapon 2": ItemSlot.WEAPON_OFFHAND,
    "Weapon 1 Swap": ItemSlot.WEAPON_MAIN,
    "Weapon 2 Swap": ItemSlot.WEAPON_OFFHAND,
}


def _map_slot(pob_slot: str | None) -> ItemSlot:
    """Convert PoB's ``<Skill slot>`` string to our ``ItemSlot`` enum.

    Falls back to BODY_ARMOUR (the most common main-skill slot) when
    PoB didn't tag the group, so the export still has a valid slot.
    """

    if not pob_slot:
        return ItemSlot.BODY_ARMOUR
    return _SLOT_MAP.get(pob_slot, ItemSlot.BODY_ARMOUR)


# ---------------------------------------------------------------------------
# Awakened / Vaal helpers
# ---------------------------------------------------------------------------


def _is_awakened(name: str) -> bool:
    return name.startswith(_AWAKENED_PREFIX)


def _is_vaal(name: str) -> bool:
    return name.startswith(_VAAL_PREFIX)


def _strip_awakened(name: str) -> str:
    """Return the non-Awakened equivalent for an Awakened gem name.

    "Awakened Burning Damage" → "Burning Damage Support"
    "Awakened Empower Support" → "Empower Support" (already has "Support")
    """

    base = name.removeprefix(_AWAKENED_PREFIX)
    if not base.endswith(" Support") and "Support" not in base:
        # Awakened *active* gems are rare; play it safe and don't append.
        return base
    return base


def _strip_vaal(name: str) -> str:
    """Return the non-Vaal equivalent ("Vaal Righteous Fire" → "Righteous Fire")."""

    return name.removeprefix(_VAAL_PREFIX)


def _is_trigger(name: str) -> bool:
    return name.casefold() in _TRIGGER_GEMS


def _is_aura_like(name: str) -> bool:
    return name.casefold().removeprefix(_VAAL_PREFIX.casefold()) in _AURA_LIKE


# ---------------------------------------------------------------------------
# Per-gem stage projection
# ---------------------------------------------------------------------------


def _project_level_quality(
    user_level: int,
    user_quality: int,
    stage_index: int,
) -> tuple[int, int]:
    """Return ``(level, quality)`` for a non-special gem at *stage_index* (0-5)."""

    if stage_index == 0:  # early_campaign
        return max(1, user_level - 12), 0
    if stage_index == 1:  # mid_campaign
        return max(8, user_level - 8), 0
    if stage_index == 2:  # end_campaign
        return max(16, user_level - 4), max(0, user_quality - 10)
    if stage_index == 3:  # early_mapping
        return min(20, user_level), min(20, max(0, user_quality))
    if stage_index == 4:  # end_mapping
        return min(21, user_level), min(20, max(0, user_quality))
    return user_level, user_quality  # high_investment — user's actual


def _awakened_stage_level(user_level: int, stage_index: int) -> int:
    """Awakened progression: 0 / 0 / 0 / 1 / 3 / user."""

    if stage_index < 3:
        # Substituted with the base gem at lvl from _project_level_quality.
        # Caller handles the substitution; this branch is unreachable in
        # practice but kept for clarity.
        return 1
    if stage_index == 3:
        return min(1, user_level)
    if stage_index == 4:
        return min(3, user_level)
    return user_level


def _project_gem(
    user_gem: PobGem,
    stage_index: int,
) -> GemSpec | None:
    """Project one user gem to its representation at *stage_index*.

    Returns None when the gem should be omitted at this stage (e.g.
    Vaal gem at early_campaign where the Vaal version doesn't exist).
    """

    name = user_gem.name
    user_level = user_gem.level
    user_quality = user_gem.quality

    # Stage 6: always return the user's actual values.
    if stage_index == 5:
        return GemSpec(
            name=name,
            level=user_level,
            quality=user_quality,
            is_support=user_gem.is_support,
        )

    # Trigger gems: pin to user's level + quality across all stages.
    # Their mechanical threshold breaks if we downscale.
    if _is_trigger(name):
        return GemSpec(
            name=name,
            level=user_level,
            quality=user_quality,
            is_support=user_gem.is_support,
        )

    # Awakened gems: substitute the regular base name for stages 1-3.
    # The base gem's "natural" max is level 20 / quality 20, so we
    # project against that — the user's Awakened lvl 1-5 isn't a
    # meaningful starting point for the substitution.
    if _is_awakened(name):
        if stage_index < 3:
            base_name = _strip_awakened(name)
            level, quality = _project_level_quality(20, 20, stage_index)
            return GemSpec(
                name=base_name,
                level=min(20, max(1, level)),
                quality=quality,
                is_support=user_gem.is_support,
            )
        # Stages 4-5: Awakened at low level / partial quality.
        return GemSpec(
            name=name,
            level=_awakened_stage_level(user_level, stage_index),
            quality=0 if stage_index == 3 else min(20, user_quality),
            is_support=user_gem.is_support,
        )

    # Vaal gems: substitute the non-Vaal version for stages 1-2
    # (the Vaal upgrade is a corruption applied late in the build).
    if _is_vaal(name) and stage_index < 2:
        base_name = _strip_vaal(name)
        level, quality = _project_level_quality(user_level, user_quality, stage_index)
        return GemSpec(
            name=base_name,
            level=level,
            quality=quality,
            is_support=user_gem.is_support,
        )

    # Aura-like gems: don't downscale level past the user's chosen — the
    # mechanic is the buff, not the numeric scale.
    if _is_aura_like(name) and stage_index < 3:
        # Modest downscale: 50%, 70%, 85% of user's level.
        ratios = (0.5, 0.7, 0.85)
        level = max(1, int(user_level * ratios[stage_index]))
        return GemSpec(
            name=name,
            level=level,
            quality=0,
            is_support=user_gem.is_support,
        )

    # Default path: project the level/quality.
    level, quality = _project_level_quality(user_level, user_quality, stage_index)
    return GemSpec(
        name=name,
        level=level,
        quality=quality,
        is_support=user_gem.is_support,
    )


# ---------------------------------------------------------------------------
# Group → GemLink projection
# ---------------------------------------------------------------------------


def _project_group(
    group: PobSkillGroup,
    stage_index: int,
) -> GemLink | None:
    """Project a user skill group to a ``GemLink`` for *stage_index*.

    Returns None when the projected group ends up empty (all gems
    omitted at this stage — rare, mostly Vaal-only weird setups).
    """

    projected: list[GemSpec] = []
    for user_gem in group.gems:
        if not user_gem.enabled:
            continue
        proj = _project_gem(user_gem, stage_index)
        if proj is not None:
            projected.append(proj)
    if not projected:
        return None
    # Clamp to 6 — PoB lets users analyse "what-if" groups with 7+ gems,
    # but PoE items have at most 6 sockets so the model validator
    # rejects anything larger. Keep the first 6 (the user-ordered ones
    # PoB shows by default).
    projected = projected[:6]
    slot = _map_slot(group.slot)
    return GemLink(
        slot=slot,
        sockets=len(projected),
        gems=tuple(projected),
        notes=group.label or "",
    )


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def _stage_notes(stage_index: int, is_main_present: bool) -> str:
    """One-line stage rationale shown in the UI ``StageCard``."""

    base = {
        0: "Atto 1-4 leveling — gems acquisite via quest, livello basso.",
        1: "Atto 5-7 — primo lab fatto, supports principali socketati.",
        2: "Atto 8-10 + Kitava — gems prossime a level 20.",
        3: "T1-T8 mapping — gems 20/20, Vaal gems disponibili.",
        4: "T14-T16 endgame — primi Awakened gems socketati.",
        5: "Min-max — Awakened lvl 5, 21/20 corrupted, alt quality.",
    }.get(stage_index, "")
    if not is_main_present:
        base = (base + " Main skill non rilevato nel PoB.").strip()
    return base


def derive_gem_progression(
    snapshot: PobSnapshot,
    *,
    target_name: str = "derived",
) -> GemProgression | None:
    """Synthesise a 6-stage gem progression from a user PoB snapshot.

    Returns None when the snapshot carries no usable skill groups
    (parser failed, or the build is an aurabot / empty placeholder).
    """

    groups = [g for g in snapshot.skills if g.enabled and g.gems]
    if not groups:
        return None

    is_main_present = any(g.is_main for g in groups)
    stages: list[StageGemLinks] = []
    for idx, key in enumerate(_STAGE_KEYS):
        links: list[GemLink] = []
        for group in groups:
            link = _project_group(group, idx)
            if link is not None:
                links.append(link)
        if not links:
            # Defensive: skip empty stages rather than emit invalid input
            # to the StageGemLinks validator (min_length=1 on links).
            continue
        stages.append(
            StageGemLinks(
                stage_key=key,
                links=tuple(links),
                notes=_stage_notes(idx, is_main_present),
            )
        )
    if not stages:
        return None
    return GemProgression(target_name=target_name, stages=tuple(stages))


__all__ = ["derive_gem_progression"]
