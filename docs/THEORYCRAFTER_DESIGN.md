# Theorycrafter — Design & Architecture Analysis (Step 37)

> Analysis document for Prompt 024. **No code was written.** This is the
> design phase: it inventories what we have, assesses each pillar's
> feasibility, proposes an architecture, and lists the decisions
> Riccardo must make before implementation starts.
>
> Date: 2026-05-19. Author: Claude Code (analysis-only session).

---

## 0. Summary

**Theorycrafter** is a new `/theorycrafter` route — a build-from-scratch
theorycrafting tool for PoE 3.28. It differs from the existing routes:

| Route | Starting point |
|---|---|
| `/finder` | a natural-language query → ladder search |
| `/analyze` | an existing PoB code |
| `/planner` | an existing PoB code |
| **`/theorycrafter`** | **nothing — design a build de novo** |

Four pillars: Build Generator, Item & Modifier Browser, Atlas Strategy
Generator, Item Filter Generator.

**Headline finding:** two of the four pillars (Item Filter Generator,
Item & Modifier *base* browsing) are buildable today with vendored data
already in the repo. The other two need exactly **one new vendored data
file each** — an affix/modifier-pool file (Pillar 2 full version) and an
atlas passive-tree JSON (Pillar 3). The Build Generator (Pillar 1) needs
no new data but does need a design decision on LLM vs. rule-based.

Recommended rollout: **Pillar 4 → Pillar 2 → Pillar 1 → Pillar 3**, one
shippable step each.

---

## 1. Feasibility assessment per pillar

### Pillar 1 — Build Generator

Generate a complete build skeleton from a natural-language description
(class + ascendancy, 6L skill setup, key uniques per budget tier,
passive-tree milestones, atlas hint).

**What we already have:**
- `poe1_fob.intent` — natural-language → `BuildIntent` extraction, with a
  hybrid rule-based + **Anthropic Haiku tool-use** path
  (`intent/llm.py`, model `claude-haiku-4-5-20251001`). The tool-use
  scaffolding for forcing structured JSON out of the model already
  exists and is proven.
- `poe1_fob.planner.templates` — 49 `BuildTemplate` classes, 7 per class,
  with Italian descriptive rationale. These are *labels + prose*, not
  data, but they map a skill/ascendancy to a build identity.
- `poe1-builds` — poe.ninja ladder data: popular skills per ascendancy,
  stat distributions per budget tier (`poe1_builds.population`).
- `packages/fob/data/tree/3_28.json` — full passive tree (3338 nodes,
  keystones/notables flagged).
- `poe1_fob.gems.dynamic` / `poe1_fob.gear.dynamic` — already synthesize
  gem links and gear progression from a snapshot; the *substitution
  tables* and *canonical-unique* heuristics inside them are reusable.

**What is missing:**
- A *de-novo* synthesis path. Every existing synthesis (Steps 16–18)
  starts from a user's pasted PoB. Theorycrafter starts from a text
  prompt. We must produce a `BuildIntent`-like target *and then* a
  plausible endgame skeleton without a PoB.
- The cleanest source for "what a good <skill> <ascendancy> build looks
  like" is the **poe.ninja ladder** — we can pick the highest-fit ladder
  build for the parsed intent and treat *that* as the de-novo skeleton.
  This reuses `poe1-builds` + `poe1_fob.ranking` wholesale. The LLM then
  only writes the *rationale* prose, not the mechanical choices.

**Complexity: L** (≈1 week). The mechanical core is "Finder + a skeleton
formatter"; the LLM rationale layer is optional polish.

**Risk factors:**
- *LLM on the critical path.* Render free tier, 512 MB, ~30 s cold start.
  Any Anthropic call must be lazy/streamed and degrade to a rule-based
  skeleton if `ANTHROPIC_API_KEY` is unset or the call fails — exactly
  how `intent/extractor.py` already treats `intent/llm.py`.
- *De-novo quality.* A pure-LLM build skeleton can hallucinate
  non-existent uniques or illegal gem links. Anchoring on a real ladder
  build (the recommendation above) removes this risk entirely — the LLM
  never invents items, it only explains a real build.

