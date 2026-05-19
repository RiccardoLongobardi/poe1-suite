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
- **Step 33 (Visual polish batch 1) DONE 2026-05-18** — `ParticleCanvas` ember field; `.vs-rarity` hover glow on all gear items (per-rarity PoE colour); `useCountUp` on Analyze KPIs; `.vs-skeleton*` ember loaders. ✅
- **Step 34 (Visual polish batch 2) DONE 2026-05-19** — lightweight route fade (CSS; see §7 for why View Transitions API was deferred, not abandoned), unique-item poe.ninja price badges, keyboard shortcuts overlay (`?`), toast redesign. ✅
- **Step 35 (Visual polish batch 3) DONE 2026-05-19** — 2/3 shipped: Analyze item hover+pin popover (`GearCard`) + header logo ember pulse. Finder virtual list dropped (≤50 items, variable-height cards). ✅
- **Step 36 (View Transitions API) DONE 2026-05-19** — only Layer 3a (Finder skill-filter micro-transition) shipped. Layer 1 (route cross-fade) was implemented then **reverted the same day** — wrapping navigation in `startViewTransition` snapshots the whole DOM per page switch and made navigation feel sluggish. Route changes keep the Step 34 CSS fade. **Do not retry route-level View Transitions.** ✅
- **Step 37 (Theorycrafter — design phase) DONE 2026-05-19** — analysis-only. `docs/THEORYCRAFTER_DESIGN.md` written: feasibility per pillar, data inventory, architecture (new `poe1_fob.theory` subpackage + `/theorycrafter` route), rollout (Steps 38–41), 6 open questions for Riccardo. **No implementation until the §5 open questions are answered.**

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

- <https://fob-ten.vercel.app> — `/finder`, `/analyze`, `/planner`.

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

- **Step 38 — Theorycrafter: Build Generator (rule-based).** Riccardo answered the §5 open questions (2026-05-19) — see §7. Scope is now narrowed: the **only** immediate Theorycrafter work is the Build Generator (Pillar 1), **rule-based** (no LLM). New `/theorycrafter` route confirmed. Loot Filter, Atlas Strategy and the scarab table are postponed. The Item & Modifier Browser, when built, is the *full* version (affix pools + ranges).

### CANDIDATE FUTURE WORK

- **Theorycrafter — Item & Modifier Browser (full version)** — affix pools + numeric ranges; needs the slimmed RePoE mods vendor file. Deferred — not the current focus.
- **Theorycrafter — Item Filter Generator** — postponed by Riccardo.
- **Theorycrafter — Atlas Strategy Generator** + curated scarab table — postponed by Riccardo.
- **Build Generator — LLM rationale layer** — future enhancement; has a per-call Anthropic cost. Rule-based first.
- **Chatbot in-app** — conversational assistant embedded in the shell. Intent: answer PoE questions, help with build decisions, guide the user through FOB features. Implementation approach TBD (depends on Theorycrafter outcome — they may share a backend AI layer).
- Build generator (superseded by Theorycrafter — same scope, renamed)
- Atlas x build generator (superseded by Theorycrafter)
- Item filter generator (superseded by Theorycrafter)

### DONE

