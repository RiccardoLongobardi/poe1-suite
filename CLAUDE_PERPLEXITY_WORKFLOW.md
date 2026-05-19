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
- **Step 35 (Visual polish batch 3) DONE 2026-05-19** — 2/3 shipped: Analyze item inline expansion + header logo pulse. Finder virtual list dropped (≤50 items, variable-height cards — over-engineering). See §6.

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

- *(nothing)*

### CANDIDATE FUTURE WORK

- **View Transitions API** — not abandoned. The Step 34 attempt stuttered because `document.startViewTransition` snapshotted the always-animating `ParticleCanvas`. Fix path when revisiting: apply `view-transition-name: none` (or `contain: paint`) to the canvas element so the API excludes it from the snapshot. Browser support is solid (Chrome 111+, Firefox 130+, Safari 18+). Pick this up after Step 35 if the polish work continues.
- Trade redirect (backlog item, tracked)
- Build generator (backlog item, tracked)
- Atlas x build generator (backlog item, tracked)
- Item filter generator (backlog item, tracked)

### DONE

- [x] **Step 35 — Visual polish batch 3** (2026-05-19, Prompt 022) — 2/3 changes: `ExpandableGearCard` (Analyze gear cells expand inline on click — replaces `GearCell` + the hover tooltip); header `IconSparkles` ember pulse. **Finder virtual list dropped** — result list capped at 50, `BuildCard`s have variable height (expand-on-click) which fights `react-window`; over-engineering for ~zero gain (Riccardo confirmed). Frontend-only, 714 tests.
- [x] **Bugfix — Trade dialog: decimal stat-filter min** (2026-05-19) — `Math.round` applied to strictness-computed min before sending to GGG; PoE rolls are integers. Frontend-only.
- [x] **Bugfix — Trade dialog: implicit mods + route transition stutter** (2026-05-19) — resolver made domain-aware (`{normalized: {domain: stat_id}}`); implicit mods now resolve to implicit-domain stat id instead of always picking explicit. Route transition View Transitions API replaced with lightweight CSS opacity fade (stutter caused by particle canvas snapshot). Gate: 714 tests / 124 mypy.
- [x] **Step 34 — Visual polish batch 2** (2026-05-19, Prompt 021) — lightweight route fade; `PriceBadge` + `usePriceHint` (unique gear cells/rows, rares excluded); `KeyboardShortcutsModal` with global `keydown` handler (`G F/A/P/N`, `T`, `L`, `?`); Mantine toast restyle in Void Stone & Ember palette. Frontend-only. 713 tests / 121 mypy at initial ship.
- [x] **Bugfix — Trade dialog: unique name search + Instant Buyout + count mods** (2026-05-18) — name + type sent together; `status_option = "securable"`; `difflib` fuzzy fallback for count mods. 713 tests / 121 mypy.
- [x] **Step 33 — Visual polish batch 1** (2026-05-18, Prompt 020) — `ParticleCanvas` (72 particles, mouse-reactive, scheme-aware); `.vs-rarity` hover glow on all gear items per PoE rarity colour; `useCountUp` on Analyze KPIs; `.vs-skeleton*` ember loaders. Frontend-only. 713 tests / 121 mypy.
- [x] **Step 32 — Trade dialog: full GGG stat DB + all mods** (2026-05-18) — `scripts/extract_trade_stats.py` → `stats.json` (~9.5k stats); `poe1_fob.trade_stats` resolver; dialog lists all mods, `size="xl"`. 706 tests / 123 mypy / 318 format.
- [x] **Step 31 — poe.ninja-style Trade-search dialog** (2026-05-18) — `TradeSearchDialog`: name/base `SegmentedControl`, per-mod toggle + strictness slider, 5L/6L; `/fob/extract-trade-mods` + `/fob/trade-url` extended with `stats[]` + `min_links`. 706 tests / 121 mypy / 316 format.
- [x] **Step 30 — Trade prefill via backend + Planner collapsed-input fix** (2026-05-18) ✅
- [x] **Step 29 — Trade redirect 403 fix + Planner input parity** (2026-05-18, Prompt 019) ✅
- [x] **Step 28 — Trade redirect v2: prefilled URLs** (2026-05-18, Prompt 018) — QA failed → fixed in Step 29.
- [x] **Step 27 — QA batch fixes + Zustand state persistence** (2026-05-18, Prompt 017) ✅
- [x] **Step 26 — Route-level code-splitting** (2026-05-18, Prompt 016) ✅
- [x] **Step 25 — Trade redirect on Planner gear + Analyze equipment** (2026-05-18, Prompt 015) ✅
- [x] **Step 24 — Finder result-list polish** (2026-05-18, Prompt 014) ✅
- [x] **Bugfix — Finder result cards muddy grey in light mode** (2026-05-17) ✅
- [x] **English support + uniform input font** (2026-05-15) ✅
- [x] **Steps 1-23** — See `CLAUDE.md` for full detail. ✅

### REJECTED / OBSOLETE

- ~~PostgreSQL data layer~~ → diskcache + poe.ninja.
- ~~poedb.tw scraping~~ → vendored JSON.
- ~~Server-side GGG Trade~~ → client-side redirect.
- ~~Hand-curated PROGRESSION registries~~ → dynamic synthesis (Steps 16-19).
- ~~New BuildTemplate subclasses per skill~~ → 49 templates frozen; stage data is dynamic.

---

## 7. Decision log

Reverse-chronological.

- **2026-05-19** — *View Transitions API: deferred, not abandoned.* The API is well-supported across evergreen browsers (Chrome 111+, Firefox 130+, Safari 18+) and remains the right long-term approach for route transitions. In Step 34 it was replaced with a plain CSS fade because `document.startViewTransition` snapshots the whole root including the always-animating `ParticleCanvas`, causing visible stutter. The correct fix when revisiting: add `view-transition-name: none` (or `contain: paint`) to the canvas element before calling `startViewTransition`, excluding it from the snapshot. This is a targeted tweak, not a rearchitecture. **Do not treat View Transitions API as rejected** — pick it back up in a future polish pass.
- **2026-05-19** — *Step 35 virtualization direction: `react-window` preferred if adding a dep is acceptable; otherwise a small in-repo windowed list.* `react-window` is the standard lightweight option for efficient large-list rendering in React. If the repo prefers zero new deps, implement a minimal custom windowing component instead — keep it simple and obvious.
- **2026-05-18** — *Visual polish roadmap agreed.* Three batches: Step 33 (particles + shimmer + count-up + skeletons), Step 34 (route transitions + price overlay badges + keyboard shortcuts + toast redesign), Step 35 (item card expand, virtual list, logo animation). All frontend-only.
- **2026-05-18** — *Trade prefill done via the backend; `?redirect&source=` abandoned.*
- **2026-05-18** — *Zustand chosen for cross-route state persistence.*
- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember" theme.*
- **2026-05-14** — *Dynamic synthesis over curated templates.*
- **2026-05-14** — *No PostgreSQL, no ETL.* diskcache model.
- **2026-05-07** — *Backend migrated Fly.io → Render.*

---

## 8. Prompt library

Reusable templates. Self-contained — runnable today without past-chat context. When a prompt ships, move to §9.

*(no active prompts — Prompt 022 shipped, see §9)*

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
- **Old Prompt 022 (Step 35 — Visual polish batch 3)** — Shipped 2026-05-19. ✅ 2/3: `ExpandableGearCard` inline expansion on Analyze, header logo ember pulse. Finder virtual list dropped (≤50 items, variable-height cards).