**Recommendation:** Pillar 1 = "Finder pointed at a single best result,
reformatted as a from-scratch skeleton, with an optional LLM rationale."
No new data, no new model integration — the Haiku path already exists.

---

### Pillar 2 — Item & Modifier Browser

A searchable browser of 3.28 items and modifiers.

**What we already have:**
- `packages/fob/data/items/base_items.json` — **1034 gear bases** (dict
  keyed by name). Each entry: `drop_level`, `implicits` (implicit mod
  *names*, e.g. `ManaRegenerationImplicitAmulet2`), `inherits_from`,
  `item_class`, `requirements`, `tags`. Covers every PoB slot.
- `packages/fob/data/trade/stats.json` — **9530 GGG stat entries**, each
  mapping a normalized stat text (e.g. `# to maximum life`) to its stat
  IDs per domain (`explicit` / `implicit` / `fractured` / `crafted` /
  `crucible` / `scourge`). This is the searchable-modifier index.
- `poe1_fob.trade_stats` — `normalize_mod_text()` + `resolve_mod()`
  already turn mod text into stat IDs.

**What this supports today (the "lite" browser):**
- Browse / filter the 1034 bases by `item_class`, `tags`, `drop_level`,
  `inherits_from`, slot.
- Search the 9530 modifiers by stat text.
- Show a base's *implicit* mod names.

**What is missing for the "full" browser the spec asks for:**
- *Affix pools* — "which explicit modifiers can roll on a given base."
  `base_items.json` has no explicit affix data. `stats.json` is a flat
  searchable index with no base→mod linkage.
- *Numeric ranges* — "the numeric ranges for affixes on a given base."
  Neither file has affix value ranges or tier breakpoints.
- *Reverse lookup* — "which items can roll a given modifier."

These three all need the **same one new vendored file**: the
`repoe-fork/repoe` modifier dataset (`mods.json` + the
`item-class ↔ mod` tag-spawn-weight tables). This is the same upstream
repo CLAUDE.md already sanctions for `base_items.json`. Estimated size
3–6 MB minified — needs filtering down (released mods, drop the
`pre_commit check-added-large-files` ceiling is 5000 KB, so the slimmed
file must stay under that, like `stats.json` did).

**Complexity:** Lite browser **M** (≈2–3 days, no new data). Full browser
**L** (≈1 week, +1 vendor script + the tag-spawn-weight join logic).

**Risk factors:**
- The mod ↔ base join in RePoE is via tag spawn-weights, not a direct
  list — the join logic is non-trivial and must be unit-tested against
  known cases (e.g. "+# to maximum Life can roll on every armour base").
- File-size ceiling (5000 KB pre-commit hook). The slimmed mods file
  must be aggressively filtered.

**Recommendation:** ship the **lite browser first** (it is genuinely
useful and needs zero new data), then add the affix-pool layer as a
follow-up once the RePoE mods vendor script is validated.

---

### Pillar 3 — Atlas Strategy Generator

Given a build's content focus, suggest atlas regions, atlas keystones,
and scarab/sextant focus.

**What we already have:** *nothing atlas-specific.* The vendored
`tree/3_28.json` is the **character** passive tree — its keys are
`tree / classes / alternate_ascendancies / groups / nodes / …`. There is
no atlas passive tree, no scarab data, no sextant data in the repo.

**What is missing:**
- *Atlas passive tree JSON.* GGG publishes it the same way as the
  character tree — embedded in a `/atlas-skill-tree` page as a JS
  variable. A new `scripts/extract_atlas_tree.py` (a near-copy of
  `extract_tree_data.py`) can vendor it to
  `packages/fob/data/atlas/atlas_tree_3_28.json`. Same MIT/public-facing
  status as the character tree.
