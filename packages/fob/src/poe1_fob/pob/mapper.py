"""Reduce a rich :class:`PobSnapshot` down to a lean :class:`poe1_core.Build`.

A :class:`~poe1_fob.pob.models.PobSnapshot` keeps every detail PoB
exported — passive tree, jewels, config toggles, pantheon. The rest of
the Oracle pipeline (ranking, planner) only wants the *gameplay* shape
of the build, which is what :class:`poe1_core.Build` encodes.

Classification here is heuristic: we read PoB's ``PlayerStat`` numbers
and the main skill id and apply hand-written rules. The heuristics favour
precision (return ``LIFE`` when unsure about defence, ``PHYSICAL`` when
unsure about damage) because a wrong guess is worse than a plain one —
downstream ranking can still work with a coarse label but will rank on
mis-classified profiles.
"""

from __future__ import annotations

from poe1_core.models import (
    Ascendancy,
    Build,
    BuildMetrics,
    BuildSourceType,
    CharacterClass,
    ContentFocus,
    DamageProfile,
    DefenseProfile,
    Item,
    ItemMod,
    ItemRarity,
    ItemSlot,
    KeyItem,
    ModType,
    Playstyle,
    ascendancy_to_class,
)

from .models import PobItem, PobSkillGroup, PobSnapshot
from .rares import valuable_stat_filters

# ---------------------------------------------------------------------------
# Main skill extraction
# ---------------------------------------------------------------------------


def _main_skill_group(snapshot: PobSnapshot) -> PobSkillGroup | None:
    """Find the active skill group the build is *built around*.

    Prefers the group flagged ``mainActiveSkill`` in PoB; falls back to
    the first enabled group that has at least one non-support gem.
    """

    main_idx = snapshot.main_skill_group_index
    if main_idx:
        for group in snapshot.skills:
            if group.socket_group == main_idx and _has_active_gem(group):
                return group
    for group in snapshot.skills:
        if group.enabled and _has_active_gem(group):
            return group
    return None


def _has_active_gem(group: PobSkillGroup) -> bool:
    return any(g.enabled and not g.is_support for g in group.gems)


def _main_gem_name(group: PobSkillGroup) -> tuple[str, str]:
    """Return ``(human_name, skill_id)`` for the active skill in *group*."""

    for gem in group.gems:
        if gem.enabled and not gem.is_support:
            return gem.name, gem.skill_id
    # Fallback: first non-support gem regardless of enabled.
    for gem in group.gems:
        if not gem.is_support:
            return gem.name, gem.skill_id
    return "Unknown", ""


def _support_gem_names(group: PobSkillGroup) -> list[str]:
    return [g.name for g in group.gems if g.is_support and g.enabled]


# ---------------------------------------------------------------------------
# Playstyle classification
# ---------------------------------------------------------------------------

# Map a skill-id *substring* (case-insensitive) to a playstyle. First match
# wins, so order matters — more specific patterns come first.
_PLAYSTYLE_MATCHES: tuple[tuple[str, Playstyle], ...] = (
    ("totem", Playstyle.TOTEM),
    ("trap", Playstyle.TRAP),
    ("mine", Playstyle.MINE),
    ("brand", Playstyle.BRAND),
    ("raisespectre", Playstyle.MINION),
    ("raisezombie", Playstyle.MINION),
    ("summonskeleton", Playstyle.MINION),
    ("summonholyrelic", Playstyle.MINION),
    ("summongolem", Playstyle.MINION),
    ("summonraging", Playstyle.MINION),
    ("animateguardian", Playstyle.MINION),
    ("animateweapon", Playstyle.MINION),
    ("cwdt", Playstyle.CAST_WHEN_DAMAGE_TAKEN),
    ("castwhendamagetaken", Playstyle.CAST_WHEN_DAMAGE_TAKEN),
    ("castwhilechannel", Playstyle.CAST_WHILE_CHANNELLING),
    ("channel", Playstyle.CAST_WHILE_CHANNELLING),
    ("righteousfire", Playstyle.DEGEN_AURA),
    ("scorchingray", Playstyle.DEGEN_AURA),
)

