"""ItemDegrader — produce upgrade ladders from endgame KeyItems.

A degrader turns ONE :class:`KeyItem` into an :class:`UpgradeLadder`:
a list of progressively cheaper predecessor rungs, anchored to specific
stages. The Step 13.D template engine emits the same advice for every
build with main_skill='X'; this engine emits ladder rungs derived from
the items the user actually carries, so a Vortex Occultist with
Mageblood gets different advice than one without.

This module ships the :class:`ItemDegrader` Protocol and
:class:`HardcodedDegrader` — a hand-curated table for ~10 popular
uniques. Future implementations (poe.ninja lookup, Awakened gem chain,
Forbidden Flame/Flesh ascendancy mapping) can replace it transparently.
"""

from __future__ import annotations

from typing import Protocol

from poe1_core.models import KeyItem

from .models import LadderStep, UpgradeLadder


class ItemDegrader(Protocol):
    """Convert one :class:`KeyItem` into an :class:`UpgradeLadder`.

    Implementations must always return a ladder with at least one rung
    (the endgame target itself). Returning ``None`` is not allowed —
    callers should not have to handle missing data.
    """

    def degrade(self, target: KeyItem) -> UpgradeLadder: ...


# ---------------------------------------------------------------------------
# Hardcoded ladders for popular uniques
# ---------------------------------------------------------------------------


# Each entry is a tuple of LadderStep kwargs minus stage/name (those are
# always present). The table key is the lower-cased unique name.
#
# Stage keys: "early_campaign", "mid_campaign", "end_campaign",
# "early_mapping", "end_mapping", "high_investment". See
# :mod:`poe1_fob.planner.stages` for the canonical definitions.


def _mageblood_ladder() -> tuple[LadderStep, ...]:
    """Quicksilver → Bottled Faith → Mageblood path."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="Bottled Faith",
            kind="unique",
            budget_div_max=50.0,
            rationale=(
                "Bottled Faith è il flask consacrated-ground-spawning "
                "che fa da ponte verso Mageblood. Da solo fornisce ~10% "
                "more damage + crit multi sui boss; budget 30-50 div in "
                "league mature."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Diamond + Quartz + Cinderswallow rare flask suite",
            kind="leveling",
            budget_div_max=5.0,
            rationale=(
                "Mentre risparmi per Mageblood: setup 5 flask rare con "
                "good roll (life recovery rate, rarity, increased crit, "
                "movement speed). Costo trascurabile vs il salto a "
                "Mageblood."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="Mageblood",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Mageblood: tutti i flask 5 permanenti senza dover "
                "premere il tasto. Game-changer assoluto: ~10-15x boost "
                "DPS vs setup rare flask per ogni build flask-scaling."
            ),
        ),
    )


def _headhunter_ladder() -> tuple[LadderStep, ...]:
    """Stygian Vise → Bisco's Leash → Headhunter path."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="Stygian Vise rare belt (life + 2 res + abyss jewel)",
            kind="rare_craft",
            budget_div_max=2.0,
            rationale=(
                "Stygian Vise rare con life + 2 resistance + abyss jewel "
                "socket: belt baseline che porta in T16 senza spendere "
                "div. Abyss jewel low-cost (~5 chaos) finisce il setup."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Bisco's Leash",
            kind="unique",
            budget_div_max=10.0,
            rationale=(
                "Bisco's Leash come mid-tier: rampage on rare kill + "
                "increased rarity item drop. Aggiunge ~30% pack clear + "
                "pickup speed mentre risparmi per HH."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="Headhunter",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Headhunter: ruba i mod degli rare per 20 secondi. La "
                "build cambia identità in mapping — diventa caotica e "
                "mostruosamente veloce. Endgame definitivo per mappers."
            ),
        ),
    )