- *Scarab / sextant catalogue.* No clean JSON source. poe.ninja prices
  scarabs (we already fetch the economy), but a *strategy* recommendation
  ("run Cartography + Harvest scarabs for currency") is editorial
  knowledge, not data. This pillar's scarab/sextant layer is best done
  as a small **hand-curated mapping** of content-focus → recommended
  scarab families (a curated table — acceptable here because it is
  ~6 content archetypes, not a 7×19 build matrix; the CLAUDE.md
  "synthesis over curation" rule targets *build* data, not this).

**Complexity: L** (≈1 week — atlas tree vendor + the region/keystone
recommendation engine + a small curated scarab table).

**Risk factors:**
- Atlas tree changes meaningfully every league — re-vendor each league.
- The recommendation quality for atlas keystones is editorial; a v1 that
  only highlights *regions to prioritize* + *keystones to consider* is
  honest, a v1 that claims a precise optimal tree is over-promising.

**Recommendation:** build Pillar 3 last. It needs the most new data and
its recommendations are the most editorial/subjective.

---

### Pillar 4 — Item Filter Generator

Given a build's stat priorities, generate a NeverSink-style `.filter`
text file to download and import into PoE.

**What we already have:**
- `base_items.json` — `item_class`, `tags`, `drop_level`, rarity is
  implicit from item class. This is **everything an item filter needs**:
  filters match on Class / BaseType / Rarity / ItemLevel / sockets, all
  derivable from the bases catalogue.
- The output is a plain text file in PoE's well-documented filter
  syntax — no external API, no new data.

**What is missing:** nothing data-wise. We need only the *filter-text
generator* logic and a download affordance on the frontend.

**Complexity: S–M** (≈1–2 days). The filter grammar is small and stable;
the generator is a templating function over the build's stat priorities
+ the bases catalogue.

**Risk factors:** low. The only real one is *taste* — a generated filter
must be sane out of the box (don't hide currency, don't show white
chaff). Anchoring tier rules on the established NeverSink conventions
(strictness levels, neutral economy tiers) mitigates this.

**Recommendation:** **build Pillar 4 first.** It is the smallest, fully
offline, needs no new data, and produces an immediately tangible
artifact (a downloadable file).

---

## 2. Data inventory

Every file currently in `packages/fob/data/`:

| File | Size | Content | Serves |
|---|---|---|---|
| `items/base_items.json` | 357 KB | 1034 gear bases (dict by name): `drop_level`, `implicits` (names), `inherits_from`, `item_class`, `requirements`, `tags` | Pillar 2 (lite), Pillar 4 |
| `trade/stats.json` | 1028 KB | 9530 GGG stat entries: normalized text → stat IDs per domain (explicit/implicit/fractured/crafted/crucible/scourge) | Pillar 2 (modifier search) |
| `tree/3_28.json` | 2.8 MB | Character passive tree: 3338 nodes, 7 classes, 34 ascendancy node-groups, keystones/notables flagged, groups/sprites | Pillar 1 (tree milestones) |

**Gaps identified:**

1. **Affix-pool + ranges** (Pillar 2 full) — no file links a base to the
   explicit mods it can roll, nor the numeric ranges. → vendor a slimmed
   `repoe-fork/repoe` mods dataset.
2. **Atlas passive tree** (Pillar 3) — not present at all. → new
   `extract_atlas_tree.py` → `data/atlas/atlas_tree_3_28.json`.
3. **Scarab / sextant strategy** (Pillar 3) — no clean data source; best
   handled as a small curated content-focus table, not vendored data.
4. **Gem data** (per-level stats) — already noted as not-yet-needed in
   CLAUDE.md; Theorycrafter does not change that. The Build Generator
   reuses the user-free `gems.dynamic` projection math.

---

## 3. Architecture proposal

### 3.1 Package placement

**Recommendation: a new subpackage `poe1_fob.theory`, not a new
top-level package.**

Rationale: Pillars 1 and 3 lean heavily on code that already lives in
`poe1-fob` — `intent`, `ranking`, `planner.templates`, `tree`, `gems`,
`gear`. A new top-level package would either duplicate that or add a
circular-ish dependency. Pillars 2 and 4 are mostly new data-loading +
formatting code; they sit comfortably as `poe1_fob.theory.items` /
`poe1_fob.theory.filter`. Keeping it all under `poe1-fob` means one
router, one set of vendored data, no new `pyproject.toml`.

