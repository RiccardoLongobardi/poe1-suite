"""Build Generator — the rule-based core of Theorycrafter (Step 38).

`generate_build` takes a natural-language description of a desired build
and returns a :class:`TheoryBuildSkeleton`. The pipeline reuses the
machinery the Finder is already built on — there is **no LLM and no
hand-written build data**:

1. ``extract_intent`` — natural-language query → :class:`BuildIntent`
   (rule-based; the LLM fallback only fires if an API key is set).
2. ``SourceAggregator`` + ``RankingEngine`` — fetch the poe.ninja
   ladder, score every candidate against the intent, keep the best one.
3. ``BuildsService.get_detail`` — hydrate that ladder character to its
   full PoB export.
4. The PoB code is parsed once; the skeleton is assembled from the
   parsed snapshot (class, skill, links, uniques, tree) — verbatim, so
   the generator never invents an item or an illegal gem link.
"""

from __future__ import annotations

from poe1_builds.service import BuildsService
from poe1_core.models.enums import ItemRarity
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient
from poe1_shared.logging import get_logger

from ..gear.dynamic import classify_item
from ..intent import extract_intent
from ..planner.templates import pick_template
from ..pob import decode_export, parse_snapshot, snapshot_to_build
from ..ranking import RankingEngine, SourceAggregator
from .models import SkeletonUnique, TheoryBuildSkeleton

log = get_logger(__name__)


class TheoryError(RuntimeError):
    """Raised when no ladder build can satisfy the query."""


def _ninja_url(league: str, account: str, character: str) -> str:
    """Public poe.ninja profile URL — mirrors the frontend ``poeNinjaUrl``."""
    slug = "-".join(league.strip().lower().split())
    return f"https://poe.ninja/builds/{slug}/character/{account}/{character}"


def _fmt(n: int) -> str:
    """Italian thousands grouping — 1234567 → '1.234.567'."""
    return f"{n:,}".replace(",", ".")


def _compose_rationale(
    *,
    template_name: str,
    character: str,
    ascendancy: str | None,
    level: int,
    life: int,
    energy_shield: int,
    dps: int,
    content: tuple[str, ...],
) -> str:
    """Build a short Italian rationale from the ladder build's own numbers."""
    asc = ascendancy or "build"
    defence = (
        f"{_fmt(energy_shield)} energy shield" if energy_shield > life else f"{_fmt(life)} vita"
    )
    focus = ", ".join(content) if content else "tutti i contenuti"
    return (
        f"Scheletro {template_name} — derivato da una {asc} di livello "
        f"{level} realmente in classifica ({character}), con {defence} e "
        f"{_fmt(dps)} DPS. Adatta a: {focus}. Tutti gli oggetti e i "
        "collegamenti gemma vengono da una build reale, non sono inventati."
    )


async def generate_build(
    query: str,
    *,
    settings: Settings,
    http: HttpClient,
) -> TheoryBuildSkeleton:
    """Generate a build skeleton from a natural-language ``query``.

    Raises :class:`TheoryError` when the ladder has no build matching the
    intent (e.g. an over-constrained query).
    """
    intent = await extract_intent(query, settings=settings)

    agg = SourceAggregator(settings)
    refs = await agg.fetch_candidates(intent, http=http)
    if not refs:
        raise TheoryError("nessuna build trovata nella classifica per questa richiesta")

    ranked = RankingEngine().rank(intent, refs, top_n=1)
    if not ranked:
        raise TheoryError("nessuna build supera i vincoli della richiesta")
    top = ranked[0].ref

    builds_svc = BuildsService(http=http, league=settings.poe_league)
    full = await builds_svc.get_detail(top)

    snapshot = parse_snapshot(
        decode_export(full.path_of_building_export),
        export_code=full.path_of_building_export,
    )
    build = snapshot_to_build(snapshot, source_id=top.source_id)

    # Main skill group → core skill + support links.
    main_skill = top.main_skill or "Sconosciuta"
    support_gems: tuple[str, ...] = ()
    idx = snapshot.main_skill_group_index - 1
    if 0 <= idx < len(snapshot.skills):
        group = snapshot.skills[idx]
        actives = [g.name for g in group.gems if not g.is_support]
        supports = [g.name for g in group.gems if g.is_support]
        if actives:
            main_skill = actives[0]
        support_gems = tuple(supports + actives[1:])

    # Unique items + their budget tier.
    uniques: list[SkeletonUnique] = []
    for slot, item in snapshot.items_by_slot.items():
        if item.rarity == ItemRarity.UNIQUE and item.name:
            uniques.append(
                SkeletonUnique(
                    name=item.name,
                    slot=slot.value,
                    tier=classify_item(item),
                ),
            )
    for jewel in snapshot.jewels:
        ji = jewel.item
        if ji.rarity == ItemRarity.UNIQUE and ji.name:
            uniques.append(
                SkeletonUnique(name=ji.name, slot="Jewel", tier=classify_item(ji)),
            )

    template_name = pick_template(build).name
    content = tuple(
        cf.focus.value for cf in sorted(intent.content_focus, key=lambda c: c.weight, reverse=True)
    )

    skeleton = TheoryBuildSkeleton(
        query=query,
        character_class=full.base_class,
        ascendancy=full.ascendancy_class_name,
        main_skill=main_skill,
        support_gems=support_gems,
        level=full.level,
        key_uniques=tuple(uniques),
        keystones=tuple(k.name for k in full.key_stones),
        passive_count=len(snapshot.tree.node_ids),
        content_focus=content,
        template_name=template_name,
        rationale=_compose_rationale(
            template_name=template_name,
            character=full.name,
            ascendancy=full.ascendancy_class_name,
            level=full.level,
            life=full.defensive_stats.life,
            energy_shield=full.defensive_stats.energy_shield,
            dps=top.dps,
            content=content,
        ),
        source_account=full.account,
        source_character=full.name,
        source_url=_ninja_url(full.league, full.account, full.name),
    )

    log.info(
        "theory_generate_ok",
        query_len=len(query),
        ascendancy=skeleton.ascendancy,
        main_skill=skeleton.main_skill,
        uniques=len(skeleton.key_uniques),
        template=template_name,
    )
    return skeleton


__all__ = ["TheoryError", "generate_build"]
