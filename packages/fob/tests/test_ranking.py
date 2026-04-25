"""Unit tests for the Ranking Engine.

All tests are fully offline — no HTTP calls, no poe.ninja, no Anthropic.
Real :class:`RemoteBuildRef` and :class:`BuildIntent` objects are
constructed in memory using the public Pydantic models.
"""

from __future__ import annotations

from datetime import UTC, datetime

from poe1_builds.models import RemoteBuildRef
from poe1_core.models.build_intent import BudgetRange, BuildIntent
from poe1_core.models.enums import (
    BudgetTier,
    ComplexityLevel,
    DamageProfile,
    DefenseProfile,
    HardConstraint,
    ParserOrigin,
    Playstyle,
)
from poe1_fob.ranking.engine import RankingEngine
from poe1_fob.ranking.models import RankedBuild, ScoreBreakdown
from poe1_fob.ranking.scorer import (
    score_budget,
    score_complexity,
    score_damage,
    score_defense,
    score_playstyle,
    score_ref,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_COUNTER = 0


def _make_ref(
    main_skill: str | None = None,
    life: int = 3000,
    energy_shield: int = 0,
    dps: int = 1_000_000,
    level: int = 90,
    class_name: str = "Witch",
) -> RemoteBuildRef:
    global _COUNTER
    _COUNTER += 1
    return RemoteBuildRef.model_validate(
        {
            "source_id": f"ninja::test::{_COUNTER}",
            "account": "testaccount",
            "character": f"testchar{_COUNTER}",
            "class": class_name,
            "level": level,
            "life": life,
            "energy_shield": energy_shield,
            "ehp": life + energy_shield,
            "dps": dps,
            "main_skill": main_skill,
            "weapon_mode": None,
            "league": "Mirage",
            "snapshot_version": "v1",
            "fetched_at": datetime.now(UTC),
        }
    )


def _make_intent(
    damage_profile: DamageProfile | None = None,
    playstyle: Playstyle | None = None,
    defense_profile: DefenseProfile | None = None,
    hard_constraints: set[HardConstraint] | None = None,
    budget_tier: BudgetTier | None = None,
    complexity_cap: ComplexityLevel | None = None,
) -> BuildIntent:
    budget = BudgetRange(tier=budget_tier) if budget_tier is not None else None
    return BuildIntent(
        damage_profile=damage_profile,
        playstyle=playstyle,
        defense_profile=defense_profile,
        hard_constraints=hard_constraints or set(),
        budget=budget,
        complexity_cap=complexity_cap,
        confidence=0.85,
        raw_input="test query",
        parser_origin=ParserOrigin.RULE_BASED,
    )


_POOL_DPS: tuple[int, ...] = tuple(range(0, 10_000_001, 100_000))  # 101 values


# ---------------------------------------------------------------------------
# score_damage
# ---------------------------------------------------------------------------


def test_score_damage_cold_match() -> None:
    ref = _make_ref("Ice Nova")
    intent = _make_intent(damage_profile=DamageProfile.COLD)
    assert score_damage(ref, intent) == 1.0


def test_score_damage_fire_match() -> None:
    ref = _make_ref("Fireball")
    intent = _make_intent(damage_profile=DamageProfile.FIRE)
    assert score_damage(ref, intent) == 1.0


def test_score_damage_mismatch() -> None:
    ref = _make_ref("Fireball")
    intent = _make_intent(damage_profile=DamageProfile.COLD)
    assert score_damage(ref, intent) == 0.1


def test_score_damage_none_intent_neutral() -> None:
    ref = _make_ref("Ice Nova")
    intent = _make_intent(damage_profile=None)
    assert score_damage(ref, intent) == 0.5


def test_score_damage_none_skill_neutral() -> None:
    ref = _make_ref(main_skill=None)
    intent = _make_intent(damage_profile=DamageProfile.COLD)
    assert score_damage(ref, intent) == 0.5


def test_score_damage_minion_family_partial() -> None:
    # MINION_ELEMENTAL intent, ref has "Skeleton" (→ MINION_PHYSICAL keywords)
    ref = _make_ref("Summon Skeletons")
    intent = _make_intent(damage_profile=DamageProfile.MINION_ELEMENTAL)
    # "skeleton" is not in MINION_ELEMENTAL keywords but IS in _MINION_KEYWORDS
    s = score_damage(ref, intent)
    assert s == 0.6


def test_score_damage_rf_fire_dot() -> None:
    ref = _make_ref("Righteous Fire")
    intent = _make_intent(damage_profile=DamageProfile.FIRE_DOT)
    assert score_damage(ref, intent) == 1.0


# ---------------------------------------------------------------------------
# score_playstyle
# ---------------------------------------------------------------------------


def test_score_playstyle_totem_match() -> None:
    ref = _make_ref("Shockwave Totem")
    intent = _make_intent(playstyle=Playstyle.TOTEM)
    assert score_playstyle(ref, intent) == 1.0


def test_score_playstyle_minion_match() -> None:
    ref = _make_ref("Summon Skeletons")
    intent = _make_intent(playstyle=Playstyle.MINION)
    assert score_playstyle(ref, intent) == 1.0


def test_score_playstyle_ranged_match() -> None:
    ref = _make_ref("Ice Arrow")
    intent = _make_intent(playstyle=Playstyle.RANGED_ATTACK)
    assert score_playstyle(ref, intent) == 1.0


def test_score_playstyle_melee_match() -> None:
    ref = _make_ref("Cyclone")
    intent = _make_intent(playstyle=Playstyle.MELEE)
    assert score_playstyle(ref, intent) == 1.0


def test_score_playstyle_mismatch() -> None:
    ref = _make_ref("Shockwave Totem")
    intent = _make_intent(playstyle=Playstyle.MELEE)
    assert score_playstyle(ref, intent) == 0.1


def test_score_playstyle_self_cast_inferred() -> None:
    # "Fireball" has no totem/trap/minion/etc. markers → inferred self-cast
    ref = _make_ref("Fireball")
    intent = _make_intent(playstyle=Playstyle.SELF_CAST)
    assert score_playstyle(ref, intent) == 0.8


def test_score_playstyle_self_cast_wrong_if_totem() -> None:
    ref = _make_ref("Shockwave Totem")
    intent = _make_intent(playstyle=Playstyle.SELF_CAST)
    assert score_playstyle(ref, intent) == 0.2


def test_score_playstyle_none_neutral() -> None:
    ref = _make_ref("Fireball")
    assert score_playstyle(ref, _make_intent(playstyle=None)) == 0.5


# ---------------------------------------------------------------------------
# score_budget
# ---------------------------------------------------------------------------


def test_score_budget_none_neutral() -> None:
    ref = _make_ref(dps=5_000_000)
    assert score_budget(ref, _make_intent(), pool_dps_sorted=_POOL_DPS) == 0.5


def test_score_budget_league_start_prefers_low_dps() -> None:
    low_dps = _make_ref(dps=100_000)
    high_dps = _make_ref(dps=9_900_000)
    intent = _make_intent(budget_tier=BudgetTier.LEAGUE_START)
    s_low = score_budget(low_dps, intent, pool_dps_sorted=_POOL_DPS)
    s_high = score_budget(high_dps, intent, pool_dps_sorted=_POOL_DPS)
    assert s_low > s_high


def test_score_budget_mirror_prefers_high_dps() -> None:
    low_dps = _make_ref(dps=100_000)
    high_dps = _make_ref(dps=9_900_000)
    intent = _make_intent(budget_tier=BudgetTier.MIRROR)
    s_low = score_budget(low_dps, intent, pool_dps_sorted=_POOL_DPS)
    s_high = score_budget(high_dps, intent, pool_dps_sorted=_POOL_DPS)
    assert s_high > s_low


def test_score_budget_medium_constant() -> None:
    ref = _make_ref(dps=5_000_000)
    intent = _make_intent(budget_tier=BudgetTier.MEDIUM)
    assert score_budget(ref, intent, pool_dps_sorted=_POOL_DPS) == 0.6


def test_score_budget_empty_pool_neutral() -> None:
    ref = _make_ref(dps=1_000_000)
    intent = _make_intent(budget_tier=BudgetTier.LOW)
    assert score_budget(ref, intent, pool_dps_sorted=()) == 0.5


# ---------------------------------------------------------------------------
# score_defense
# ---------------------------------------------------------------------------


def test_score_defense_life_match() -> None:
    ref = _make_ref(life=5000, energy_shield=0)
    intent = _make_intent(defense_profile=DefenseProfile.LIFE)
    assert score_defense(ref, intent) == 1.0


def test_score_defense_ci_match() -> None:
    ref = _make_ref(life=1, energy_shield=8000)
    intent = _make_intent(defense_profile=DefenseProfile.CHAOS_INOCULATION)
    assert score_defense(ref, intent) == 1.0


def test_score_defense_mom_match() -> None:
    # MoM heuristic: life <= 1 and es > 0 → CI or LowLife, not MoM
    # For a real MoM character: high life, low ES, large mana (no mana in ref)
    # Refs don't expose mana, so MoM detection always falls to LIFE → mismatch
    ref = _make_ref(life=4000, energy_shield=0)
    intent = _make_intent(defense_profile=DefenseProfile.MIND_OVER_MATTER)
    # Falls to LIFE type, MoM compat = {MOM} → mismatch
    assert score_defense(ref, intent) == 0.1


def test_score_defense_none_neutral() -> None:
    ref = _make_ref(life=5000)
    assert score_defense(ref, _make_intent(defense_profile=None)) == 0.5


def test_score_defense_mismatch() -> None:
    ref = _make_ref(life=5000, energy_shield=0)
    intent = _make_intent(defense_profile=DefenseProfile.CHAOS_INOCULATION)
    assert score_defense(ref, intent) == 0.1


# ---------------------------------------------------------------------------
# score_complexity
# ---------------------------------------------------------------------------


def test_score_complexity_low_cap_simple_skill() -> None:
    ref = _make_ref("Summon Skeletons")
    intent = _make_intent(complexity_cap=ComplexityLevel.LOW)
    assert score_complexity(ref, intent) == 0.9


def test_score_complexity_low_cap_hard_skill() -> None:
    ref = _make_ref("Flicker Strike")
    intent = _make_intent(complexity_cap=ComplexityLevel.LOW)
    assert score_complexity(ref, intent) == 0.1


def test_score_complexity_high_cap_anything() -> None:
    ref = _make_ref("Flicker Strike")
    intent = _make_intent(complexity_cap=ComplexityLevel.HIGH)
    assert score_complexity(ref, intent) == 0.7


def test_score_complexity_none_neutral() -> None:
    ref = _make_ref("Flicker Strike")
    assert score_complexity(ref, _make_intent(complexity_cap=None)) == 0.5


# ---------------------------------------------------------------------------
# score_ref (composite)
# ---------------------------------------------------------------------------


def test_score_ref_total_in_range() -> None:
    ref = _make_ref("Ice Nova", life=4000, dps=2_000_000)
    intent = _make_intent(damage_profile=DamageProfile.COLD, playstyle=Playstyle.SELF_CAST)
    bd = score_ref(ref, intent, pool_dps_sorted=_POOL_DPS)
    assert isinstance(bd, ScoreBreakdown)
    assert 0.0 <= bd.total <= 1.0


def test_score_ref_weights_sum_check() -> None:
    """Manual verification that the weights used in scorer.py sum to 1.0."""
    from poe1_fob.ranking.scorer import _WEIGHTS

    assert abs(sum(_WEIGHTS.values()) - 1.0) < 1e-9


def test_score_ref_cold_build_ranks_higher_for_cold_intent() -> None:
    cold = _make_ref("Ice Nova", dps=2_000_000)
    fire = _make_ref("Fireball", dps=2_000_000)
    intent = _make_intent(damage_profile=DamageProfile.COLD)
    pool = (2_000_000, 2_000_000)
    bd_cold = score_ref(cold, intent, pool_dps_sorted=pool)
    bd_fire = score_ref(fire, intent, pool_dps_sorted=pool)
    assert bd_cold.total > bd_fire.total


# ---------------------------------------------------------------------------
# RankingEngine.filter_hard_constraints
# ---------------------------------------------------------------------------


def test_filter_no_constraint_passes_all() -> None:
    refs = [_make_ref("Fireball"), _make_ref("Summon Skeletons")]
    engine = RankingEngine()
    result = engine.filter_hard_constraints(refs, _make_intent())
    assert len(result) == 2


def test_filter_no_minion_removes_summon() -> None:
    summon = _make_ref("Summon Skeletons")
    fire = _make_ref("Fireball")
    intent = _make_intent(hard_constraints={HardConstraint.NO_MINION})
    result = RankingEngine().filter_hard_constraints([summon, fire], intent)
    assert len(result) == 1
    assert result[0].main_skill == "Fireball"


def test_filter_no_melee_removes_cyclone() -> None:
    melee = _make_ref("Cyclone")
    ranged = _make_ref("Ice Arrow")
    intent = _make_intent(hard_constraints={HardConstraint.NO_MELEE})
    result = RankingEngine().filter_hard_constraints([melee, ranged], intent)
    assert len(result) == 1
    assert result[0].main_skill == "Ice Arrow"


def test_filter_no_totem_removes_totem() -> None:
    totem = _make_ref("Shockwave Totem")
    caster = _make_ref("Fireball")
    intent = _make_intent(hard_constraints={HardConstraint.NO_TOTEM})
    result = RankingEngine().filter_hard_constraints([totem, caster], intent)
    assert len(result) == 1


def test_filter_no_trap_mine_removes_trap() -> None:
    trap = _make_ref("Lightning Trap")
    other = _make_ref("Ice Nova")
    intent = _make_intent(hard_constraints={HardConstraint.NO_TRAP_MINE})
    result = RankingEngine().filter_hard_constraints([trap, other], intent)
    assert len(result) == 1


def test_filter_no_rf_removes_rf() -> None:
    rf = _make_ref("Righteous Fire")
    other = _make_ref("Fireball")
    intent = _make_intent(hard_constraints={HardConstraint.NO_RF})
    result = RankingEngine().filter_hard_constraints([rf, other], intent)
    assert len(result) == 1


def test_filter_no_ci_removes_ci_build() -> None:
    ci = _make_ref("Ice Nova", life=1, energy_shield=8000)
    life = _make_ref("Ice Nova", life=5000, energy_shield=0)
    intent = _make_intent(hard_constraints={HardConstraint.NO_CI})
    result = RankingEngine().filter_hard_constraints([ci, life], intent)
    assert len(result) == 1
    assert result[0].life == 5000


def test_filter_no_low_life() -> None:
    low = _make_ref("Fireball", life=30, energy_shield=5000)
    normal = _make_ref("Fireball", life=4000, energy_shield=0)
    intent = _make_intent(hard_constraints={HardConstraint.NO_LOW_LIFE})
    result = RankingEngine().filter_hard_constraints([low, normal], intent)
    assert len(result) == 1
    assert result[0].life == 4000


def test_filter_all_removed_returns_empty() -> None:
    refs = [_make_ref("Summon Skeletons"), _make_ref("Summon Raging Spirit")]
    intent = _make_intent(hard_constraints={HardConstraint.NO_MINION})
    assert RankingEngine().filter_hard_constraints(refs, intent) == []


# ---------------------------------------------------------------------------
# RankingEngine.rank
# ---------------------------------------------------------------------------


def test_rank_returns_sorted_descending() -> None:
    # cold build should rank above fire build for cold intent
    refs = [_make_ref("Fireball"), _make_ref("Ice Nova"), _make_ref("Arc")]
    intent = _make_intent(damage_profile=DamageProfile.COLD)
    ranked = RankingEngine().rank(intent, refs, top_n=3)
    totals = [r.score.total for r in ranked]
    assert totals == sorted(totals, reverse=True)


def test_rank_top_n_respected() -> None:
    refs = [_make_ref(f"Skill{i}") for i in range(20)]
    intent = _make_intent()
    ranked = RankingEngine().rank(intent, refs, top_n=5)
    assert len(ranked) == 5


def test_rank_rank_field_sequential() -> None:
    refs = [_make_ref("Fireball"), _make_ref("Ice Nova"), _make_ref("Arc")]
    ranked = RankingEngine().rank(_make_intent(), refs, top_n=3)
    assert [r.rank for r in ranked] == [1, 2, 3]


def test_rank_empty_refs_returns_empty() -> None:
    assert RankingEngine().rank(_make_intent(), [], top_n=10) == []


def test_rank_all_filtered_returns_empty() -> None:
    refs = [_make_ref("Summon Skeletons")]
    intent = _make_intent(hard_constraints={HardConstraint.NO_MINION})
    assert RankingEngine().rank(intent, refs, top_n=10) == []


def test_rank_result_type() -> None:
    refs = [_make_ref("Fireball")]
    ranked = RankingEngine().rank(_make_intent(), refs, top_n=1)
    assert len(ranked) == 1
    assert isinstance(ranked[0], RankedBuild)
    assert isinstance(ranked[0].score, ScoreBreakdown)
    assert ranked[0].ref.main_skill == "Fireball"


def test_rank_top_n_larger_than_candidates() -> None:
    refs = [_make_ref("Fireball"), _make_ref("Ice Nova")]
    ranked = RankingEngine().rank(_make_intent(), refs, top_n=50)
    assert len(ranked) == 2


def test_rank_cold_build_first_for_cold_intent() -> None:
    refs = [_make_ref("Fireball", dps=5_000_000), _make_ref("Ice Nova", dps=5_000_000)]
    intent = _make_intent(damage_profile=DamageProfile.COLD)
    ranked = RankingEngine().rank(intent, refs, top_n=2)
    assert ranked[0].ref.main_skill == "Ice Nova"