def _kaom_heart_ladder() -> tuple[LadderStep, ...]:
    """Tabula Rasa → 4L craftato → 6L craftato → Kaom's Heart."""

    return (
        LadderStep(
            stage_key="early_campaign",
            item_name="Tabula Rasa",
            kind="unique",
            budget_div_max=0.5,
            rationale=(
                "Tabula Rasa: 6L economico (~1-2 chaos) per partire con "
                "il main skill già linkato. Zero life ma ti fa correre "
                "fino al primo lab senza problemi."
            ),
        ),
        LadderStep(
            stage_key="mid_campaign",
            item_name="Body 4L craftato (alteration spam life + 2 res)",
            kind="rare_craft",
            budget_div_max=0.5,
            rationale=(
                "Switch a body 4L craftato: alteration spam su un base "
                "armour/EV/ES per life% + 2 resistance. Costo ~1 chaos, "
                "regge fino a Kaom's Heart."
            ),
        ),
        LadderStep(
            stage_key="early_mapping",
            item_name="Kaom's Heart",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Kaom's Heart: niente socket ma +500 life flat e damage "
                "massive da '%life increased'. Il signature di tante "
                "build life-stacking (RF Jugg, Cyclone Slayer)."
            ),
        ),
    )


def _watchers_eye_ladder(target: KeyItem) -> tuple[LadderStep, ...]:
    """Generic Watcher's Eye ladder with the target's specific mods."""

    target_name = target.item.name or "Watcher's Eye"
    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="Watcher's Eye 1-mod",
            kind="unique",
            budget_div_max=10.0,
            rationale=(
                "Watcher's Eye 1-mod (single useful aura mod): mid-tier "
                "intro. Costa 5-10 div in league mature. Spinta solida "
                "anche prima della versione 2-mod."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name=target_name,
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Watcher's Eye 2-mod (entrambe gli aura mod che vuoi): "
                "lo step endgame. La spesa varia drasticamente per la "
                "combo (10-300+ div). Trade API stat-aware lookup è il "
                "modo più affidabile di prezzarlo."
            ),
        ),
    )


def _forbidden_pair_ladder(target: KeyItem) -> tuple[LadderStep, ...]:
    """Forbidden Flame / Flesh combo — ascendancy-aware pair ladder.

    Reads the target's mod text to extract the ascendancy notable being
    allocated (via the same regex used in
    :func:`poe1_pricing.variants.keystone_allocates_resolver`). When the
    notable can't be resolved, falls back to a generic "(any notable)"
    label so the ladder still surfaces.
    """

    target_name = target.item.name or "Forbidden Jewel"
    notable = _resolve_forbidden_notable(target)
    notable_label = notable or "(any notable)"

    if notable is not None:
        # The pair targets a specific ascendancy notable (e.g.
        # "Avatar of Fire", "Mind Over Matter"). Surface it explicitly
        # so the user knows which notable to chase.
        end_map_text = (
            f"Single Forbidden Flame OR Flesh per '{notable}': "
            "costa 1/10 della coppia matchata ma non dà bonus da solo. "
            "Lascia questo come marker durante End Mapping mentre cerchi "
            "il match (la coppia + 1/2 jewel = doppia notable)."
        )
        endgame_text = (
            f"Forbidden Flame + Flesh matched pair per '{notable}': la "
            "doppia ascendancy notable. Il prezzo esplode in base alla "
            "notable scelta (10-300+ div per la coppia)."
        )
    else:
        # No notable extractable from mods — fall back to the generic
        # phrasing the original ladder used.
        end_map_text = (
            "Single Forbidden Flame OR Flesh costa 1/10 della combo ma "
            "non dà bonus: serve la coppia matchata. Lascia questo come "
            "marker durante End Mapping mentre cerchi il match."
        )
        endgame_text = (
            "Forbidden Flame + Flesh matched pair: doppia ascendancy "
            "notable. Step endgame per ogni build moderna; il prezzo "
            "esplode in base alla notable scelta (10-300+ div per la "
            "coppia matchata)."
        )

    return (
        LadderStep(
            stage_key="end_mapping",
            item_name=f"{target_name} (single jewel — {notable_label})",
            kind="unique",
            budget_div_max=20.0,
            rationale=end_map_text,
        ),
        LadderStep(
            stage_key="high_investment",
            item_name=f"{target_name} matched pair ({notable_label})",
            kind="unique",
            budget_div_max=None,
            rationale=endgame_text,
        ),
    )


