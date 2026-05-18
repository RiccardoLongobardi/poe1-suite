# CLAUDE_PERPLEXITY_WORKFLOW

Coordination playbook between **Perplexity** (research / design / data-source surveys) and **Claude Code** (in-repo implementation) for the `poe1-suite` mono-repo.

This file's only job is to keep the two tools in sync — what each is responsible for, what's currently open, what's been decided. The source of truth for the codebase itself remains [`CLAUDE.md`](./CLAUDE.md) (architecture, conventions, gate, lessons learned).

> **Read this AND `CLAUDE.md` before starting any session.** This file is the workflow contract; `CLAUDE.md` is the project contract.

---

## 1. Where the project actually stands (read first)

Don't trust earlier versions of this file — the section below is the authoritative snapshot. As of **2026-05-18**:

- **FOB is live in production**, free tier:
  - Frontend: <https://fob-ten.vercel.app> (Vercel, auto-deploy from `main`).
  - Backend: <https://fob-api-rtgg.onrender.com> (Render, region Frankfurt, auto-deploy from `main`).
  - Cost: **$0/month**.
- **Baseline gate**: 706 tests green / 123 mypy / 318 ruff-format files. Frontend build main 440 KB / 140 KB gzip + lazy route + `pageStore` chunks.
- **Working features (all QA-verified 2026-05-18)**:
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19). ✅ QA passed.
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA. ✅ QA passed.
  - "Importa stage in PoB": exports a stage-specific PoB code. Passes through the user's real `<Items>`/`<Skills>` verbatim (only the passive tree differs per stage). ✅ QA passed.
  - PoB Analyze → full build dashboard (Step 20, done 2026-05-15): character header + key stats, equipment grid with per-item tooltips, flasks, tree jewels, skill-link panel. ✅ QA passed.
  - Cold-start Divine Orb warmup overlay (Step 21, done 2026-05-15). ✅ QA passed.
- **Design system**: "Void Stone & Ember" (Step 22, done 2026-05-15) — void-black warm backgrounds, ember-gold accent, parchment text, Cinzel/Cabinet Grotesk/Geist Mono type. ✅ QA passed.
- **Light mode**: "Parchment" theme (Step 23, done 2026-05-15) — warm cream backgrounds (`#f2ece0`), ink-on-parchment text (`#2a1f0e`), ember gold as accent only. Pairs with the Void Stone dark mode. ✅ QA passed.
- **Dynamic-synthesis pivot complete** (Steps 16/17/18/19, all done).
- **Step 27 (QA batch + Zustand state persistence) DONE 2026-05-18** — see §6.
- **Step 28/29 (client-side prefilled Trade URL) — ABANDONED.** The `?redirect&source=` GET-prefill mechanism does not exist; GGG 403s any direct navigation to a `/api/` path. Superseded by Step 30.
- **Step 30 (Trade prefill via backend + Planner collapsed-input fix) DONE 2026-05-18** — `POST /fob/trade-url` works again from Render. Planner collapsed `<Code>` no longer balloons.
- **Step 31 (poe.ninja-style Trade-search dialog) DONE 2026-05-18** — the Trade icon opens a configurable `TradeSearchDialog` (search-by name/base, per-mod toggle + strictness slider, 5L/6L). Backend: re-added `/fob/extract-trade-mods`, extended `/fob/trade-url` with `stats[]` + `min_links`.
- **Step 32 (Trade dialog: full GGG stat DB + all mods) DONE 2026-05-18** — vendored GGG's full `/api/trade/data/stats` (~9.5k stats) → `poe1_fob.trade_stats` resolver; the dialog now lists every mod of the item, bigger modal. See §6.
- **Step 33 (Visual polish batch) IN PROGRESS** — See §6 and Prompt 020 in §8.

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
| Trade search | GGG `/api/trade/search` via `POST /fob/trade-url` | in-memory 8 min TTL | Backend POST works from Render again (re-verified 2026-05-18); frontend opens the returned prefilled URL |
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
4. **GGG Trade access (corrected 2026-05-18):** the Render backend **can** reach GGG — `POST /fob/trade-url` mints prefilled search URLs and `scripts/extract_trade_stats.py` vendors `/api/trade/data/stats`. The old "Render IP blacklisted → 403" note is stale. What does NOT work: a browser-side `fetch` to GGG's Trade API (CORS) and navigating the browser straight to a `pathofexile.com/api/` path (Cloudflare 403, `code 6`). So: GGG Trade calls go through the backend (rate-limited + cached); the frontend only opens the URL the backend returns.
5. Vendor data, don't fetch at runtime.
6. **The Patch Notes page is part of every feature.** Whenever a feature/fix ships, the `RELEASES` array in `apps/shell/src/pages/PatchNotesPage.tsx` MUST be updated in the **same commit** as `CLAUDE.md` and this file — with user-facing, bilingual (`it`/`en`) copy. A step that updates the `.md` files but not the Patch Notes is not done.