# Melee skill ids often start with these prefixes in PoB's internal ids.
_MELEE_PREFIXES: frozenset[str] = frozenset(
    {
        "cleave",
        "groundslam",
        "heavystrike",
        "lacerate",
        "ancestralwarchief",
        "earthquake",
        "doublestrike",
        "lightningstrike",
        "flickerstrike",
        "frostblades",
        "icecrash",
        "molten",
        "sunder",
        "sweep",
        "vaalcycloneskill",
        "cyclone",
        "smite",
        "shieldcharge",
        "whirlingblades",
        "boneshatter",
        "mana_strike",
    }
)

_RANGED_ATTACK_PREFIXES: frozenset[str] = frozenset(
    {
        "tornadoshot",
        "lightningarrow",
        "splitarrow",
        "icicleburst",
        "icespear",
        "kinetic",
        "powersiphon",
        "stormburst",
        "caustic_arrow",
        "rainofarrows",
        "barrage",
        "burningarrow",
        "blast_rain",
        "toxicrain",
        "galvanicarrow",
        "artillery",
        "puncture",
        "spectralshield",
    }
)


def _classify_playstyle(skill_id: str, group: PobSkillGroup) -> Playstyle:
    """Pick the closest :class:`Playstyle` for the active skill."""

    key = skill_id.lower().replace("_", "").replace("-", "")

    for fragment, style in _PLAYSTYLE_MATCHES:
        if fragment in key:
            return style

    # Support gems in the group can disambiguate attack/spell/ranged.
    support_keys = {s.lower() for s in _support_gem_names(group)}
    if any("bow" in s or "projectile" in s for s in support_keys):
        return Playstyle.RANGED_ATTACK

    for pref in _RANGED_ATTACK_PREFIXES:
        if pref in key:
            return Playstyle.RANGED_ATTACK
    for pref in _MELEE_PREFIXES:
        if pref in key:
            return Playstyle.MELEE

    # Default: if the skill id contains "attack" it's an attack; else cast.
    if "attack" in key or "strike" in key or "slam" in key:
        return Playstyle.MELEE
    return Playstyle.SELF_CAST


# ---------------------------------------------------------------------------
# Damage profile classification
# ---------------------------------------------------------------------------


def _is_minion_skill(skill_id: str) -> bool:
    key = skill_id.lower()
    return any(
        tag in key
        for tag in (
            "spectre",
            "zombie",
            "skeleton",
            "golem",
            "animateguardian",
            "animateweapon",
            "holyrelic",
        )
    )