Proposed layout:

```
packages/fob/src/poe1_fob/theory/
  __init__.py
  models.py          ← Pydantic models (frozen, camelCase aliases)
  generator.py       ← Pillar 1: de-novo build skeleton
  items.py           ← Pillar 2: base + modifier browser/search
  atlas.py           ← Pillar 3: atlas strategy
  filter.py          ← Pillar 4: item-filter text generator
packages/fob/data/
  atlas/atlas_tree_3_28.json   ← new (Pillar 3)
  mods/mods_3_28.json          ← new, slimmed RePoE (Pillar 2 full)
scripts/
  extract_atlas_tree.py        ← new
  extract_mods.py              ← new
```

### 3.2 New FastAPI endpoints

All under the existing `/fob` router prefix (the router is already
mounted; no new `make_router` wiring needed). All responses are frozen
Pydantic models with `camelCase` aliases, matching repo convention.

| Method | Path | Input | Output |
|---|---|---|---|
| `POST` | `/fob/theory/generate` | `{query: str, budget?: str}` | `TheoryBuildSkeleton` (class, ascendancy, skill, 6L links, uniques by tier, tree milestones, atlas hint, rationale) |
| `GET` | `/fob/theory/bases` | query params: `item_class?`, `tag?`, `slot?`, `q?` | `BaseItemPage` (filtered list of bases) |
| `GET` | `/fob/theory/mods` | query params: `q`, `domain?` | `ModSearchResult` (matching stat entries + which item classes can roll them — full version only) |
| `GET` | `/fob/theory/atlas` | query params: `content_focus` | `AtlasStrategy` (regions, keystones, scarab families) |
| `POST` | `/fob/theory/filter` | `{stat_priorities: str[], strictness: str}` | `{filter_text: str}` (the `.filter` file body) |

`/fob/theory/generate` may stream (SSE) if the LLM rationale is enabled —
reuse the existing `plan/stream` SSE machinery pattern. The mechanical
skeleton can be returned immediately and the rationale streamed after.

### 3.3 Frontend

New route `/theorycrafter` in `App.tsx`, lazy-loaded like the other
heavy feature pages. New `pages/TheorycrafterPage.tsx` with a Mantine
`<Tabs>` shell — one tab per pillar:

```
TheorycrafterPage
  <Tabs>
    Tab "Genera build"   → BuildGeneratorPanel   (Pillar 1)
    Tab "Oggetti & mod"  → ItemBrowserPanel       (Pillar 2)
    Tab "Atlas"          → AtlasStrategyPanel      (Pillar 3)
    Tab "Loot filter"    → FilterGeneratorPanel    (Pillar 4)
```

- **State:** a new Zustand slice `theory` in `store/pageStore.ts`
  (cross-route persistence, same as `finder` / `analyze` / `planner`).
  Server data goes through TanStack Query (the bases/mods browser is a
  classic cached-query case).
- **i18n:** every new string bilingual via `t({ it, en })`.
- **Design system:** Void Stone & Ember tokens; the bases/mods tables
  reuse `.vs-rarity` colours and existing card styling.
- The four panels are independently shippable — the tab simply shows a
  "in arrivo" placeholder for not-yet-built pillars.

### 3.4 LLM usage

Only Pillar 1 may call an LLM, and only for **rationale prose**, never
for mechanical choices. Reuse `intent/llm.py`'s Haiku tool-use pattern
and its graceful degradation: no `ANTHROPIC_API_KEY` → rule-based
skeleton with template-derived rationale, no LLM call. The LLM call is
lazy (only when the user opens the Build Generator and submits) and
streamed, so it is never on the app's critical/cold-start path.

---

## 4. Implementation order

Four steps, one pillar each, each independently shippable:

**Step 38 — Pillar 4 (Item Filter Generator).** Smallest, fully offline,
zero new data, tangible artifact. Validates the `theory` subpackage +
the new route + the Zustand slice scaffolding with the lowest risk.