- [x] **Step 37 — Theorycrafter design & architecture analysis** (2026-05-19, Prompt 024) — analysis-only, no code. `docs/THEORYCRAFTER_DESIGN.md`: 4-pillar feasibility, data inventory, `poe1_fob.theory` subpackage architecture, Steps 38–41 rollout, 6 open questions.
- [x] **Step 36 — View Transitions API** (2026-05-19, Prompt 023) — only Layer 3a shipped (Finder skill-filter micro-transition via the `useViewTransition` hook). Layer 1 route cross-fade was implemented then **reverted same-day**: `startViewTransition` + `flushSync` snapshots the whole DOM on every page switch (worse with lazy routes) — navigation felt sluggish. Route changes keep the Step 34 keyed CSS fade. Layers 2 / 3b / 3c never implemented (no BuildCard→Analyze route; hover-driven `GearCard` popover; portal `<Modal>`s). Frontend-only, 714 tests / 124 mypy.
- [x] **Step 35 — Visual polish batch 3** (2026-05-19, Prompt 022) — 2/3 changes. `GearCard` (Analyze): hover pops item details panel, click pins it open (one pinned at a time). Header `IconSparkles` ember pulse (opacity 0.55→1 + scale + bright glow). **Finder virtual list dropped** — ≤50 items, variable-height cards. Frontend-only, 714 tests.
- [x] **Bugfix — Trade dialog: decimal stat-filter min** (2026-05-19) — `Math.round` on strictness-computed min. Frontend-only.
- [x] **Bugfix — Trade dialog: implicit mods + route transition stutter** (2026-05-19) — domain-aware resolver; CSS fade replaces View Transitions API. Gate: 714/124.
- [x] **Step 34 — Visual polish batch 2** (2026-05-19, Prompt 021) — route fade; price badges (uniques); keyboard shortcuts; toast restyle. 713/121.
- [x] **Bugfix — Trade dialog: unique name search + Instant Buyout + count mods** (2026-05-18). 713/121.
- [x] **Step 33 — Visual polish batch 1** (2026-05-18, Prompt 020) — particles, rarity glow, KPI count-up, ember skeletons. 713/121.
- [x] **Step 32 — Trade dialog: full GGG stat DB + all mods** (2026-05-18). 706/123.
- [x] **Step 31 — poe.ninja-style Trade-search dialog** (2026-05-18). 706/121.
- [x] **Steps 25–30** — Trade redirect pipeline (prefilled GGG Trade URLs via backend POST). ✅
- [x] **Step 24 — Finder result-list polish** (2026-05-18, Prompt 014). ✅
- [x] **Steps 1–23** — See `CLAUDE.md`. ✅

### REJECTED / OBSOLETE

- ~~PostgreSQL data layer~~ → diskcache + poe.ninja.
- ~~poedb.tw scraping~~ → vendored JSON.
- ~~Server-side GGG Trade~~ → client-side redirect.
- ~~Hand-curated PROGRESSION registries~~ → dynamic synthesis (Steps 16-19).
- ~~New BuildTemplate subclasses per skill~~ → 49 templates frozen; stage data is dynamic.

---

## 7. Decision log

Reverse-chronological.

