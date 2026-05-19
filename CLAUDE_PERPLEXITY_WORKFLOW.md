# CLAUDE_PERPLEXITY_WORKFLOW
Coordination playbook between **Perplexity** (research / design / data-source surveys) and **Claude Code** (in-repo implementation) for the `poe1-suite` mono-repo.

This file's only job is to keep the two tools in sync — what each is responsible for, what's currently open, what's been decided. The source of truth for the codebase itself remains [`CLAUDE.md`](./CLAUDE.md) (architecture, conventions, gate, lessons learned).

> **Read this AND `CLAUDE.md` before starting any session.** This file is the workflow contract; `CLAUDE.md` is the project contract.

---

## 1. Where the project actually stands (read first)

Don't trust earlier versions of this file — the section below is the authoritative snapshot. As of **2026-05-19**:

- **FOB is live in production**, free tier:
  - Frontend: <https://fob-ten.vercel.app> (Vercel, auto-deploy from `main`).
  - Backend: <https://fob-api-rtgg.onrender.com> (Render, region Frankfurt, auto-deploy from `main`).
  - Cost: **$0/month**.
- **Baseline gate**: 714 tests green / 124 mypy / ruff clean. Frontend build main 440 KB / 140 KB gzip + lazy route + `pageStore` chunks.
- **Working features (all QA-verified or post-QA fixed)**:
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19). ✅
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA. ✅
  - "Importa stage in PoB": exports a stage-specific PoB code. ✅
  - PoB Analyze → full build dashboard: character header + key stats, equipment grid with per-item tooltips, flasks, tree jewels, skill-link panel. ✅
  - Cold-start Divine Orb warmup overlay. ✅
  - Trade dialog: `TradeSearchDialog` with full GGG stat DB (~9.5k stats), name/base search, per-mod toggles + strictness slider, 5L/6L filter, Instant Buyout default, integer min-roll filters, domain-aware implicit/explicit stat resolution. ✅
- **Design system**: "Void Stone & Ember" — void-black warm backgrounds, ember-gold accent, parchment text, Cinzel/Cabinet Grotesk/Geist Mono type. Light mode: "Parchment" (warm cream + ink). Both QA-verified. ✅
- **Step 33–35, 36**: visual polish + GearCard + View Transitions Layer 3a only. ✅
- **Step 37**: `docs/THEORYCRAFTER_DESIGN.md` written (analysis-only). ✅
- **Step 38r**: `/theorycrafter` reset to clean "coming soon" stub. Finder-vs-Theorycrafter boundary permanent in `CLAUDE.md`. 714 tests / 124 mypy. ✅
- **Step 39 (Theorycrafter Build Generator v1) IN PROGRESS** — Prompt 026 drafted (see §8). True from-scratch generator using vendored 3.28 data.

If anything you read in this file or in `CLAUDE.md` contradicts the above, **the above wins**.

---

## 1bis. Where to verify the *current* state (read before any planning)

The §1 snapshot is hand-maintained — it might lag a few hours after a feature lands. Before drafting prompts, doing research, or assuming anything about the codebase, **always re-check the live sources** below.

### Repo (GitHub, branch `main`)

- **Browse the repo**: <https://github.com/RiccardoLongobardi/poe1-suite>
- **Latest commit on main**:
  ```sh
  curl -s https://api.github.com/repos/RiccardoLongobardi/poe1-suite/commits/main | jq -r '"\(.sha[0:7]) \(.commit.author.date) \(.commit.message | split("\n")[0])"'
  ```
- **Recent commit log** (last 20):
  ```sh
  curl -s 'https://api.github.com/repos/RiccardoLongobardi/poe1-suite/commits?per_page=20&sha=main' | jq -r '.[] | "\(.sha[0:7])  \(.commit.message | split("\n")[0])"'
  ```
- **Raw file at HEAD**:
  ```
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE.md
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE_PERPLEXITY_WORKFLOW.md
  ```