def _resolve_forbidden_notable(target: KeyItem) -> str | None:
    """Extract the ascendancy notable from a Forbidden Jewel's mods.

    Reuses the same "Allocates X" regex defined in
    :mod:`poe1_pricing.variants` (the variant registry resolver).
    Returns the notable display name (e.g. "Avatar of Fire") or
    ``None`` when the mod text doesn't carry an ``Allocates`` line —
    e.g. test fixtures with empty mods or builds where the PoB export
    stripped the variant line.
    """

    from poe1_pricing.variants import keystone_allocates_resolver

    mod_lines = tuple(m.text for m in target.item.mods)
    return keystone_allocates_resolver(mod_lines)


def _loreweave_ladder() -> tuple[LadderStep, ...]:
    """Tabula → 4L → Loreweave (cap 80% all res with 6L)."""

    return (
        LadderStep(
            stage_key="early_campaign",
            item_name="Tabula Rasa",
            kind="unique",
            budget_div_max=0.5,
            rationale=("Tabula Rasa: 6L economico per partire. Stop-gap fino al primo body 4L."),
        ),
        LadderStep(
            stage_key="end_campaign",
            item_name="Body 4L craftato (life + 2 res alteration spam)",
            kind="rare_craft",
            budget_div_max=1.0,
            rationale=(
                "Body 4L craftato per arrivare a Kitava con 75% res cap. "
                "Loreweave costa troppo prima del mapping."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Loreweave",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Loreweave: cap 80% all res con 6L. Un upgrade di 5% res "
                "su tutti gli elementi è enorme contro mob ele alti. "
                "Drop-in vs Kaom's Heart se la build vuole socket."
            ),
        ),
    )


def _ashes_of_the_stars_ladder() -> tuple[LadderStep, ...]:
    """+1 amulet base → Astramentis → Ashes of the Stars."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="+1 to Spell Skills amulet (Hinekora's Lock craft)",
            kind="rare_craft",
            budget_div_max=3.0,
            rationale=(
                "Amulet rare con +1 spell skills + life + res: budget intro. "
                "Costa pochi div ma porta tier intermedio decoroso."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Astramentis",
            kind="unique",
            budget_div_max=10.0,
            rationale=(
                "Astramentis: +80-100 a tutti gli attributi. Risolve i "
                "requirements stat di endgame gem (Awakened Empower 5 "
                "wants 200+ str/int) senza pivot del tree."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="Ashes of the Stars",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Ashes of the Stars: +1 to Level of Socketed Gems su "
                "amulet. Combinato con +2 socketed body = +9 levels totali "
                "sui 6L. Il jolly endgame per ogni build gem-scaling."
            ),
        ),
    )


def _bottled_faith_ladder() -> tuple[LadderStep, ...]:
    """Diamond flask → Cinderswallow → Bottled Faith."""

    return (
        LadderStep(
            stage_key="end_campaign",
            item_name="Diamond Flask rare (rarity + crit chance)",
            kind="rare_craft",
            budget_div_max=0.3,
            rationale=(
                "Diamond Flask con good roll: bridge low-budget per crit "
                "scaling fino a Bottled Faith. Costo trascurabile."
            ),
        ),
        LadderStep(
            stage_key="early_mapping",
            item_name="Cinderswallow Urn",
            kind="unique",
            budget_div_max=2.0,
            rationale=(
                "Cinderswallow Urn (~5-15 chaos): increased item rarity + "
                "10% increased life on kill. Mid-tier pre-Bottled Faith."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Bottled Faith",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Bottled Faith: spawna consacrated ground = 100% increased "
                "crit chance + 10% more damage taken sui mob nell'area. "
                "Build crit / consacrated scaling (Inquisitor / Pathfinder)."
            ),
        ),
    )


def _aegis_aurora_ladder() -> tuple[LadderStep, ...]:
    """Lifesprig → Saffel's → Aegis Aurora."""

    return (
        LadderStep(
            stage_key="early_campaign",
            item_name="Lifesprig wand (twinned offhand)",
            kind="unique",
            budget_div_max=0.05,
            rationale=(
                "Lifesprig wand 1 chaos: +1 spell skill + life regen on "
                "kill. Twinned (DW Lifesprig) per +2 spell skill totali."
            ),
        ),
        LadderStep(
            stage_key="mid_campaign",
            item_name="Saffell's Frame shield",
            kind="unique",
            budget_div_max=0.5,
            rationale=(
                "Saffell's Frame: spell block + +5% max all res. Bridge "
                "verso Aegis Aurora durante atto 6-10."
            ),
        ),
        LadderStep(
            stage_key="early_mapping",
            item_name="Aegis Aurora",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Aegis Aurora (~1-3 div): replenish ES on block. Combinato "
                "con block cap (Glancing Blows / Versatile Combatant) = "
                "infinite ES sustain. Signature build difensivo Guardian / "
                "Inquisitor / Glad."
            ),
        ),
    )