def _classify_damage_profile(skill_id: str, stats: dict[str, float]) -> DamageProfile:
    """Derive a damage profile from the active skill and PoB stats."""

    # DoT families — PoB breaks these out by element.
    dot_mapping: tuple[tuple[str, DamageProfile], ...] = (
        ("FireDotDPS", DamageProfile.FIRE_DOT),
        ("ColdDotDPS", DamageProfile.COLD_DOT),
        ("ChaosDotDPS", DamageProfile.CHAOS_DOT),
        ("PhysicalDotDPS", DamageProfile.PHYSICAL_DOT),
        ("TotalDotDPS", DamageProfile.PHYSICAL_DOT),  # fallback
    )
    # Ailment DPS — these dominate when present.
    ailment_mapping: tuple[tuple[str, DamageProfile], ...] = (
        ("IgniteDPS", DamageProfile.IGNITE),
        ("BleedDPS", DamageProfile.BLEED),
        ("PoisonDPS", DamageProfile.POISON),
    )

    hit_dps = stats.get("HitSpeed", 0.0) * stats.get("AverageDamage", 0.0)
    if not hit_dps:
        hit_dps = stats.get("CombinedDPS", stats.get("TotalDPS", 0.0))

    # Ailments dominate if they're the build's primary output.
    for key, profile in ailment_mapping:
        if stats.get(key, 0.0) > max(hit_dps, 1_000_000.0):
            return profile

    # DoT if its dps contribution is meaningful.
    dot_total = stats.get("TotalDotDPS", 0.0)
    if dot_total > max(hit_dps, 1.0) * 0.5:
        for key, profile in dot_mapping[:-1]:
            if stats.get(key, 0.0) > 0.0:
                return profile

    # Minion skill → minion damage profile, pick element by support hint.
    if _is_minion_skill(skill_id):
        # Heuristic: chaos-flavoured spectres (e.g. Syndicate Operative)
        # show up as ChaosDamage stats. Otherwise most strong spectres do
        # elemental damage; physical is the rarer case.
        chaos = stats.get("MainHand_ChaosDPS", 0.0) + stats.get("ChaosDPS", 0.0)
        phys = stats.get("MainHand_PhysicalDPS", 0.0) + stats.get("PhysicalDPS", 0.0)
        ele = stats.get("FireDPS", 0.0) + stats.get("ColdDPS", 0.0) + stats.get("LightningDPS", 0.0)
        if chaos > max(phys, ele):
            return DamageProfile.MINION_CHAOS
        if phys > ele:
            return DamageProfile.MINION_PHYSICAL
        return DamageProfile.MINION_ELEMENTAL

    # Hit-based: pick the strongest element / phys channel.
    ele_stats = {
        DamageProfile.FIRE: stats.get("FireDPS", 0.0),
        DamageProfile.COLD: stats.get("ColdDPS", 0.0),
        DamageProfile.LIGHTNING: stats.get("LightningDPS", 0.0),
        DamageProfile.CHAOS: stats.get("ChaosDPS", 0.0),
        DamageProfile.PHYSICAL: stats.get("PhysicalDPS", 0.0),
    }
    best = max(ele_stats.items(), key=lambda kv: kv[1])
    if best[1] > 0:
        # If top two elements are both non-zero and similar, it's hybrid.
        ranked = sorted(ele_stats.values(), reverse=True)
        if (
            len(ranked) >= 2
            and ranked[1] > 0
            and ranked[0] < ranked[1] * 2.0
            and best[0] in {DamageProfile.FIRE, DamageProfile.COLD, DamageProfile.LIGHTNING}
        ):
            return DamageProfile.ELEMENTAL_HYBRID
        return best[0]

    # Last-resort inference from the skill id.
    key = skill_id.lower()
    if "fire" in key or "ignite" in key:
        return DamageProfile.FIRE
    if "cold" in key or "ice" in key or "frost" in key:
        return DamageProfile.COLD
    if "lightning" in key or "shock" in key or "arc" in key:
        return DamageProfile.LIGHTNING
    if "chaos" in key or "poison" in key or "caustic" in key:
        return DamageProfile.CHAOS
    return DamageProfile.PHYSICAL


# ---------------------------------------------------------------------------
# Defense profile classification
# ---------------------------------------------------------------------------


def _classify_defense(stats: dict[str, float], ascendancy: Ascendancy | None) -> DefenseProfile:
    """Decide between Life / CI / Low-Life / Hybrid / etc."""

    life = stats.get("Life", 0.0)
    es = stats.get("EnergyShield", 0.0)
    ci = stats.get("ChaosInoculation", 0.0)  # PoB emits 1.0 when CI is keystoned

    if ci >= 0.5 or (life <= 1.0 and es > 1000.0):
        return DefenseProfile.CHAOS_INOCULATION

    if stats.get("LowLife", 0.0) >= 0.5:
        return DefenseProfile.LOW_LIFE

    if life > 0.0 and es > life * 0.4:
        return DefenseProfile.HYBRID

    if stats.get("MindOverMatter", 0.0) >= 0.5:
        return DefenseProfile.MIND_OVER_MATTER

    # Pure-evasion/armour fall back to LIFE here because "life" is the
    # dominant survival pool; evasion/armour describe mitigation layered
    # on top, not the pool itself.
    return DefenseProfile.LIFE


# ---------------------------------------------------------------------------
# Build metrics
# ---------------------------------------------------------------------------


def _round_int(value: float) -> int:
    try:
        return max(0, round(value))
    except (OverflowError, ValueError):
        return 0


def _clamp_res(value: float) -> int:
    v = _round_int(value)
    return max(-200, min(200, v if value >= 0 else -abs(v)))


