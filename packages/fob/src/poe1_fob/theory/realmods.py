"""Real explicit-mod resolution for the Theorycrafter (Step 47).

Replaces the invented `_AFFIX_VALUES` table with real PoE mod tiers from
``packages/fob/data/mods/mods_3_28.json`` (vendored by
``scripts/extract_mods.py``). Given a recommended affix stem, a gear
base's tags and a budget tier, :func:`real_affix_line` returns the real
mod text at the best tier that can actually roll on that item — e.g.
``"+189 to maximum Life"`` (real T1 max) rather than a made-up number.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .models import BudgetTier

_MODS_PATH = Path(__file__).parent.parent.parent.parent / "data" / "mods" / "mods_3_28.json"

# Our recommendation stems (as emitted by `_stat_priorities`) → real PoE
# stat id(s), in preference order. Resolved from RePoE stat_translations
# (probe 2026-05-22). A stem can map to several candidate stats: e.g. ES
# is a flat mod on jewellery (`base_maximum_energy_shield`) but a *%
# increased* mod on armour (`local_energy_shield_+%`); `real_affix_line`
# picks whichever can actually roll on the slot.
_STEM_TO_STAT: dict[str, tuple[str, ...]] = {
    "to maximum Life": ("base_maximum_life",),
    "to maximum Energy Shield": ("base_maximum_energy_shield", "local_energy_shield_+%"),
    "to maximum Mana": ("base_maximum_mana",),
    "to Mana": ("base_maximum_mana",),
    "to Fire Resistance": ("base_fire_damage_resistance_%",),
    "to Cold Resistance": ("base_cold_damage_resistance_%",),
    "to Lightning Resistance": ("base_lightning_damage_resistance_%",),
    "to all Attributes": ("additional_all_attributes",),
    "increased Cast Speed": ("base_cast_speed_+%",),
    "increased Attack Speed": ("attack_speed_+%", "local_attack_speed_+%"),
    "increased Spell Damage": ("spell_damage_+%",),
    "increased Physical Damage": ("local_physical_damage_+%",),
    "Critical Strike Multiplier": ("base_critical_strike_multiplier_+",),
    "critical strike": ("local_critical_strike_chance_+%",),
    "Accuracy": ("accuracy_rating", "local_accuracy_rating"),
    "Movement Speed": ("base_movement_velocity_+%",),
    "Chance to Block": ("local_additional_block_chance_%",),
    "increased Flask Life Recovery": ("flask_life_recovery_rate_+%",),
    # Step 61 — DoT multipliers (damage-over-time builds).
    "Damage over Time Multiplier": ("dot_multiplier_+",),
    "Chaos Damage over Time Multiplier": ("chaos_dot_multiplier_+",),
    "Cold Damage over Time Multiplier": ("cold_dot_multiplier_+",),
    "Fire Damage over Time Multiplier": ("fire_dot_multiplier_+",),
    # Step 69 — body-armour gem-level influence affixes (mirror-tier). The
    # primary 6L is socketed in the Body Armour, so "+1 to Level of Socketed
    # Skill Gems" raises the main skill's level and "+1 to Level of Socketed
    # Support Gems" raises every support — the classic Shaper+Elder
    # (Awakener's Orb) body. Real RePoE affixes; PoB applies them.
    "to Level of Socketed Skill Gems": ("local_socketed_active_skill_gem_level_+",),
    "to Level of Socketed Support Gems": ("local_socketed_support_gem_level_+",),
}

# Step 69: the gem-level body affixes only spawn via *influence* spawn-weight
# tags (Shaper / Crusader for the skill-gem mod, Elder / Redeemer for the
# support-gem mod), never on a bare base. A mirror-tier body IS influenced, so
# when resolving these stems we augment the base's tags with the influence
# tags that carry them — honest (the build buys/crafts an influenced body),
# not invented.
_INFLUENCE_STEMS: frozenset[str] = frozenset(
    {"to Level of Socketed Skill Gems", "to Level of Socketed Support Gems"}
)
_BODY_INFLUENCE_TAGS: frozenset[str] = frozenset(
    {
        "body_armour_shaper",
        "body_armour_adjudicator",  # Crusader (skill-gem mod)
        "body_armour_elder",
        "body_armour_eyrie",  # Redeemer (support-gem mod)
    }
)

# Render templates for stat ids whose translation didn't survive the
# extraction (conditional / multi-line translations).
_FALLBACK_RENDER: dict[str, dict[str, object]] = {
    "local_physical_damage_+%": {"string": "{0}% increased Physical Damage", "plus": False},
}

# Budget tier → max item level we'll consider when picking a mod tier.
_BUDGET_ILVL: dict[BudgetTier, int] = {"starter": 50, "mid": 73, "endgame": 86}


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not _MODS_PATH.exists():  # pragma: no cover - deployment guard
        return {}, {}, {}
    raw = json.loads(_MODS_PATH.read_text(encoding="utf-8"))
    return raw.get("render", {}), raw.get("tiers", {}), raw.get("added", {})


# "Adds # to # Damage" stems → candidate added-damage groups (tried in
# order; the first that can roll on the slot wins). Weapon-local + spell
# variants for the weapon, attack variants for jewellery/gloves.
_STEM_TO_ADDED: dict[str, tuple[str, ...]] = {
    "Adds Physical Damage": ("local_physical", "attack_physical"),
    "Adds Fire Damage": ("local_fire", "attack_fire"),
    "Adds Cold Damage": ("local_cold", "attack_cold"),
    "Adds Lightning Damage": ("local_lightning", "attack_lightning"),
    "Adds Chaos Damage": ("local_chaos", "attack_chaos"),
    "Adds Fire Damage to Spells": ("spell_fire",),
    "Adds Cold Damage to Spells": ("spell_cold",),
    "Adds Lightning Damage to Spells": ("spell_lightning",),
    "Adds Chaos Damage to Spells": ("spell_chaos",),
}


def _added_line(stem: str, item_tags: frozenset[str], cap: int) -> str | None:
    keys = _STEM_TO_ADDED.get(stem)
    if not keys:
        return None
    _, _, added = _load()
    for key in keys:
        group = added.get(key)
        if not group:
            continue
        cands = [
            t
            for t in group.get("tiers", [])
            if isinstance(t.get("ilvl"), int)
            and t["ilvl"] <= cap
            and t.get("vmax") is not None
            and can_spawn(t.get("weights", []), item_tags)
        ]
        if cands:
            best = max(cands, key=lambda t: (t["ilvl"], t["vmax"]))
            string = str(group.get("string", ""))
            return string.replace("{0}", str(best["vmin"])).replace("{1}", str(best["vmax"]))
    return None


def can_spawn(weights: list[list[Any]], item_tags: frozenset[str]) -> bool:
    """Real PoE spawn-weight check: the first weight whose tag the item
    carries (or the catch-all ``default``) decides — weight > 0 = can roll.
    """
    for entry in weights:
        if len(entry) != 2:
            continue
        tag, weight = entry
        if tag == "default" or (isinstance(tag, str) and tag in item_tags):
            return isinstance(weight, int | float) and weight > 0
    return False


def _render(stat_id: str, value: object) -> str | None:
    render, _, _ = _load()
    tpl = render.get(stat_id) or _FALLBACK_RENDER.get(stat_id)
    if not tpl:
        return None
    string = tpl.get("string")
    if not isinstance(string, str):
        return None
    num = f"+{value}" if tpl.get("plus") else f"{value}"
    return string.replace("{0}", num)


def real_affix_line(stem: str, item_tags: frozenset[str], budget: BudgetTier) -> str | None:
    """Real mod text for *stem* at the best tier that can roll on a base
    with *item_tags* within *budget*. ``None`` if the stem has no real mod
    mapping or no tier can spawn on this slot.
    """
    cap = _BUDGET_ILVL[budget]
    # "Adds # to #" damage mods (2-stat) are handled separately.
    if stem in _STEM_TO_ADDED:
        return _added_line(stem, item_tags, cap)
    stat_ids = _STEM_TO_STAT.get(stem)
    if not stat_ids:
        return None
    # Influence-gated body affixes (Step 69) spawn only via influence tags.
    if stem in _INFLUENCE_STEMS:
        item_tags = item_tags | _BODY_INFLUENCE_TAGS
    _, tiers, _ = _load()
    # Try each candidate stat id; use the first that has a tier able to
    # roll on this slot (e.g. flat ES on jewellery vs % ES on armour).
    for stat_id in stat_ids:
        candidates = [
            t
            for t in tiers.get(stat_id, [])
            if isinstance(t.get("ilvl"), int)
            and t["ilvl"] <= cap
            and t.get("max") is not None
            and can_spawn(t.get("weights", []), item_tags)
        ]
        if candidates:
            best = max(candidates, key=lambda t: (t["ilvl"], t["max"]))
            return _render(stat_id, best["max"])
    return None
