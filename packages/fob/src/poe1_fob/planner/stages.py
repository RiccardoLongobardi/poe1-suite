"""Stage definitions and bucketing logic for the planner v2.

Six stages cover the full PoE 1 journey from day 0 to day 100+:

* **Early Campaign** (≤ 0.5 div) — atti 1-4, levelling pre-lab,
  Holy Flame Totem / Caustic Arrow / Frostblink-tier skills, gem dalle
  quest, qualche unique levelling cheap (Goldrim, Wanderlust, Lifesprig).
* **Mid Campaign** (0.5 - 2 div) — atti 5-7, primo lab, prima 4L,
  Springleaf / Karui Ward, ascendancy iniziale.
* **End Campaign** (2 - 8 div) — atti 8-10 + Kitava, res cap, primo
  set di unique core, primo body 4L/5L, ascendancy completa.
* **Early Mapping** (8 - 25 div) — T1-T8 maps, Atlas tree avviato,
  primi cluster jewel, primo body 6L, Maven Awakening.
* **End Mapping** (25 - 100 div) — T14-T16, Conqueror+Sirus+Maven,
  set unique core completo, awakened gem base.
* **High Investment** (≥ 100 div) — Uber pinnacle, mirror-tier rare,
  Mageblood, awakened 5/6, Forbidden Flame+Flesh combo.

Items are bucketed by their *divine-equivalent midpoint*. Boundaries
are inclusive on the lower stage so an item priced exactly at 0.5 div
lands in Early Campaign (cheaper bucket wins).

Stage budgets are computed by summing the items inside each stage and
expanding the band so it always covers at least the spec-default
range. That preserves the monotone-midpoint invariant
:class:`BuildPlan` enforces, even in edge cases (a Mid Campaign stage
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
    boundaries (``Early Campaign.ceiling == Mid Campaign.floor``) so an
    item priced exactly at 0.5 div lands in Early Campaign — the
    cheaper bucket wins ties.

    The ``key`` is a stable identifier used to dispatch
    template-specific content (gem changes, tree changes, rationale)
    in :mod:`poe1_fob.planner.templates` — the label may be
    user-facing copy and prone to translation churn.
    """

    key: str
    label: str
    floor_div: float
    ceiling_div: float
    rationale: str
    next_trigger: str | None
    expected_content: tuple[ContentFocus, ...]


# ---------------------------------------------------------------------------
# The six stages
# ---------------------------------------------------------------------------

EARLY_CAMPAIGN = StageSpec(
    key="early_campaign",
    label="Early Campaign",
    floor_div=0.0,
    ceiling_div=0.5,
    rationale=(
        "Atti 1-4. Usi i gem dalle quest, raccogli currency a terra, e indossi "
        "qualche unique levelling sotto 0.5 div (Goldrim, Wanderlust, Lifesprig, "
        "Tabula Rasa quando arrivi al level 5). Niente craft sofisticato: "
        "Transmute + Alteration spam su un body bianco a 4-link è già abbastanza."
    ),
    next_trigger=(
        "Quando completi atto 5 (~level 40-45) e hai accumulato 5-10 chaos "
        "liquidi, passa al Mid Campaign."
    ),
    expected_content=(ContentFocus.LEAGUE_START,),
)

MID_CAMPAIGN = StageSpec(
    key="mid_campaign",
    label="Mid Campaign",
    floor_div=0.5,
    ceiling_div=2.0,
    rationale=(
        "Atti 5-7. Primo lab (level ~33), ascendancy points iniziali, prima "
        "4L per la skill principale. Resistenze importanti: cap fire/cold/lightning "
        "almeno a 60% per i debuff di Kitava in arrivo. Springleaf, Karui Ward, "
        "Goldrim sono i workhorse di questa fase."
    ),
    next_trigger=(
        "Quando hai finito il secondo lab (Cruel) e i res sono sopra 60%, "
        "spingi per finire la campaign."
    ),
    expected_content=(ContentFocus.LEAGUE_START,),
)

END_CAMPAIGN = StageSpec(
    key="end_campaign",
    label="End Campaign",
    floor_div=2.0,
    ceiling_div=8.0,
    rationale=(
        "Atti 8-10 + Kitava. Res cap a 75% (Kitava taglia 30%, prevedi over-cap), "
        "ascendancy completa al Merciless (terzo lab, level ~65). Body 4L/5L "
        "rare con life + res, primo unique core della build (Belly of the Beast, "
        "Brass Dome, Cospri's Will, ecc. a seconda dell'archetipo). "
        "Pronto per atlas progression."
    ),
    next_trigger=(
        "Kitava è morto, sei in white maps con res cappati e ~3-5 div liquidi. "
        "Inizia Atlas progression."
    ),
    expected_content=(ContentFocus.LEAGUE_START, ContentFocus.MAPPING),
)