def _sublime_vision_ladder() -> tuple[LadderStep, ...]:
    """+1 amulet → Yoke of Suffering → Sublime Vision."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="Yoke of Suffering",
            kind="unique",
            budget_div_max=2.0,
            rationale=(
                "Yoke of Suffering: ailments overlap (chill + scorch + "
                "shock + sap stack tutti). Damage multi flat per build "
                "ele attack."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Sublime Vision",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Sublime Vision: l'aura selezionata ha effetto triplicato. "
                "Step endgame per Aurabot / build aura-scaling. La scelta "
                "dell'aura cambia drasticamente il prezzo (Wrath/Pride "
                "top, Vitality/Clarity entry)."
            ),
        ),
    )


def _crown_of_tyrant_ladder() -> tuple[LadderStep, ...]:
    """Devouring Diadem → Crown of the Tyrant (aura builds)."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="The Devouring Diadem",
            kind="unique",
            budget_div_max=2.0,
            rationale=(
                "Devouring Diadem (~1-3 div): Eldritch Battery + reservation "
                "efficiency + auto-cast Desecrate. Bridge per build mana-"
                "intensive + aura stacking pre-Crown of the Tyrant."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="Crown of the Tyrant",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Crown of the Tyrant: 35% increased effect of non-curse "
                "auras + Eldritch implicit slots = aura effect massivo. "
                "Endgame Aurabot + build aura-stacking (Sublime Vision "
                "synergy) — 10-30 div."
            ),
        ),
    )


def _brass_dome_ladder() -> tuple[LadderStep, ...]:
    """4L craft → Tabula 6L → Brass Dome (armour tank builds)."""

    return (
        LadderStep(
            stage_key="end_campaign",
            item_name="Body armour rare 4L (life + armour + res)",
            kind="rare_craft",
            budget_div_max=0.5,
            rationale=(
                "Body 4L armour-base craftato: armour% + life + 2 res. "
                "Bridge fino a Brass Dome o Loreweave. Affordable."
            ),
        ),
        LadderStep(
            stage_key="early_mapping",
            item_name="Brass Dome",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Brass Dome (~1-3 div): massive armour + cannot be shocked "
                "+ critical strikes deal no extra damage. Game-changer "
                "per Boneshatter / slam tank builds (resistono ai loro "
                "stessi crit ricochet)."
            ),
        ),
    )


def _shavronne_ladder() -> tuple[LadderStep, ...]:
    """Tabula → 4L craft → Shavronne's Wrappings (Low Life builds)."""

    return (
        LadderStep(
            stage_key="early_campaign",
            item_name="Tabula Rasa",
            kind="unique",
            budget_div_max=0.5,
            rationale=("Tabula Rasa: 6L economico per il main skill. No life ma in atto regge."),
        ),
        LadderStep(
            stage_key="end_campaign",
            item_name="Body 6L craftato (life + ES hybrid)",
            kind="rare_craft",
            budget_div_max=2.0,
            rationale=(
                "Body 6L craftato hybrid life/ES: bridge verso il setup "
                "Low Life. Affordable e regge nel mapping iniziale."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Shavronne's Wrappings",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Shavronne's Wrappings: chaos damage doesn't bypass ES. "
                "Abilita Low Life setup (Pain Attunement = +50% spell "
                "damage) + Shavronne's + Solaris Lorica per chaos res "
                "infinito. Signature spell caster Low Life."
            ),
        ),
    )