**Step 39 — Pillar 2 lite, then full (Item & Modifier Browser).** The
lite browser (bases + modifier-text search) ships on existing data. The
full browser (affix pools + ranges) follows as a sub-step once
`extract_mods.py` is written and the base↔mod join is unit-tested. The
browser is also a building block the Build Generator can link into.

**Step 40 — Pillar 1 (Build Generator).** Reuses Finder/ranking +
templates for the mechanical skeleton; optional Haiku rationale. Depends
on nothing new, but benefits from Pillar 2 existing (so generated
uniques/bases are clickable through to the browser).

**Step 41 — Pillar 3 (Atlas Strategy Generator).** Last: needs the most
new data (atlas tree vendor) and its output is the most editorial.

Rationale for this order: risk and new-data dependency both increase
monotonically, so each step de-risks the next, and the first shippable
result lands fast.

---

## 5. Open questions for Riccardo

1. **Build Generator — LLM or rule-based?** Recommendation: ladder-anchored
   mechanical skeleton (rule-based, always) + *optional* Haiku rationale
   prose. Do you want the LLM rationale at all, or is template-derived
   Italian prose enough? (LLM adds a small Anthropic cost per generate.)
2. **Item Filter — custom tier thresholds?** Should the filter generator
   expose strictness presets only (Soft / Regular / Strict, NeverSink
   style), or also let the user hand-tune tier breakpoints? Recommendation:
   presets only for v1.
3. **Atlas tree vendoring.** OK to add a 4th vendored data file
   (`atlas_tree_3_28.json`, ~2–3 MB) and a per-league re-vendor script?
   This is consistent with the existing tree/items/stats policy.
4. **Modifier browser depth.** Is the *lite* browser (browse bases +
   search modifier text) enough for v1, or is the full affix-pool +
   ranges view a hard requirement? The full version needs a new ~3–6 MB
   upstream file slimmed under the 5000 KB pre-commit ceiling.
5. **Scarab/sextant strategy.** Accept a small hand-curated content-focus
   → scarab-family table (≈6 archetypes)? There is no clean data source;
   the alternative is to drop scarab advice from Pillar 3 entirely.
6. **Route naming.** `/theorycrafter` confirmed? The nav label would be
   "Theorycrafter" (bilingual copy TBD — it is a community term, likely
   kept untranslated).

---

## 6. What NOT to build (v1 scope guard)

To prevent scope creep, Theorycrafter v1 explicitly does **not** include:

- **A live crafting simulator / crafting-cost calculator** — "spam alt
  until T1 life, cost in divines" is a separate, much larger feature.
- **A full interactive atlas tree editor** — Pillar 3 *recommends*, it
  does not render an editable atlas tree canvas.
- **A full interactive character passive-tree editor** — Pillar 1 emits
  tree *milestones* (keystones + notable clusters), not a node-by-node
  editable tree. (Tree editing is what PoB is for.)
- **PoB export from Theorycrafter** — the generated skeleton is advice,
  not a `.pob` code. (The Planner already owns PoB export from a real
  build.) This may be a v2 follow-up.
- **DPS / EHP simulation of the generated build** — Theorycrafter does
  not compute combat stats; it reuses ladder builds' *measured* stats.
- **PoE 2 support** — 3.28 (PoE 1) only, consistent with the whole repo.
- **Account / character import** — no GGG OAuth, per the standing
  data-source policy.
- **Real-time price tracking inside the browser** — the item browser may
  link out to the existing `/pricing` quote, but is not a price ticker.

---

## 7. Conclusion

Theorycrafter is feasible within the existing architecture with **no new
package, no new stack element, and exactly two new vendored data files**
(atlas tree + slimmed mods — and the mods file only for the *full*
Pillar 2). Pillars 4 and 2-lite are buildable today. The Build Generator
reuses the Finder/ranking/templates machinery and the already-proven
Haiku tool-use path, so it needs a *decision* (LLM yes/no) more than new
infrastructure. Recommended next action: confirm the open questions in
§5, then run a Step 38 prompt for Pillar 4 (Item Filter Generator).
