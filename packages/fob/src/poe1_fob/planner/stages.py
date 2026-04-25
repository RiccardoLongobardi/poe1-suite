"""Stage definitions and bucketing logic for the planner.

Three stages cover the typical PoE 1 progression:

* **League start** (≤ 1 div): cheap rares + skill setup. Anything you
  can buy in the first day of a fresh league.
* **Mid-game** (1 - 25 div): the build's defining unique items, a
  5L/6L body armour, the first jewels.
* **End-game** (≥ 25 div): chase uniques, mirror-tier rares, awakened
  gems, and final min-max polishing.

Items are bucketed by their *divine-equivalent midpoint*: anything
priced at ≤ 1 div lands in League start, items in [1, 25] div go to
Mid-game, and anything above (or items poe.ninja can't price) ends up
in End-game.

Stage budgets are computed by summing the items inside each stage and
expanding the band so it always covers at least the spec-default
range. That preserves the monotone-midpoint invariant
:class:`BuildPlan` enforces, even in edge cases (e.g. a Mid-game stage
with one cheap unique that sums below the spec floor).
"""

from __future__ import annotations

from dataclasses import dataclass

from poe1_core.models import (
    Confidence,
    ContentFocus,
    CoreItem,
    Currency,
    PriceRange,
    PriceSource,
    PriceValue,
)


@dataclass(frozen=True)
class StageSpec:
    """Static description of one progression stage.

    ``floor_div`` and ``ceiling_div`` set both the bucketing threshold
    *and* the minimum range the resulting :class:`PlanStage` must
    cover. The spec defaults are deliberately overlapping at the
    boundaries (``LEAGUE_START.ceiling == MID_GAME.floor``) so an item
    priced exactly at 1 div lands in League start — the cheaper bucket
    wins ties.
    """

    label: str
    floor_div: float
    ceiling_div: float
    rationale: str
    next_trigger: str | None
    expected_content: tuple[ContentFocus, ...]


LEAGUE_START = StageSpec(
    label="League start",
    floor_div=0.0,
    ceiling_div=1.0,
    rationale=(
        "Setup base con i gem dalle quest, qualche rare cheap craftato o "
        "comprato, e gli unique sotto 1 divine. Obiettivo: cap delle "
        "resistenze e capacità di farmare T1-T8 in modo regolare."
    ),
    next_trigger=(
        "Quando hai accumulato ~1 div liquido e i tre res elementali sono "
        "a 75 %, passa al mid-game."
    ),
    expected_content=(ContentFocus.LEAGUE_START, ContentFocus.MAPPING),
)

MID_GAME = StageSpec(
    label="Mid-game",
    floor_div=1.0,
    ceiling_div=25.0,
    rationale=(
        "Aggiungi gli unique core della build (1-25 div), un body 5L/6L, "
        "e i primi cluster/jewel singoli. Stop appena puoi farmare T16 "
        "in modo affidabile e i res chaos non sono più un problema."
    ),
    next_trigger=(
        "Quando hai ~25 div di liquidità e ti senti comodo nelle T16, spingi verso l'end-game."
    ),
    expected_content=(ContentFocus.MAPPING, ContentFocus.BOSSING),
)

END_GAME = StageSpec(
    label="End-game",
    floor_div=25.0,
    ceiling_div=100.0,
    rationale=(
        "Min-max: awakened gem, cluster jewel craftati, gli unique chase "
        "(>25 div) e rare top-tier sui pezzi rimasti. Da qui in poi è "
        "ottimizzazione marginale, ma è ciò che separa una build comoda "
        "da una build da Uber."
    ),
    next_trigger=None,
    expected_content=(ContentFocus.BOSSING, ContentFocus.UBERS),
)

ALL_STAGES: tuple[StageSpec, ...] = (LEAGUE_START, MID_GAME, END_GAME)


def stage_for_amount(div_amount: float | None) -> StageSpec:
    """Decide which stage an item with *div_amount* belongs to.

    ``None`` means "we couldn't price this" — those items go to
    :data:`END_GAME` because un-priced uniques are usually the chase
    pieces poe.ninja doesn't have enough listings for.
    """

    if div_amount is None:
        return END_GAME
    if div_amount <= LEAGUE_START.ceiling_div:
        return LEAGUE_START
    if div_amount <= MID_GAME.ceiling_div:
        return MID_GAME
    return END_GAME


def _stage_default_budget(spec: StageSpec) -> PriceRange:
    """Default range for a stage with no priced items.

    Marked HEURISTIC + LOW confidence so the UI can render it dimmer
    than a data-driven band.
    """

    return PriceRange(
        min=PriceValue(amount=spec.floor_div, currency=Currency.DIVINE),
        max=PriceValue(amount=spec.ceiling_div, currency=Currency.DIVINE),
        source=PriceSource.HEURISTIC,
        confidence=Confidence.LOW,
    )


def stage_budget(
    items: list[CoreItem],
    spec: StageSpec,
    *,
    chaos_per_divine: float,
) -> PriceRange:
    """Aggregate item prices into a divine-denominated stage budget.

    Sums each item's chaos-equivalent low/high, converts back to
    divines, and clamps the result so it always covers
    ``[spec.floor_div, spec.ceiling_div]``. The clamp is what
    guarantees :class:`BuildPlan`'s monotone-midpoint invariant.

    When no item is priced (or the stage is empty), returns the
    HEURISTIC default range — same as :func:`_stage_default_budget`.
    """

    if not items:
        return _stage_default_budget(spec)

    rate = chaos_per_divine if chaos_per_divine > 0 else 1.0

    total_min_div = 0.0
    total_max_div = 0.0
    has_priced = False

    for ci in items:
        if ci.price_estimate is None:
            continue
        rng = ci.price_estimate
        if rng.currency is Currency.DIVINE:
            total_min_div += rng.min.amount
            total_max_div += rng.max.amount
        else:
            total_min_div += rng.min.amount / rate
            total_max_div += rng.max.amount / rate
        has_priced = True

    if not has_priced:
        return _stage_default_budget(spec)

    # Clamp so the band covers at least the spec defaults — preserves
    # monotone ordering across stages.
    min_div = max(spec.floor_div, total_min_div)
    max_div = max(spec.ceiling_div, max(min_div, total_max_div))

    return PriceRange(
        min=PriceValue(amount=round(min_div, 2), currency=Currency.DIVINE),
        max=PriceValue(amount=round(max_div, 2), currency=Currency.DIVINE),
        source=PriceSource.POE_NINJA,
        confidence=Confidence.MEDIUM,
    )


__all__ = [
    "ALL_STAGES",
    "END_GAME",
    "LEAGUE_START",
    "MID_GAME",
    "StageSpec",
    "stage_budget",
    "stage_for_amount",
]