- **File tree at HEAD**:
  ```sh
  curl -s 'https://api.github.com/repos/RiccardoLongobardi/poe1-suite/git/trees/main?recursive=1' | jq -r '.tree[].path' | head -80
  ```

### Live backend (Render)

- **Health probe**: `curl -s https://fob-api-rtgg.onrender.com/health | jq .`
- **First request after ~15 min idle takes ~30 s** (Render free-tier cold start — the Divine Orb overlay handles this).

### Live frontend (Vercel)

- <https://fob-ten.vercel.app> — `/finder`, `/analyze`, `/planner`, `/theorycrafter` ("coming soon" stub).

---

## 2. Stack & data sources (no PostgreSQL, no ETL)

| Layer | Source | Caching | Refresh |
|---|---|---|---|
| Live economy | `poe.ninja` economy JSON | `diskcache` 15 min TTL | Per-request |
| Build ladder | `poe.ninja` builds protobuf | `diskcache` 15 min TTL | Per-request |
| Trade search | GGG `/api/trade/search` via `POST /fob/trade-url` | in-memory 8 min TTL | Backend POST works from Render; frontend opens returned URL |
| Passive tree | GGG vendored JSON | `packages/fob/data/tree/3_28.json` | Manual per league |
| Item bases | repoe-fork JSON | `packages/fob/data/items/base_items.json` | Manual per league |