---

## 5. Open questions for Perplexity

*(none as of 2026-05-18)*

---

## 6. Backlog & status

### IN PROGRESS

- **Step 33 — Visual polish batch** (Prompt 020 in §8) — Canvas particles background, unique item shimmer, KPI count-up animation, ember-style skeleton loaders.

### NEXT

- **Step 34 — Visual polish batch 2** (Prompt 021 — to be written after Step 33 QA passes): route transitions (View Transitions API), route transitions, price overlay badge on items (poe.ninja data), keyboard shortcuts overlay (`?`), toast redesign.
- **Step 35 — Visual polish batch 3** (Prompt 022 — to be written after Step 34 QA passes): item card expand/flip on Analyze, virtual list on Finder, header logo animated pulse.

### CANDIDATE FUTURE WORK

- Build generator (backlog item, tracked)
- Atlas x build generator (backlog item, tracked)
- Item filter generator (backlog item, tracked)

### DONE

- [x] **Step 32 — Trade dialog: full GGG stat DB + all mods** (2026-05-18) — Vendored GGG's `/api/trade/data/stats` (`scripts/extract_trade_stats.py` → `packages/fob/data/trade/stats.json`, ~9.5k stats). New `poe1_fob.trade_stats` resolver (`normalize_mod_text` + dict lookup). `/fob/extract-trade-mods` now returns every mod line with a nullable `stat_id` — the dialog lists *all* of an item's mods (resolved = toggleable, unresolved = dimmed) and is `size="xl"`. 706 tests / 123 mypy / 318 format.
- [x] **Step 31 — poe.ninja-style Trade-search dialog** (2026-05-18) — New `TradeSearchDialog`: search-by name/base `SegmentedControl`, per-mod toggle + 50-100% strictness slider, 5L/6L link filter; opened from every Trade icon (Planner Overview + Gear tab, Analyze equipment/flasks/jewels). Backend: re-added `POST /fob/extract-trade-mods`; `POST /fob/trade-url` extended with explicit `stats[]` + `min_links` (→ GGG `socket_filters`). 706 tests / 121 mypy / 316 format. Property filters (DPS/APS/crit) intentionally not replicated — FOB has no computed weapon stats.
- [x] **Step 30 — Trade prefill via backend + Planner collapsed-input fix** (2026-05-18) — QA fix for Steps 28/29. `openTradeSearch()` opens a blank tab synchronously, calls `POST /fob/trade-url` (re-verified working from Render — GGG returns a real `search_id`), and navigates the tab to the prefilled `/trade/search/<league>/<id>` URL; bare-page + clipboard fallback on error/429. Planner collapsed `<Code>` chip no longer balloons (`whiteSpace:nowrap` + `minWidth:0`). Frontend-only.
- [x] **Step 29 — Trade redirect 403 fix + Planner input parity** (2026-05-18, Prompt 019) — `openTradeSearch()` navigates via a programmatic `<a>` click instead of `window.open` (GGG/Cloudflare 403'd the `window.open` Referer); the Planner PoB input form now mirrors Analyze (flex `TextInput` + button in one row, Ctrl+Enter hint below, Planner controls underneath). Frontend-only.
- [x] **Step 28 — Trade redirect v2: prefilled URLs** (2026-05-18, Prompt 018) — **QA failed — GGG returns code 6 Forbidden. Fixed in Step 29.**
- [x] **Step 27 — QA batch fixes + Zustand state persistence** (2026-05-18, Prompt 017) ✅
- [x] **Step 26 — Route-level code-splitting** (2026-05-18, Prompt 016) ✅
- [x] **Step 25 — Trade redirect on Planner gear + Analyze equipment** (2026-05-18, Prompt 015) ✅
- [x] **Step 24 — Finder result-list polish** (2026-05-18, Prompt 014) ✅
- [x] **Bugfix — Finder result cards muddy grey in light mode** (2026-05-17) ✅
- [x] **English support + uniform input font** (2026-05-15) ✅
- [x] **Patch Notes page** (2026-05-15) ✅
- [x] **Step 23 — Parchment light mode** (2026-05-15) ✅
- [x] **Step 22c — Planner timeline + Analyze polish** (2026-05-15) ✅
- [x] **Step 22b — Finder page redesign** (2026-05-15) ✅
- [x] **Step 22a — Void Stone & Ember design system** (2026-05-15) ✅
- [x] **Step 21 — Divine Orb cold-start overlay** (2026-05-15) ✅
- [x] **Step 20 — Analyze page full redesign** (2026-05-15) ✅
- [x] **Steps 1-19** — See `CLAUDE.md` for full detail. ✅
- [x] **Bugfix — Finder blank page** (2026-05-15) ✅
- [x] **Bugfix — Stage export fake items + `explodeSource`** (2026-05-15) ✅

### REJECTED / OBSOLETE

- ~~PostgreSQL data layer~~ → diskcache + poe.ninja.
- ~~poedb.tw scraping~~ → vendored JSON.
- ~~Server-side GGG Trade~~ → client-side redirect.
- ~~Hand-curated PROGRESSION registries~~ → dynamic synthesis (Steps 16-19).
- ~~New BuildTemplate subclasses per skill~~ → 49 templates frozen; stage data is dynamic.

---

## 7. Decision log

Reverse-chronological.

- **2026-05-18** — *Visual polish roadmap agreed.* Three batches of frontend-only polish work decided: Step 33 (particles + shimmer + count-up + skeletons), Step 34 (route transitions + price overlay badges + keyboard shortcuts + toast redesign), Step 35 (item card expand, virtual list, logo animation). All frontend-only, no backend changes, no new npm deps beyond what already exists.

- **2026-05-18** — *Trade prefill done via the backend; `?redirect&source=` abandoned.* The client-side `?redirect&source=` GET-prefill (Steps 28/29) does not work — GGG 403s any direct browser navigation to a `/api/` path (`code 6 Forbidden`); the mechanism never existed. **`POST /fob/trade-url` on Render was re-tested live and works** — it POSTs to GGG and gets a real `search_id`. The 2026-05-14 "server-side Trade impossible / Render IP blacklisted" decision is **stale** and reversed: the backend POST is the supported path. Frontend opens a blank tab, calls `/fob/trade-url`, navigates the tab to the prefilled URL.

- **2026-05-18** — *Trade redirect `window.open()` blocked by Cloudflare (GGG code 6 Forbidden).* Fix: programmatic `<a>` element click, same pattern as poe.ninja.
- **2026-05-18** — *Zustand chosen for cross-route state persistence.*
- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember" theme.*
- **2026-05-14** — *Dynamic synthesis over curated templates.* Steps 16-19.
- **2026-05-14** — *Vendor data, don't fetch at runtime.*
- **2026-05-14** — *No PostgreSQL, no ETL.* diskcache model.
- **2026-05-07** — *Backend migrated Fly.io → Render.*

---

## 8. Prompt library

Reusable templates. Self-contained — runnable today without past-chat context. When a prompt ships, move to §9.

---

### Prompt 020 — Step 33: Visual polish batch 1 (particles, shimmer, count-up, skeletons)

**Scope**: frontend-only. No backend changes, no new npm dependencies.

**Context**: FOB uses the "Void Stone & Ember" design system — void-black warm backgrounds (`--vs-bg` / `--vs-surface-*`), ember-gold accent (`--mantine-color-ember-*`, `#c8932a` at shade 6), parchment text (`--vs-text`), Cinzel display + Cabinet Grotesk body + Geist Mono numbers. Light mode is "Parchment" (`[data-mantine-color-scheme="light"]` block in `index.css`). The design token CSS vars are in `apps/shell/src/index.css`; Mantine theme is in `apps/shell/src/theme.ts`.

The goal is to make the site feel **alive and futuristic** without breaking the existing design system. Every change must:
- Work in both dark ("Void Stone") and light ("Parchment") colour schemes.
- Respect `prefers-reduced-motion` — all animations must be disabled or reduced under that media query.
- Not regress the gate (706 tests / 123 mypy / 318 ruff-format).
- Update `PatchNotesPage.tsx` `RELEASES` array with bilingual user-facing copy in the same commit.

---

#### Change 1 — Canvas particle background

Add a subtle animated particle field as a full-viewport background layer, visible on all pages.

**Requirements**:
- A single `<ParticleCanvas>` component mounted once in `App.tsx`, rendered as a `position: fixed; inset: 0; z-index: 0; pointer-events: none` canvas element behind all content.
- Vanilla Canvas2D — no Three.js, no external library. Keep it under ~80 lines of actual code.
- **Dark mode**: 35–50 particles, ember-gold (`rgba(200, 147, 42, α)`) on void-black. Particle opacity 0.15–0.35, connection line opacity 0.08. Each particle drifts slowly (speed 0.15–0.3 px/frame); connections drawn when distance < 120px.
- **Light mode** (`window.matchMedia('(prefers-color-scheme: dark)')` and `data-mantine-color-scheme` attribute on `<html>`): same particle count but use ink-on-parchment tones (`rgba(42, 31, 14, α)`) at reduced opacity (0.06–0.12) so they don't overwhelm the cream background.
- Mouse proximity: particles within 80px of the cursor are gently pushed away (repulsion force, max 1.5 px/frame delta). Purely cosmetic — no click handlers.
- `prefers-reduced-motion`: freeze all particle movement and connections entirely (canvas stays blank/invisible).
- The component must watch for `data-mantine-color-scheme` attribute mutations on `<html>` via a `MutationObserver` and re-initialise colours without re-creating the canvas.
- Wrap in `React.memo` — no re-renders after mount.

**Files to create/edit**:
- `apps/shell/src/components/ParticleCanvas.tsx` — new component.
- `apps/shell/src/App.tsx` — mount `<ParticleCanvas />` as the first child of the root `<div>`, before `<MantineProvider>` children or inside it but before `<AppShell>`. Ensure `z-index` stacking doesn't clip app content.

---

#### Change 2 — Unique item shimmer effect

Unique items already have a brown/gold colour treatment in the equipment grid (`BuildDashboard`) and the Planner gear tab (`StageCard`). Add a CSS-only foil shimmer that scrolls diagonally across unique item cards.

**Requirements**:
- A new CSS class `.vs-unique-shimmer` in `index.css`.
- The shimmer is a `::after` pseudo-element with a `linear-gradient` at ~30° angle using ember/gold tones (`#c8932a`, `#e8b84b`, `#c8932a`) at low opacity (peak ~0.18 in dark mode, ~0.10 in light mode), animated via `background-position` from `-200%` to `200%` over 3.5 s, `ease-in-out`, infinite.
- Apply the class only to elements that already have the `data-rarity="unique"` attribute (or the equivalent rarity class used in `GearCell` / `StageGearSlot`). Check the current DOM structure before deciding where to add the class — do NOT add it to every item card blindly.
- `prefers-reduced-motion`: remove the animation, keep a static subtle gold tint via `background: linear-gradient(...)` with opacity 0.07.
- Light mode: reduce shimmer opacity by 40%.

**Files to edit**:
- `apps/shell/src/index.css` — add `.vs-unique-shimmer` keyframe + class.
- `apps/shell/src/pages/AnalyzePage.tsx` — add class to unique `GearCell` wrappers.
- `apps/shell/src/components/StageCard.tsx` — add class to unique `StageGearSlot` rows.

---

#### Change 3 — Count-up animation on KPI numbers

The Analyze page shows key stats (Life, Energy Shield, EHP, DPS, Armour, Evasion) as plain numbers. Animate them to count up from 0 to their final value when they first render.

**Requirements**:
- A small `useCountUp(target: number, duration = 800)` hook in `apps/shell/src/hooks/useCountUp.ts`.
  - Uses `requestAnimationFrame`. Linear easing is fine — keep it simple.
  - Returns the current animated value (integer).
  - Only animates once per mount (not on every re-render).
  - `prefers-reduced-motion`: return `target` immediately without animation.
- Apply the hook to the 6–7 key stat values rendered in `AnalyzePage.tsx` inside the stats grid.
- Numbers must still use the `.mono` / Geist Mono class — don't change the styling, only the value source.
- Format with the existing compact formatter (e.g. `5.5k`, `1.2M`) — apply the formatter to the animated value at each frame.

**Files to create/edit**:
- `apps/shell/src/hooks/useCountUp.ts` — new hook.
- `apps/shell/src/pages/AnalyzePage.tsx` — apply hook to stat values.

---

#### Change 4 — Ember-style skeleton loaders

Data-loading states inside the app show either nothing or a Mantine `<Loader>`. Replace these with shimmer skeleton loaders that match the "Void Stone & Ember" palette.

**Requirements**:
- A new global CSS block in `index.css` defining `.vs-skeleton` and `.vs-skeleton-text`, `.vs-skeleton-heading`, `.vs-skeleton-avatar`, `.vs-skeleton-card` variants.
- The shimmer animation: `background: linear-gradient(90deg, var(--vs-surface-offset) 25%, var(--vs-surface-dynamic) 50%, var(--vs-surface-offset) 75%); background-size: 200% 100%; animation: vs-shimmer 1.6s ease-in-out infinite;` — this follows the existing `--vs-*` token naming already in `index.css`.
- Define `@keyframes vs-shimmer` (name must not clash with any existing keyframe — check `index.css` first).
- `prefers-reduced-motion`: replace the animated gradient with a static `background: var(--vs-surface-offset)` (no shimmer movement).
- Light mode: the `--vs-surface-offset` and `--vs-surface-dynamic` tokens already flip in the `[data-mantine-color-scheme="light"]` block — so the skeleton colours inherit automatically without extra rules.
- Apply skeletons in **two places**:
  1. `FinderPage.tsx`: while `isLoading` (TanStack Query) is true after clicking "Consulta l'oracolo", show 4–5 stacked `.vs-skeleton-card` placeholders (matching the approximate height of a `BuildCard`) instead of the Mantine `<Loader>`.
  2. `AnalyzePage.tsx`: while the mutation is pending, show a `.vs-skeleton-heading` + three rows of `.vs-skeleton-text` inside the left dashboard column instead of blank space.

**Files to edit**:
- `apps/shell/src/index.css` — add keyframe + skeleton classes.
- `apps/shell/src/pages/FinderPage.tsx` — replace loading state with skeleton cards.
- `apps/shell/src/pages/AnalyzePage.tsx` — replace loading state with skeleton rows.

---

#### Patch Notes entry (mandatory, same commit)

Add to the top of `RELEASES` in `apps/shell/src/pages/PatchNotesPage.tsx`:

```ts
{
  version: "Step 33",
  date: "2026-05-18",
  title: { it: "Interfaccia viva", en: "Living interface" },
  summary: {
    it: "Il sito ora respira: particelle ember sullo sfondo, oggetti unici con effetto shimmer, numeri che si animano all'apertura e scheletri di caricamento raffinati.",
    en: "The site now breathes: ember particles in the background, unique items with a shimmer effect, animated stat counters on load, and refined skeleton loaders."
  },
  bullets: [
    { it: "Sfondo animato con particelle ember che reagiscono al mouse", en: "Animated ember particle background that reacts to mouse movement" },
    { it: "Oggetti Unique con effetto shimmer dorato in scorrimento", en: "Unique items with a scrolling gold shimmer effect" },
    { it: "Statistiche chiave (Vita, DPS, EHP…) con count-up animato all'apertura", en: "Key stats (Life, DPS, EHP…) animate from 0 on load" },
    { it: "Skeleton loader ember-style durante il caricamento dei risultati", en: "Ember-style skeleton loaders while results are loading" },
  ]
}
```

---

#### Gate

Run before declaring done:
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
cd apps/shell && npm run build
```

All five must pass with zero errors. This step is frontend-only — the Python gate should be a no-op, but run it anyway.

---

## 9. Prompt archive

Closed prompts kept for context. Don't run these.

- **Old Prompt 001 (Core DB schema)** — PostgreSQL schema. Rejected 2026-05-14.
- **Old Prompt 002 (PoE Ninja ETL)** — ETL into Postgres. Rejected 2026-05-14.
- **Old Prompt 003 (Base items ETL)** — ETL into Postgres. Rejected 2026-05-14.
- **Old Prompt 004 (Finder blank page bugfix)** — Shipped 2026-05-15. ✅
- **Old Prompt 005 (PoB `explodeSource` crash)** — Shipped 2026-05-15. ✅
- **Old Prompt 006 (Step 20 — Analyze page redesign)** — Shipped 2026-05-15. ✅
- **Old Prompt 007 (Step 21 — Divine Orb cold-start overlay)** — Shipped 2026-05-15. ✅
- **Old Prompt 008 (Step 17 scaffolding)** — Shipped 2026-05-15. ✅
- **Old Prompt 009 (Step 19 scaffolding)** — Shipped 2026-05-15. ✅
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