def _cospri_will_ladder() -> tuple[LadderStep, ...]:
    """Cherrubim's Maleficence → Cospri's Will (chaos DoT builds)."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="Cherrubim's Maleficence",
            kind="unique",
            budget_div_max=1.0,
            rationale=(
                "Cherrubim's Maleficence (~5-10 chaos): +5 to all chaos "
                "skill gems + life. Bridge verso Cospri's Will per "
                "chaos DoT scaling."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="Cospri's Will",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Cospri's Will (~5-15 div): cursed by Despair + Wither on "
                "hit (gratis su nemici se cannot evade). Auto-curse + "
                "auto-wither = DPS multiplier massiccio per chaos "
                "DoT (BV Assassin, Bane Occ, ED+Contagion)."
            ),
        ),
    )


def _saviour_ladder() -> tuple[LadderStep, ...]:
    """Lycosidae → +1 socketed shield → The Saviour."""

    return (
        LadderStep(
            stage_key="early_mapping",
            item_name="Lycosidae shield",
            kind="unique",
            budget_div_max=0.5,
            rationale=(
                "Lycosidae (~1 chaos): hits can't be evaded. Risolve il "
                "problema accuracy per build attack senza Resolute "
                "Technique. Step intro affordable."
            ),
        ),
        LadderStep(
            stage_key="end_mapping",
            item_name="+1 to Socketed Gems shield craft",
            kind="rare_craft",
            budget_div_max=10.0,
            rationale=(
                "Shield rare con +1 to socketed gems + spell crit + life: "
                "bridge intermedio prima del Saviour. Custom craft "
                "Hinekora's Lock o Eldritch implicit."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="The Saviour",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "The Saviour (~30-50 div): triggered Reflection (mirror "
                "minion che usa la tua weapon) + crit chance + crit multi. "
                "Endgame crit attack signature (Reave Slayer, Static "
                "Strike Glad, Spectral Helix Scion)."
            ),
        ),
    )


def _crystallised_omniscience_ladder() -> tuple[LadderStep, ...]:
    """Astramentis → Crystallised Omniscience (omniscience scaling)."""

    return (
        LadderStep(
            stage_key="end_mapping",
            item_name="Astramentis",
            kind="unique",
            budget_div_max=10.0,
            rationale=(
                "Astramentis: +80-100 a tutti gli attributi. Bridge verso "
                "Crystallised Omniscience: ti dà gli attributi necessari "
                "per equip stat-heavy items mentre raccogli i res da gear."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name="Crystallised Omniscience",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Crystallised Omniscience: tutti i res ele convertiti in "
                "Omniscience (stat). Scaling esponenziale: +1 to all "
                "attributes per ogni 15 omniscience. Endgame stat-stack "
                "(50-150+ div). Richiede res cap già da gear/passive."
            ),
        ),
    )


# Lookup table — keys are case-folded unique names. Values are factory
# functions that build the rung tuple for that target. Some take the
# target as input (Watcher's Eye, Forbidden) so they can substitute the
# specific variant name into the rationale; static ones ignore it.
_LADDER_TABLE: dict[str, object] = {
    # Body armours
    "kaom's heart": _kaom_heart_ladder,
    "loreweave": _loreweave_ladder,
    "brass dome": _brass_dome_ladder,
    "shavronne's wrappings": _shavronne_ladder,
    "cospri's will": _cospri_will_ladder,
    # Belts
    "mageblood": _mageblood_ladder,
    "headhunter": _headhunter_ladder,
    # Helmets
    "crown of the tyrant": _crown_of_tyrant_ladder,
    # Amulets
    "ashes of the stars": _ashes_of_the_stars_ladder,
    "sublime vision": _sublime_vision_ladder,
    "crystallised omniscience": _crystallised_omniscience_ladder,
    # Shields
    "aegis aurora": _aegis_aurora_ladder,
    "the saviour": _saviour_ladder,
    # Flasks
    "bottled faith": _bottled_faith_ladder,
    # Jewels
    "watcher's eye": _watchers_eye_ladder,
    "forbidden flame": _forbidden_pair_ladder,
    "forbidden flesh": _forbidden_pair_ladder,
}


def _endgame_only_fallback(target: KeyItem) -> UpgradeLadder:
    """Single-rung ladder pointing at the endgame target itself.

    Used when no entry in :data:`_LADDER_TABLE` matches. The rung is
    anchored to High Investment with no budget cap.
    """

    name = target.item.name or "(unknown item)"
    return UpgradeLadder(
        target_name=name,
        rungs=(
            LadderStep(
                stage_key="high_investment",
                item_name=name,
                kind="unique",
                budget_div_max=None,
                rationale=(
                    f"Per ora niente ladder hardcoded per {name}. Il "
                    "reverse-progression engine ha solo l'endgame come "
                    "milestone — nessun rung intermedio. Aggiungi una "
                    "voce in poe1_fob.reverse.degrader._LADDER_TABLE "
                    "per migliorare."
                ),
            ),
        ),
    )


class HardcodedDegrader:
    """First :class:`ItemDegrader` implementation.

    Looks up the target's name in :data:`_LADDER_TABLE`. If found,
    invokes the factory to build the rung tuple (passing the target
    when the factory accepts it). If not found, falls back to a single-
    rung "endgame only" ladder anchored to High Investment.

    Stateless and reusable across requests.
    """

    def degrade(self, target: KeyItem) -> UpgradeLadder:
        name = (target.item.name or "").casefold()
        factory = _LADDER_TABLE.get(name)
        if factory is None:
            return _endgame_only_fallback(target)

        # Factories with target-aware substitution take 1 arg, static
        # ones take 0. Use a tiny callable shim instead of duck-typing.
        rungs: tuple[LadderStep, ...]
        try:
            rungs = factory(target)  # type: ignore[operator]
        except TypeError:
            rungs = factory()  # type: ignore[operator]

        return UpgradeLadder(
            target_name=target.item.name or "(unknown)",
            rungs=rungs,
        )


# ---------------------------------------------------------------------------
# Awakened-gem chain degrader
# ---------------------------------------------------------------------------


# Pattern matching for Awakened gem ladder construction. Awakened
# gems have an explicit upgrade chain: Awakened * 5 → 4 → 3 → 2 → 1
# → vanilla support. Each level drops ~50-70% in price (rough).
# We don't price the chain here; the rationale describes what to chase.
_AWAKENED_GEM_NAMES: frozenset[str] = frozenset(
    {
        "awakened added chaos",
        "awakened added cold",
        "awakened added fire",
        "awakened added lightning",
        "awakened blasphemy",
        "awakened brand recall",
        "awakened brutality",
        "awakened burning damage",
        "awakened cast on critical strike",
        "awakened cast while channelling",
        "awakened chain",
        "awakened cold penetration",
        "awakened controlled destruction",
        "awakened deadly ailments",
        "awakened elemental damage with attacks",
        "awakened elemental focus",
        "awakened empower",
        "awakened enhance",
        "awakened enlighten",
        "awakened fire penetration",
        "awakened fork",
        "awakened generosity",
        "awakened greater multiple projectiles",
        "awakened hextouch",
        "awakened lightning penetration",
        "awakened melee physical damage",
        "awakened melee splash",
        "awakened minion damage",
        "awakened multistrike",
        "awakened spell cascade",
        "awakened spell echo",
        "awakened swift affliction",
        "awakened trap and mine damage",
        "awakened unbound ailments",
        "awakened vicious projectiles",
        "awakened vile toxins",
        "awakened void manipulation",
    }
)


class AwakenedGemDegrader:
    """Degrader specialised for Awakened gem chains.

    Awakened gems live in a known upgrade ladder: regular support →
    vaal-corrupted 21/20 → Awakened level 1 → 2 → 3 → 4 → 5. Prices
    drop sharply each step down, so a build that calls for "Awakened
    Empower 5" naturally has "Awakened Empower 3" as a mid-tier target
    and "Empower 4" as an early-tier one.

    This degrader emits the conceptual ladder (no live pricing yet —
    Step 13.C T3 covers data-driven enrichment). It only matches items
    whose name appears in :data:`_AWAKENED_GEM_NAMES`; for other items
    callers should fall through to :class:`HardcodedDegrader` or any
    other degrader in their composite pipeline.

    Returns a 3-rung ladder: regular support (Mid Campaign) → Awakened
    level 1 / vaal corrupted (Early Mapping) → Awakened level 5 (High
    Investment).
    """

    def degrade(self, target: KeyItem) -> UpgradeLadder:
        name = (target.item.name or "").strip()
        if name.casefold() not in _AWAKENED_GEM_NAMES:
            return _endgame_only_fallback(target)

        # Strip the "Awakened " prefix to derive the regular support gem
        # name. e.g. "Awakened Empower" → "Empower Support".
        regular_base = name.removeprefix("Awakened ").removeprefix("awakened ").strip()
        regular_name = f"{regular_base} Support"

        return UpgradeLadder(
            target_name=name,
            rungs=(
                LadderStep(
                    stage_key="mid_campaign",
                    item_name=regular_name,
                    kind="leveling",
                    budget_div_max=0.5,
                    rationale=(
                        f"Versione regular ({regular_name}): si droppa "
                        "in atto o si compra a 1 alteration. Il level 18 "
                        "regge fino al primo body 6L."
                    ),
                ),
                LadderStep(
                    stage_key="early_mapping",
                    item_name=f"{name} 1 (entry-level)",
                    kind="unique",
                    budget_div_max=2.0,
                    rationale=(
                        f"{name} level 1 (~1-3 div): primo step nella "
                        "ladder Awakened. Il vero damage tier salta a "
                        "level 3-4, ma level 1 è un upgrade tangibile "
                        "rispetto al regular Vaal-corrupted 21."
                    ),
                ),
                LadderStep(
                    stage_key="high_investment",
                    item_name=f"{name} 5",
                    kind="unique",
                    budget_div_max=None,
                    rationale=(
                        f"{name} level 5 corrupted: cap del support gem. "
                        "Mirror-tier setup. Costo varia 30-200+ div in "
                        "base al gem (Empower/Multistrike top, Spell "
                        "Cascade/Brand Recall mid)."
                    ),
                ),
            ),
        )


# ---------------------------------------------------------------------------
# Composite degrader — chain multiple strategies
# ---------------------------------------------------------------------------


class CompositeDegrader:
    """Try each :class:`ItemDegrader` in order; first match wins.

    A degrader "matches" when it returns a multi-rung ladder. A
    single-rung fallback ("no ladder hardcoded for X") counts as miss
    so the next degrader gets a shot. This lets you stack specialised
    degraders (gems → uniques → fallback) without each one needing to
    know about the others.

    Construction order matters: list the most specialised degraders
    first. A reasonable default for production is::

        CompositeDegrader([
            AwakenedGemDegrader(),
            HardcodedDegrader(),
        ])
    """

    def __init__(self, degraders: list[ItemDegrader]) -> None:
        if not degraders:
            raise ValueError("CompositeDegrader requires at least one degrader")
        self._degraders = list(degraders)

    def degrade(self, target: KeyItem) -> UpgradeLadder:
        last_fallback: UpgradeLadder | None = None
        for degrader in self._degraders:
            ladder = degrader.degrade(target)
            if len(ladder.rungs) > 1:
                # Multi-rung ladder = real match, return immediately.
                return ladder
            # Single-rung = fallback. Keep it as a last-resort but
            # let later degraders try first.
            last_fallback = ladder
        # All degraders fell back. Return the last one's fallback so
        # the user still sees *some* rung anchored to High Investment.
        assert last_fallback is not None  # constructor guarantees non-empty
        return last_fallback