EARLY_MAPPING = StageSpec(
    key="early_mapping",
    label="Early Mapping",
    floor_div=8.0,
    ceiling_div=25.0,
    rationale=(
        "T1-T8 maps. Atlas tree avviato (Maven Awakening + Eldritch Altars sono "
        "le 2 voids prioritarie), primi cluster jewel medi (1-2 div), body 6L "
        "(comprato pre-fitted o craftato con Tainted Fusing). Inizia a buyout "
        "i primi unique medi (Inpulsa, Kaom's Heart, Voll's Devotion). "
        "Maven Awakening level 3+ è il target per sbloccare Searing Exarch."
    ),
    next_trigger=(
        "T16 stabile, 25+ div liquidi, hai ucciso almeno una volta i Conqueror. "
        "Passa al farming dell'end-game."
    ),
    expected_content=(ContentFocus.MAPPING,),
)

END_MAPPING = StageSpec(
    key="end_mapping",
    label="End Mapping",
    floor_div=25.0,
    ceiling_div=100.0,
    rationale=(
        "T14-T16, Conqueror, Sirus, Maven. Set unique core completo, body 6L "
        "rare con +1 socketed o equivalente, awakened gem base (Awakened Added "
        "Fire / Awakened Spell Echo / Awakened Empower 4). Cluster jewel "
        "high-roll, watcher's eye con la combo aura della build. Atlas "
        "completato 95%+, Wandering Path o Voidstones."
    ),
    next_trigger=(
        "Sirus 9 è facile, Maven da Awakened è confortevole. "
        "Vuoi puntare agli Uber? Vai di High Investment."
    ),
    expected_content=(ContentFocus.MAPPING, ContentFocus.BOSSING),
)

HIGH_INVESTMENT = StageSpec(
    key="high_investment",
    label="High Investment",
    floor_div=100.0,
    ceiling_div=1000.0,
    rationale=(
        "Uber pinnacle e oltre. Mageblood (~250-300 div), awakened 5/6 a "
        "level 21, mirror-tier rare con +2 socketed gems / suppression / "
        "life / res, Forbidden Flame+Flesh combo per ascendancy notable extra. "
        "Hands of the High Templar craftato custom. Da qui in poi è "
        "ottimizzazione marginale ma è ciò che separa una build comoda "
        "da una build da Uber."
    ),
    next_trigger=None,
    expected_content=(ContentFocus.BOSSING, ContentFocus.UBERS),
)

ALL_STAGES: tuple[StageSpec, ...] = (
    EARLY_CAMPAIGN,
    MID_CAMPAIGN,
    END_CAMPAIGN,
    EARLY_MAPPING,
    END_MAPPING,
    HIGH_INVESTMENT,
)


# ---------------------------------------------------------------------------
# Bucketing
# ---------------------------------------------------------------------------


def stage_for_amount(div_amount: float | None) -> StageSpec:
    """Decide which stage an item with *div_amount* belongs to.

    ``None`` means "we couldn't price this" — those items go to
    :data:`HIGH_INVESTMENT` because un-priced uniques are usually
    chase pieces poe.ninja doesn't have enough listings for.
    """

    if div_amount is None:
        return HIGH_INVESTMENT
    if div_amount <= EARLY_CAMPAIGN.ceiling_div:
        return EARLY_CAMPAIGN
    if div_amount <= MID_CAMPAIGN.ceiling_div:
        return MID_CAMPAIGN
    if div_amount <= END_CAMPAIGN.ceiling_div:
        return END_CAMPAIGN
    if div_amount <= EARLY_MAPPING.ceiling_div:
        return EARLY_MAPPING
    if div_amount <= END_MAPPING.ceiling_div:
        return END_MAPPING
    return HIGH_INVESTMENT


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
    "EARLY_CAMPAIGN",
    "EARLY_MAPPING",
    "END_CAMPAIGN",
    "END_MAPPING",
    "HIGH_INVESTMENT",
    "MID_CAMPAIGN",
    "StageSpec",
    "stage_budget",
    "stage_for_amount",
]