Sources explicitly rejected (don't propose again): poedb.tw, GGG OAuth API for game data, brather1ng/RePoE (dead).

---

## 3. Roles

### 3.1 Perplexity — research & design

Owns: data-source surveys, algorithm design, comparative library reviews, long-form research, UI/UX design direction and design system spec.

Does NOT: edit `.py` / `.ts` / `.json` files, modify Claude Code todos, update §6 implementation status, analyse bugs or write fix strategies (that is Claude's job).

### 3.2 Claude Code — implementation

Owns: all code under `packages/` + `apps/` + `scripts/`, test changes, gate enforcement, commits + pushes, updating both `CLAUDE.md` and this file's §6 / §7. Also owns bug root-cause analysis and fix strategy.

Constraints: no `--no-verify`, no secrets, must run full gate before declaring done.

### 3.3 The user (Riccardo)

Owns: strategic direction, manual QA in PoB Community, final-call on architectural trade-offs.

---

## 4. Collaboration rules

1. `CLAUDE.md` is the contract, this file is the playbook. When they conflict, `CLAUDE.md` wins.
2. No silent re-architecture — changes to stack / data sources / public API go in §7.
3. Prompts in this file are reusable templates, self-contained, runnable today without past-chat context.
4. **GGG Trade access (corrected 2026-05-18):** the Render backend **can** reach GGG — `POST /fob/trade-url` mints prefilled search URLs and `scripts/extract_trade_stats.py` vendors `/api/trade/data/stats`. What does NOT work: a browser-side `fetch` to GGG's Trade API (CORS) and navigating the browser straight to a `pathofexile.com/api/` path (Cloudflare 403, `code 6`). GGG Trade calls go through the backend; the frontend only opens the URL the backend returns.
5. Vendor data, don't fetch at runtime.
6. **The Patch Notes page is part of every feature.** Whenever a feature/fix ships, the `RELEASES` array in `apps/shell/src/pages/PatchNotesPage.tsx` MUST be updated in the **same commit** as `CLAUDE.md` and this file — with user-facing, bilingual (`it`/`en`) copy. A step that updates the `.md` files but not the Patch Notes is not done.

---

## 5. Open questions for Perplexity

*(none as of 2026-05-19)*

---

## 6. Backlog & status

### IN PROGRESS

- **Step 39 — Theorycrafter Build Generator v1** — Prompt 026 in §8. True from-scratch generator.

### CANDIDATE FUTURE WORK

- **Theorycrafter — Item & Modifier Browser (full version)** — affix pools + numeric ranges; needs the slimmed RePoE mods vendor file. Deferred.
- **Theorycrafter — Item Filter Generator** — postponed by Riccardo.
- **Theorycrafter — Atlas Strategy Generator** + curated scarab table — postponed by Riccardo.
- **Build Generator — LLM rationale layer** — future optional enhancement (per-call cost). Only for text explanation, never for data generation.
- **Chatbot in-app** — conversational PoE assistant. Approach TBD.

### DONE

- [x] **Step 38r — Theorycrafter architectural reset** (2026-05-19, Prompt 025) — Option C: deleted ladder-anchored `poe1_fob.theory`; `/theorycrafter` = clean stub. 714 tests / 124 mypy. ✅
- [x] **Step 38 — Theorycrafter: Build Generator** (2026-05-19) ⚠️ ARCHITECTURAL DRIFT — reset by Step 38r.
- [x] **Step 37 — Theorycrafter design & architecture analysis** (2026-05-19, Prompt 024). ✅
- [x] **Step 36 — View Transitions API** (2026-05-19, Prompt 023) — Layer 3a only. Layer 1 reverted. ✅
- [x] **Step 35 — Visual polish batch 3** (2026-05-19, Prompt 022). ✅
- [x] **Bugfixes — Trade dialog** (2026-05-19). ✅
- [x] **Step 34 — Visual polish batch 2** (2026-05-19, Prompt 021). ✅
- [x] **Step 33 — Visual polish batch 1** (2026-05-18, Prompt 020). ✅
- [x] **Steps 31–32 — Trade dialog** (2026-05-18). ✅
- [x] **Steps 25–30 — Trade redirect pipeline** (2026-05-18). ✅
- [x] **Step 24 — Finder result-list polish** (2026-05-18, Prompt 014). ✅
- [x] **Steps 1–23** — See `CLAUDE.md`. ✅

### REJECTED / OBSOLETE

- ~~PostgreSQL data layer~~ → diskcache + poe.ninja.
- ~~poedb.tw scraping~~ → vendored JSON.
- ~~Hand-curated PROGRESSION registries~~ → dynamic synthesis (Steps 16-19).
- ~~New BuildTemplate subclasses per skill~~ → 49 templates frozen; stage data is dynamic.

---

## 7. Decision log

Reverse-chronological.

- **2026-05-19** — *Theorycrafter Build Generator v1 — from-scratch generation confirmed as next step (Step 39).* Perplexity-proposed architecture reviewed: rule-based deterministic planner using vendored 3.28 tree + item bases + gem data (wherever Claude finds it). LLM excluded from build data generation. Pillars 2/3/4 remain deferred per Riccardo's earlier decisions. Claude owns all data inventory decisions and architectural sub-choices for Step 39 — no open questions for Perplexity.
- **2026-05-19** — *Step 38r reset executed (Prompt 025) — Option C chosen.* Ladder-anchored `poe1_fob.theory` deleted; stub left. Finder-vs-Theorycrafter boundary permanent in `CLAUDE.md`.
- **2026-05-19** — *Step 38 architectural drift identified.* Theorycrafter ≠ Finder. From-scratch generation = rule-based + vendored 3.28 data. LLM only for optional NL intent parsing + prose rationale, never for item/gem/tree data.
- **2026-05-19** — *Theorycrafter rollout narrowed.* Build Generator rule-based; Item Filter Generator postponed; Atlas Strategy postponed; Item & Modifier Browser deferred; LLM rationale = future enhancement.
- **2026-05-19** — *View Transitions API: route-level use rejected for good.* Do not retry.
- **2026-05-18** — *Trade prefill via backend; `?redirect&source=` abandoned.*
- **2026-05-18** — *Zustand for cross-route state persistence.*
- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember".*
- **2026-05-14** — *Dynamic synthesis over curated templates. No PostgreSQL, no ETL.*
- **2026-05-07** — *Backend migrated Fly.io → Render.*

---

## 8. Prompt library

Reusable templates. Self-contained — runnable today without past-chat context. When a prompt ships, move to §9.

---

### Prompt 026 — Step 39 — Theorycrafter Build Generator v1

**Purpose:** Build the true Theorycrafter Build Generator: a rule-based, deterministic, from-scratch build skeleton generator that uses exclusively vendored 3.28 data. No ladder retrieval. No poe.ninja builds as primary source. Output is a `BuildSkeleton` the user can use to bootstrap a new character in PoB.

**Run as:** Claude Code (Opus 4.7). Touches backend + frontend. Gate required.

---

```
Read CLAUDE.md and CLAUDE_PERPLEXITY_WORKFLOW.md top-to-bottom before doing anything else.
Pay special attention to:
- §7 decision log: the Finder-vs-Theorycrafter permanent boundary.
- docs/THEORYCRAFTER_DESIGN.md: the full architectural analysis Claude Code wrote in Step 37.
- The current state of packages/fob/src/poe1_fob/ — read the directory tree before writing a line of code.

---

## Context and boundary

The repo has four routes:
- /finder        → retrieval: NL query → poe.ninja ladder → best-fit real build.
- /analyze       → paste PoB → build dashboard.
- /planner       → paste PoB → 6-stage leveling plan.
- /theorycrafter → NOTHING as input → generate a build skeleton from scratch.

The permanent rule (in CLAUDE.md, do not violate):
- Finder = ladder retrieval.
- Theorycrafter = from-scratch generation using vendored 3.28 data.
- The two must never be confused. Theorycrafter must NOT use poe.ninja ladder builds as its primary engine.

---

## Your task: Step 39 — Build Generator v1

Implement the **Theorycrafter Build Generator** as described in `docs/THEORYCRAFTER_DESIGN.md`, Pillar 1, with the architecture in §3 of that doc — but with one hard rule:

**The mechanical build skeleton (class, ascendancy, 6L gems, tree milestones, gear slots) must be generated deterministically from vendored data. The poe.ninja ladder may only be used as a secondary popularity signal (e.g. "which skill is most common for Inquisitor among current ladder builds"), never as the source of the skeleton itself.**

---

## Phase 1 — Data inventory (no code yet)

Before writing any code, read and report:

1. Does a gem/skill vendor file exist anywhere in `packages/fob/data/`? List all `.json` files in that directory tree.
2. Read `packages/fob/data/items/base_items.json` — what fields are present per base? Confirm whether it includes gear-slot mapping.
3. Read `packages/fob/data/tree/3_28.json` — confirm keystones and notables are flagged; confirm ascendancy node groups are present.
4. Inspect `poe1_fob.intent`, `poe1_fob.ranking`, and `poe1_fob.planner.templates` — summarise what is reusable for intent parsing and archetype mapping.
5. Based on (1)–(4), decide: is a new gem vendor file needed? If yes, write `scripts/extract_gems.py` to produce `packages/fob/data/gems/gems_3_28.json` from the PoB Community `src/Data/Skills/*.lua` files (available at https://github.com/PathOfBuildingCommunity/PathOfBuilding/tree/master/src/Data/Skills). If no suitable upstream source exists, fall back to a **minimal hand-curated JSON** of the 30 most-played skills in 3.28 (top skills by poe.ninja ladder share), each with: `skill_id`, `skill_name`, `tags` (e.g. `["fire", "aoe", "spell"]`), `gem_type` (active/support), and `canonical_supports` (list of up to 6 recommended support gem names for that skill). This fallback is explicitly acceptable — it is a small, stable, reviewable file, not a full data warehouse.

State your findings and decisions clearly before proceeding.

---

## Phase 2 — Backend: `poe1_fob.theory` subpackage

Implement the subpackage as specified in `docs/THEORYCRAFTER_DESIGN.md` §3.1, but only `generator.py` and `models.py` for this step (Pillar 1 only). `items.py`, `atlas.py`, and `filter.py` are future steps.

### 2.1 Pydantic models (`theory/models.py`)

```python
class GemLink(BaseModel):
    skill: str           # active skill gem name
    supports: list[str]  # up to 5 support gem names

class TreeMilestone(BaseModel):
    label: str           # e.g. "Ascendancy: Inquisitor — Instruments of Virtue"
    node_ids: list[int]  # vendored tree node IDs; may be empty if milestone is prose-only
    priority: int        # 1 = first, higher = later

class GearSlot(BaseModel):
    slot: str            # e.g. "Helmet", "Chest", "Weapon"
    recommended_bases: list[str]  # base type names from base_items.json
    priority_stats: list[str]     # e.g. ["+# to maximum life", "fire resistance"]
    budget_tier: str     # "starter" | "mid" | "endgame"

class BuildSkeleton(BaseModel):
    class_name: str
    ascendancy: str
    core_skill: str
    links: list[GemLink]
    tree_milestones: list[TreeMilestone]
    gear_slots: list[GearSlot]
    budget_tier: str
    content_focus: str
    rationale_it: str
    rationale_en: str
    pob_import_hint: str  # short Italian/English hint: "Apri PoB, nuova build, seleziona [class], aggiungi questi nodi..."
```

All models: frozen, camelCase aliases via `model_config = ConfigDict(populate_by_name=True)`, matching repo convention.

### 2.2 Generator (`theory/generator.py`)

The generation pipeline:

```
Input: query (str), budget_tier? (str), content_focus? (str)

1. Intent extraction
   - Reuse poe1_fob.intent.extractor.extract_intent() to parse query → BuildIntent.
   - This already handles class hints, skill hints, budget proxy via poe.ninja stats.
   - Do NOT add an LLM call here. Rule-based only for v1.

2. Archetype resolution
   - Map (class, ascendancy, skill_family) to the best matching archetype.
   - Use poe1_fob.planner.templates.TEMPLATES (49 entries) as archetype catalogue.
   - Use poe.ninja ladder popularity signal only to break ties (e.g. two equally valid templates for Inquisitor → pick the one whose skill appears most often in ladder builds).
   - Never use a specific ladder build as the skeleton source.

3. Gem link generation
   - From the gem data decided in Phase 1 (vendored file or hand-curated fallback).
   - Produce one GemLink per active 6L. For builds with two setups (e.g. Cyclone + Fortify), emit two GemLinks.
   - canonical_supports from gem data = the primary source. Populate node_ids from tree data for keystone/notable support requirements if relevant.

4. Tree milestone generation
   - From packages/fob/data/tree/3_28.json.
   - Milestones are: (a) starting area nodes relevant to archetype, (b) major keystones (Elemental Overload, Acrobatics, etc.) flagged in the tree, (c) ascendancy node names and their node_ids, (d) 3–4 notable cluster recommendations by name.
   - Sort by priority (start area → early notables → keystones → ascendancy).
   - If a node_id lookup fails, emit milestone with empty node_ids and a prose label — never crash.

5. Gear slot generation
   - From packages/fob/data/items/base_items.json.
   - For each gear slot relevant to the archetype, select recommended base types filtered by item_class + tags appropriate to the build (e.g. ES bases for low-life, armour bases for melee).
   - priority_stats per slot: derive from archetype damage type + defence archetype (life/ES/ward). Use well-known PoE priority-stat conventions per slot (these are stable knowledge, not per-build data).
   - budget_tier: "starter" → rare self-found bases; "mid" → trade-accessible rares; "endgame" → top-tier uniques where applicable (name them only if they exist in base_items.json or are poe.ninja-confirmed uniques).

6. Rationale generation
   - Rule-based v1: use poe1_fob.planner.templates to pull the Italian rationale prose already written per template (it exists! use it).
   - Translate / extend programmatically for the English version.
   - pob_import_hint: generate a short bilingual string "Apri PoB → Nuova build → Seleziona [Classe] > [Ascendancy] → aggiungi nodi [milestone labels]". English equivalent.
   - Do NOT call Anthropic API in v1. The LLM rationale layer is a future enhancement.
```

### 2.3 FastAPI endpoint

Add to the existing `/fob` router:

```python
POST /fob/theory/generate
Body: { "query": str, "budget_tier"?: "starter"|"mid"|"endgame", "content_focus"?: str }
Response: BuildSkeleton (JSON, not streamed — streaming is a future enhancement)
Errors: 422 if query is empty; 503 if data files are missing.
```

No SSE for v1. The response is synchronous and fast (rule-based, no LLM calls).

---

## Phase 3 — Frontend: TheorycrafterPage Build Generator panel

Replace the `/theorycrafter` "coming soon" stub with the full page.

Architecture matches `docs/THEORYCRAFTER_DESIGN.md` §3.3:

### 3.1 Page structure

```tsx
TheorycrafterPage
  <Tabs defaultValue="genera">
    <Tabs.Tab value="genera">Genera build</Tabs.Tab>
    <Tabs.Tab value="oggetti" disabled>Oggetti & mod — in arrivo</Tabs.Tab>
    <Tabs.Tab value="atlas" disabled>Atlas — in arrivo</Tabs.Tab>
    <Tabs.Tab value="filter" disabled>Loot filter — in arrivo</Tabs.Tab>
  </Tabs>
  <Tabs.Panel value="genera">
    <BuildGeneratorPanel />
  </Tabs.Panel>
```

### 3.2 BuildGeneratorPanel

```tsx
Inputs:
  - Textarea: descrivi la tua build (placeholder: "es. Elementalist con Palle di Fuoco, endgame mapping")
  - Select: Budget (Starter / Mid / Endgame), default Mid
  - Select: Focus (Mapping / Bossing / All content / League mechanic), default Mapping
  - Button: "Genera" (primary, ember-gold, disabled while loading)

Output (only shown after successful generation):
  - Header card: class + ascendancy badge, core skill, budget tier chip, content focus chip
  - GemLinkCard: shows each 6L with active gem + support gems. Use .vs-rarity colour for active gem.
  - TreeMilestoneList: ordered list of milestones; node_ids shown as small code chips; "apri in PoB" hint at bottom.
  - GearSlotGrid: one card per slot. Recommended bases listed. Priority stats as small badge chips.
  - Rationale accordion: collapsible, shows rationale_it by default, rationale_en toggle.
  - PoBImportHint: a copyable text box with the pob_import_hint string.

State: store in Zustand `theory.generator` slice (query, budget_tier, content_focus, result, isLoading, error). Persist query and filters; clear result on new query submission.

Error states:
  - Empty query: inline validation (do not submit).
  - 503 (missing data): toast "Dati non disponibili, riprova tra poco".
  - Generic error: inline error card (not a toast — this is a primary-action failure).

All strings bilingual via t({ it, en }). Every new i18n key added.
```

---

## Phase 4 — Tests

Add to `packages/fob/tests/`:

1. `test_theory_generator.py`:
   - `test_generate_returns_build_skeleton` — smoke test: valid query → BuildSkeleton with non-empty fields.
   - `test_generate_known_archetype` — "Elementalist Fireball mapping" → class_name="Witch", ascendancy="Elementalist", core_skill contains "Fire".
   - `test_generate_unknown_query_fallback` — garbage query → still returns a BuildSkeleton (fallback archetype, no crash).
   - `test_generate_all_budget_tiers` — same query × 3 budget tiers → gear_slots differ by budget_tier.
   - `test_generate_gear_slots_use_known_bases` — every recommended_base in every GearSlot must exist in base_items.json.
   - `test_generate_tree_milestones_have_priority_order` — milestones sorted by priority ascending.
2. `test_theory_endpoint.py`:
   - `test_post_theory_generate_200` — valid body → 200, camelCase response.
   - `test_post_theory_generate_422_empty_query` — `{"query": ""}` → 422.

Minimum 8 new tests. All must pass in the gate.

---

## Phase 5 — Documentation + Patch Notes

Update in the **same commit** as code:

**CLAUDE.md**: Update baseline gate count (tests + mypy).

**CLAUDE_PERPLEXITY_WORKFLOW.md**:
- §1 snapshot: mark Step 39 DONE with gate numbers.
- §6: move Step 39 from IN PROGRESS to DONE.
- §7: add entry for today's Step 39 decisions (which data source was chosen for gems, which archetype mapping strategy was used).
- §8 prompt library: this prompt is no longer open — move to §9.

**PatchNotesPage.tsx** RELEASES array — bilingual:
- Italian: "Theorycrafter — Genera build: descrivi in italiano la build che vuoi giocare e ricevi uno scheletro completo con skill setup, pietre passive e slot oggetti."
- English: "Theorycrafter — Build Generator: describe your build idea in natural language and get a complete skeleton with skill setup, passive milestones, and gear slots."

---

## Phase 6 — Gate

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

All must pass. Report final test / mypy / ruff counts.

---

## Hard constraints

- Theorycrafter must NOT use poe.ninja ladder builds as the skeleton source. poe.ninja may be used only for popularity tie-breaking.
- LLM: no Anthropic API calls in v1. Rule-based only.
- No poedb.tw, no GGG OAuth, no PostgreSQL.
- Render free tier: 512 MB RAM — no heavy model loading on startup. All data files are loaded lazily on first request and cached in-process.
- No streaming in v1. POST /fob/theory/generate is synchronous.
- The gate must pass before declaring done.
- Patch Notes and .md files must be updated in the same commit as the code.
```

---

## 9. Prompt archive

Closed prompts kept for context. Don't run these.

- **Old Prompt 001–009** — Rejected or shipped 2026-05-14/15. See git history.
- **Old Prompt 010 (Step 22a — Void Stone & Ember design system)** — Shipped 2026-05-15. ✅
- **Old Prompt 011 (Step 22b — Finder page redesign)** — Shipped 2026-05-15. ✅
- **Old Prompt 012 (Step 22c — Planner timeline + Analyze polish)** — Shipped 2026-05-15. ✅
- **Old Prompt 013 (Step 23 — Parchment light mode)** — Shipped 2026-05-15. ✅
- **Old Prompt 014 (Step 24 — Finder result-list polish)** — Shipped 2026-05-18. ✅
- **Old Prompt 015 (Step 25 — Trade redirect on Planner gear + Analyze equipment)** — Shipped 2026-05-18. ✅
- **Old Prompt 016 (Step 26 — Route-level code-splitting)** — Shipped 2026-05-18. ✅
- **Old Prompt 017 (Step 27 — QA batch fixes + Zustand state persistence)** — Shipped 2026-05-18. ✅
- **Old Prompt 018 (Step 28 — Trade redirect v2: prefilled URLs)** — Shipped 2026-05-18. ✅ QA failed → fixed in Prompt 019.
- **Old Prompt 019 (Step 29 — Trade redirect 403 fix + Planner input parity)** — Shipped 2026-05-18. ✅
- **Old Prompt 020 (Step 33 — Visual polish batch 1)** — Shipped 2026-05-18. ✅
- **Old Prompt 021 (Step 34 — Visual polish batch 2)** — Shipped 2026-05-19. ✅
- **Old Prompt 022 (Step 35 — Visual polish batch 3)** — Shipped 2026-05-19. ✅
- **Old Prompt 023 (Step 36 — View Transitions API)** — Shipped 2026-05-19, partially reverted. ✅
- **Old Prompt 024 (Step 37 — Theorycrafter design & architecture analysis)** — Shipped 2026-05-19. ✅
- **Old Prompt 025 (Step 38r — Theorycrafter architectural reset)** — Shipped 2026-05-19. ✅ Option C chosen.