- **2026-05-19** — *Theorycrafter rollout narrowed (Riccardo's answers to the §5 open questions).* (1) Build Generator is **rule-based** — no LLM now; an LLM rationale layer is a future enhancement (it has a per-call cost). (2) Item Filter Generator: **postponed**. (3) Atlas Strategy + atlas-tree vendoring: **postponed**. (4) Item & Modifier Browser: when built, do the **full** version (affix pools + ranges). (5) Scarab/sextant curated table: **postponed**. (6) Route `/theorycrafter` **confirmed**. → The only active Theorycrafter work is **Step 38 — Build Generator (rule-based)**; the doc's 4-step rollout is superseded by this single-focus order.
- **2026-05-19** — *Theorycrafter scoped as next major feature.* Four backlog items (build generator, atlas x build generator, item filter generator + trade redirect already done) consolidated into one product feature called **Theorycrafter** — a `/theorycrafter` route covering full theorycrafting: build-from-scratch generator, 3.28 item/modifier browser, atlas strategy per build, item filter generator. Prompt 024 (design & architecture) must run before any implementation.
- **2026-05-19** — *Chatbot in-app added as candidate backlog.* Conversational PoE assistant embedded in the shell. Approach TBD — may share backend layer with Theorycrafter's AI components.
- **2026-05-19** — *View Transitions API: route-level use rejected for good (Step 36 revert).* Layer 1 (route cross-fade) was implemented per the approval below, then reverted the same day after QA: `document.startViewTransition` + `flushSync` snapshots the whole DOM on every navigation, which — with React lazy routes — made page switching feel sluggish vs. the plain CSS fade. The View Transitions API pays a full-page-snapshot cost for what is just an opacity fade. **Route changes permanently use the keyed `.vs-route` CSS fade.** The API is kept only for cheap in-page micro-transitions (Layer 3a — Finder skill filter). This is the second rejection (Step 34 deferred, Step 36 reverted) — do not propose route-level View Transitions again.
- **2026-05-19** — *View Transitions API: full implementation approved (Step 36).* (Superseded by the revert above — kept for context.) Three levels: (1) route cross-fade with ParticleCanvas excluded via `view-transition-name: none`; (2) shared-element transitions on named elements (gear cards, build cards, KPI numbers); (3) micro-interaction transitions on state changes (pin/unpin, expand/collapse, filter apply). React 19 `<ViewTransition>` component NOT used — verify React version first; if < 19, use the imperative `document.startViewTransition` wrapper pattern. All transitions must be progressive-enhancement: if API unavailable, fall back to the existing CSS fade. `prefers-reduced-motion` disables all transitions at the CSS level.
- **2026-05-19** — *View Transitions API: deferred, not abandoned.* (Original deferral note — superseded by the decision above.) The Step 34 attempt stuttered because `document.startViewTransition` snapshots the whole root including the always-animating `ParticleCanvas`. Correct fix: `view-transition-name: none` on the canvas element before `startViewTransition`.
- **2026-05-19** — *Step 35 virtualization dropped.* Finder list ≤50 items with variable-height cards — react-window over-engineering.
- **2026-05-18** — *Visual polish roadmap: three batches (Steps 33, 34, 35).* All frontend-only.
- **2026-05-18** — *Trade prefill via backend; `?redirect&source=` abandoned.*
- **2026-05-18** — *Zustand for cross-route state persistence.*
- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember".*
- **2026-05-14** — *Dynamic synthesis over curated templates.*
- **2026-05-14** — *No PostgreSQL, no ETL.*
- **2026-05-07** — *Backend migrated Fly.io → Render.*

---

## 8. Prompt library

Reusable templates. Self-contained — runnable today without past-chat context. When a prompt ships, move to §9.

---

*(no open prompts as of 2026-05-19 — Prompt 024 shipped, see §9)*

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
- **Old Prompt 021 (Step 34 — Visual polish batch 2)** — Shipped 2026-05-19. ✅ Route fade (CSS, View Transitions API deferred — see §7), price badges on uniques, keyboard shortcuts, toast restyle. Post-QA fixes: implicit mod domain resolution + integer min-roll filters.
- **Old Prompt 022 (Step 35 — Visual polish batch 3)** — Shipped 2026-05-19. ✅ 2/3: GearCard hover+pin popover, header logo ember pulse. Finder virtual list dropped.
- **Old Prompt 023 (Step 36 — View Transitions API)** — Shipped 2026-05-19, partially reverted same day. ✅ Only Layer 3a (Finder skill-filter micro-transition) stuck. Layer 1 (route cross-fade) was implemented then reverted — `startViewTransition` snapshots the whole DOM per navigation and made page switching sluggish. **Route-level View Transitions are now twice-rejected (Step 34 + 36) — do not retry.** Route changes use the keyed `.vs-route` CSS fade.
- **Old Prompt 024 (Step 37 — Theorycrafter design & architecture analysis)** — Shipped 2026-05-19. ✅ Analysis-only, no code. Output: `docs/THEORYCRAFTER_DESIGN.md` — 4-pillar feasibility (Build Generator / Item & Modifier Browser / Atlas Strategy / Item Filter Generator), data inventory, `poe1_fob.theory` subpackage + `/theorycrafter` route architecture, Steps 38–41 rollout, 6 open questions for Riccardo.