def _build_metrics(stats: dict[str, float]) -> BuildMetrics:
    """Pack PoB PlayerStat values into our :class:`BuildMetrics`."""

    total_dps = (
        stats.get("FullDPS")
        or stats.get("CombinedDPS")
        or stats.get("TotalDPS")
        or stats.get("AverageHit")
        or None
    )

    return BuildMetrics(
        total_dps=float(total_dps) if total_dps is not None else None,
        effective_hp=_round_int(stats["TotalEHP"]) if "TotalEHP" in stats else None,
        life=_round_int(stats["Life"]) if "Life" in stats else None,
        energy_shield=(_round_int(stats["EnergyShield"]) if "EnergyShield" in stats else None),
        mana=_round_int(stats["Mana"]) if "Mana" in stats else None,
        fire_res=_clamp_res(stats["FireResist"]) if "FireResist" in stats else None,
        cold_res=_clamp_res(stats["ColdResist"]) if "ColdResist" in stats else None,
        lightning_res=(
            _clamp_res(stats["LightningResist"]) if "LightningResist" in stats else None
        ),
        chaos_res=_clamp_res(stats["ChaosResist"]) if "ChaosResist" in stats else None,
        movement_speed_pct=(
            _round_int(stats["MovementSpeedMod"] * 100) if "MovementSpeedMod" in stats else None
        ),
    )


# ---------------------------------------------------------------------------
# Key items (uniques)
# ---------------------------------------------------------------------------


_MOD_TYPE_PREFIX: dict[str, ModType] = {
    "{crafted}": ModType.CRAFTED,
    "{fractured}": ModType.FRACTURED,
    "{enchant}": ModType.ENCHANT,
}


def _pob_item_to_core(pob_item: PobItem, *, slot: ItemSlot) -> Item:
    """Convert a :class:`PobItem` to a :class:`poe1_core.Item`."""

    mods: list[ItemMod] = []
    for text in pob_item.implicits:
        if text:
            mods.append(ItemMod(text=text, mod_type=ModType.IMPLICIT))
    for text in pob_item.explicits:
        if not text:
            continue
        mod_type = ModType.EXPLICIT
        lower = text.lower()
        for prefix, mt in _MOD_TYPE_PREFIX.items():
            if prefix in lower:
                mod_type = mt
                break
        mods.append(ItemMod(text=text, mod_type=mod_type))

    # Derive link count from the sockets string ("G-B-R R-R-G" has two
    # groups — the max-length group wins).
    links: int | None = None
    if pob_item.sockets:
        links = max(
            (len(group.split("-")) for group in pob_item.sockets.split()),
            default=None,
        )
        links = min(links, 6) if links else None

    return Item(
        name=pob_item.name or "",
        base_type=pob_item.base_type,
        rarity=pob_item.rarity,
        slot=slot,
        item_level=pob_item.item_level,
        mods=mods,
        sockets=pob_item.sockets,
        links=links,
        corrupted=pob_item.corrupted,
    )


# Importance per slot for promoted rares. Higher = priced first.
# Body armour and weapons have the highest absolute price spread, so
# they get top importance; jewellery sits in the middle.
_RARE_SLOT_IMPORTANCE: dict[ItemSlot, int] = {
    ItemSlot.BODY_ARMOUR: 4,
    ItemSlot.WEAPON_MAIN: 4,
    ItemSlot.WEAPON_OFFHAND: 4,
    ItemSlot.HELMET: 3,
    ItemSlot.GLOVES: 3,
    ItemSlot.BOOTS: 3,
    ItemSlot.AMULET: 3,
    ItemSlot.BELT: 3,
    ItemSlot.RING: 2,
    ItemSlot.QUIVER: 3,
}

# Below this many recognised valuable mods we don't promote a rare.
# Two filters are the minimum the Trade API needs to narrow the search
# beyond "any rare of this base"; one filter alone returns thousands
# of unrelated listings and pollutes the percentile pricer.
_RARE_MIN_VALUABLE_MODS: int = 2


