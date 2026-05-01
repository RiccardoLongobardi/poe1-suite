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
    """Forbidden Flame / Flesh combo — single-jewel placeholder + endgame combo."""

    target_name = target.item.name or "Forbidden Jewel"
    return (
        LadderStep(
            stage_key="end_mapping",
            item_name=f"{target_name} (single jewel only)",
            kind="unique",
            budget_div_max=20.0,
            rationale=(
                "Single Forbidden Flame OR Flesh costa 1/10 della combo "
                "ma non da bonus: serve la coppia matchata. Lascia "
                "questo come marker durante End Mapping mentre cerchi il "
                "match."
            ),
        ),
        LadderStep(
            stage_key="high_investment",
            item_name=f"{target_name} matched pair (Flame + Flesh)",
            kind="unique",
            budget_div_max=None,
            rationale=(
                "Forbidden Flame + Flesh matched pair: doppia ascendancy "
                "notable. Step endgame per ogni build moderna; il prezzo "
                "esplode in base alla notable scelta (10-300+ div per la "
                "coppia matchata)."
            ),
        ),
    )


# Lookup table — keys are case-folded unique names. Values are factory
# functions that build the rung tuple for that target. Some take the
# target as input (Watcher's Eye, Forbidden) so they can substitute the
# specific variant name into the rationale; static ones ignore it.
_LADDER_TABLE: dict[str, object] = {
    "mageblood": _mageblood_ladder,
    "headhunter": _headhunter_ladder,
    "kaom's heart": _kaom_heart_ladder,
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