def _key_items(snapshot: PobSnapshot) -> list[KeyItem]:
    """Build the KeyItem list — equipped uniques + worth-pricing rares.

    A rare is "worth pricing" when it has at least
    :data:`_RARE_MIN_VALUABLE_MODS` mods that match the
    :data:`MOD_PATTERNS` table — i.e. enough signal to send a focused
    Trade API query. Bare rares (e.g. unidentified, or with only mods
    we don't track) are skipped to avoid wasting Trade requests on
    queries that would return noise.

    Importance follows :data:`_RARE_SLOT_IMPORTANCE`. Uniques keep
    their default importance of 3 — the planner orders by stage cost
    bucket, not by importance, so the absolute number matters less
    than the relative ordering inside each bucket.
    """

    out: list[KeyItem] = []
    for slot, pob_item in snapshot.items_by_slot.items():
        if pob_item.rarity is ItemRarity.UNIQUE:
            out.append(
                KeyItem(
                    slot=slot,
                    item=_pob_item_to_core(pob_item, slot=slot),
                    importance=3,
                )
            )
            continue
        if pob_item.rarity is ItemRarity.RARE:
            filters = valuable_stat_filters(pob_item, max_filters=8)
            if len(filters) < _RARE_MIN_VALUABLE_MODS:
                continue
            importance = _RARE_SLOT_IMPORTANCE.get(slot, 2)
            out.append(
                KeyItem(
                    slot=slot,
                    item=_pob_item_to_core(pob_item, slot=slot),
                    importance=importance,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Top-level mapper
# ---------------------------------------------------------------------------


def _ensure_consistent_class(ascendancy: Ascendancy | None, cls: CharacterClass) -> CharacterClass:
    """Make sure ``character_class`` lines up with the ascendancy.

    PoB exports keep them in sync but edge cases (custom builds, class
    changes) occasionally drift; prefer the ascendancy's base class when
    the two disagree.
    """

    if ascendancy is None:
        return cls
    expected = ascendancy_to_class(ascendancy)
    return expected


def snapshot_to_build(snapshot: PobSnapshot, *, source_id: str) -> Build:
    """Reduce *snapshot* to a cross-source :class:`Build`.

    ``source_id`` should be stable across re-imports of the same PoB;
    the ingest layer uses ``f"pob::{sha1(code)[:12]}"`` so the same
    paste resolves to the same id.
    """

    group = _main_skill_group(snapshot)
    if group is None:
        raise ValueError(
            "cannot map a PoB with no active skill group; this is usually a "
            "half-finished export with every skill disabled."
        )

    main_name, main_skill_id = _main_gem_name(group)
    supports = _support_gem_names(group)

    damage = _classify_damage_profile(main_skill_id, snapshot.stats)
    playstyle = _classify_playstyle(main_skill_id, group)
    defense = _classify_defense(snapshot.stats, snapshot.ascendancy)
    metrics = _build_metrics(snapshot.stats)

    character_class = _ensure_consistent_class(snapshot.ascendancy, snapshot.character_class)

    # Default content tags: every build is assumed MAPPING-capable. A
    # meaningful total_dps tips it into BOSSING as well. Finer tagging
    # will come from the Ranking engine, which can cross-reference the
    # intent and budget.
    content_tags: list[ContentFocus] = [ContentFocus.MAPPING]
    if metrics.total_dps is not None and metrics.total_dps >= 3_000_000.0:
        content_tags.append(ContentFocus.BOSSING)
    if metrics.total_dps is not None and metrics.total_dps >= 30_000_000.0:
        content_tags.append(ContentFocus.UBERS)

    return Build(
        source_id=source_id,
        source_type=BuildSourceType.POB,
        character_class=character_class,
        ascendancy=snapshot.ascendancy,
        main_skill=main_name,
        support_gems=supports,
        damage_profile=damage,
        playstyle=playstyle,
        content_tags=content_tags,
        defense_profile=defense,
        metrics=metrics,
        key_items=_key_items(snapshot),
        pob_code=snapshot.export_code,
        origin_url=snapshot.origin_url,
        tree_version=snapshot.tree.tree_version,
    )


__all__ = ["snapshot_to_build"]
