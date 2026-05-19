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
- **Step 36 (View Transitions API — full implementation) READY TO IMPLEMENT** — See §8 Prompt 023.

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

- **Step 36 — View Transitions API (full implementation)** (Prompt 023 in §8)

### CANDIDATE FUTURE WORK

- Trade redirect (backlog item, tracked)
- Build generator (backlog item, tracked)
- Atlas x build generator (backlog item, tracked)
- Item filter generator (backlog item, tracked)

### DONE

- [x] **Step 35 — Visual polish batch 3** (2026-05-19, Prompt 022) — 2/3 changes. `GearCard` (Analyze): hover pops item details panel, click pins it open (one pinned at a time). Header `IconSparkles` ember pulse (opacity 0.55→1 + scale + bright glow). **Finder virtual list dropped** — ≤50 items, variable-height cards. Frontend-only, 714 tests.
- [x] **Bugfix — Trade dialog: decimal stat-filter min** (2026-05-19) — `Math.round` on strictness-computed min. Frontend-only.
- [x] **Bugfix — Trade dialog: implicit mods + route transition stutter** (2026-05-19) — domain-aware resolver; CSS fade replaces View Transitions API. Gate: 714/124.
- [x] **Step 34 — Visual polish batch 2** (2026-05-19, Prompt 021) — route fade; price badges (uniques); keyboard shortcuts; toast restyle. 713/121.
- [x] **Bugfix — Trade dialog: unique name search + Instant Buyout + count mods** (2026-05-18). 713/121.
- [x] **Step 33 — Visual polish batch 1** (2026-05-18, Prompt 020) — particles, rarity glow, KPI count-up, ember skeletons. 713/121.
- [x] **Step 32 — Trade dialog: full GGG stat DB + all mods** (2026-05-18). 706/123.
- [x] **Step 31 — poe.ninja-style Trade-search dialog** (2026-05-18). 706/121.
- [x] **Steps 25–30** — Trade redirect pipeline. ✅
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

- **2026-05-19** — *View Transitions API: full implementation approved (Step 36).* Three levels: (1) route cross-fade with ParticleCanvas excluded via `view-transition-name: none`; (2) shared-element transitions on named elements (gear cards, build cards, KPI numbers); (3) micro-interaction transitions on state changes (pin/unpin, expand/collapse, filter apply). React 19 `<ViewTransition>` component NOT used — verify React version first; if < 19, use the imperative `document.startViewTransition` wrapper pattern. All transitions must be progressive-enhancement: if API unavailable, fall back to the existing CSS fade. `prefers-reduced-motion` disables all transitions at the CSS level.
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

### Prompt 023 — Step 36: View Transitions API — full implementation (route + shared element + micro-interactions)

**Goal**: make FOB feel like a native app. The View Transitions API is the single biggest quality-of-life upgrade available in the browser today. This prompt implements it in three layers, from most impactful to least, in a single frontend-only pass.

**Context**: FOB uses "Void Stone & Ember" design system. The app has three main routes (`/finder`, `/analyze`, `/planner`), a `ParticleCanvas` that animates continuously in the background, and several interactive components: `GearCard` (hover+pin popover), `BuildCard` (Finder result), KPI counters (`useCountUp`), ember skeletons, and the Trade dialog.

**Why the previous attempt failed**: `document.startViewTransition` snapshots the entire root DOM including the always-animating `ParticleCanvas`, producing a stuttering frozen frame during the transition. The fix is surgical: assign `view-transition-name: none` to the canvas element *before* calling `startViewTransition`. This tells the browser to exclude it from the snapshot entirely.

**React version check — MANDATORY first step**: before writing any code, check `apps/shell/package.json` to determine the React version.
- If React **≥ 19**: you may use the native `<ViewTransition>` component from `react` for shared-element transitions — it integrates with `startTransition` and is the cleanest API.
- If React **< 19**: use the imperative pattern (`document.startViewTransition` wrapped in a `useViewTransition` hook). Do not add React 19 as a dependency just for this.

All changes must:
- Be **frontend-only** — no backend changes.
- Work in both dark and light colour schemes.
- Respect `prefers-reduced-motion` — when the media query is active, all `::view-transition-*` animations are suppressed via CSS and `startViewTransition` falls back to an instant update.
- Be **progressive enhancement**: wrap every `startViewTransition` call with `if ('startViewTransition' in document)` — if the API is unavailable (Firefox < 130, Safari < 18), fall back gracefully to the existing CSS fade.
- Not regress the gate (currently **714 tests / 124 mypy / ruff clean**).
- Update `PatchNotesPage.tsx` `RELEASES` array in the same commit.

---

#### Layer 1 — Route cross-fade (fix the previous attempt)

**What**: when the user navigates between `/finder`, `/analyze`, `/planner` and `/patch-notes`, the outgoing page fades out and the incoming page fades in using the View Transitions API — not a CSS keyed-wrapper hack.

**The ParticleCanvas fix**:
```ts
// In the navigation handler / useViewTransition hook,
// BEFORE calling document.startViewTransition:
const canvas = document.querySelector('canvas[data-particle-canvas]');
if (canvas) canvas.style.viewTransitionName = 'none';

document.startViewTransition(async () => {
  // perform the React Router navigation here
  // (flushSync + navigate, or useNavigate inside startViewTransition)
  await navigationCallback();
}).ready.finally(() => {
  // restore after transition snapshot is taken
  if (canvas) canvas.style.viewTransitionName = '';
});
```

Make sure the `<canvas>` element in `ParticleCanvas` has `data-particle-canvas` attribute so it is selectable without fragile class queries.

**CSS** — define `::view-transition-old(root)` and `::view-transition-new(root)` in `index.css`:
```css
@keyframes vt-fade-out { from { opacity: 1; } to { opacity: 0; } }
@keyframes vt-fade-in  { from { opacity: 0; } to { opacity: 1; } }

::view-transition-old(root) {
  animation: vt-fade-out 180ms cubic-bezier(0.4, 0, 1, 1) forwards;
}
::view-transition-new(root) {
  animation: vt-fade-in 220ms cubic-bezier(0, 0, 0.2, 1) forwards;
}

@media (prefers-reduced-motion: reduce) {
  ::view-transition-old(root),
  ::view-transition-new(root) { animation: none; }
}
```

**Integration**: create or recreate `apps/shell/src/hooks/useViewTransition.ts` — a hook that wraps `document.startViewTransition` with the canvas fix and the `prefers-reduced-motion` check. Integrate into the navbar links and the `G F/A/P/N` keyboard shortcuts.

---

#### Layer 2 — Shared element transitions

This is the premium interaction. Assign the same `view-transition-name` to a "source" element and a "target" element in two different render states; the browser morphs position, size and shape between them automatically.

**Apply to these specific cases:**

**2a. Finder BuildCard → route (if Analyze accepts a build URL)**
If clicking a Finder result already navigates or could navigate to `/analyze` with that build pre-loaded, give both the result card and the Analyze header the same `view-transition-name: build-hero`. If this navigation path does not exist yet, **skip this sub-case and note it in the commit message** — do not build new routing for it here.

**2b. GearCard popover expansion (Analyze)**
The gear cell in the equipment grid and its pinned popover panel are the same logical item — one is compact, one is expanded. When the popover opens (pins), use a shared element transition so the card visually "expands" to the popover position rather than popping:
```tsx
// On the compact gear cell:
style={{ viewTransitionName: `gear-${slotKey}` }}

// On the popover panel:
style={{ viewTransitionName: `gear-${slotKey}` }}
```
Wrap the pin/unpin state update inside `startViewTransition`. The `slotKey` must be unique per gear slot (e.g. `helmet`, `chest`, `weapon`). Use `contain: layout` on both elements to prevent the transition from affecting sibling layout.

**2c. KPI counter values (Analyze)**
When the user re-analyzes a different build (if that flow exists), the KPI numbers animate from old to new position using shared element transitions instead of just count-up. If build re-analysis does not exist as a user flow yet, **skip this sub-case**.

**CSS pattern for shared elements**:
```css
/* Shared elements: use default cross-fade morphing */
/* The browser handles position/size interpolation automatically */
/* Only override if the default looks wrong */

@media (prefers-reduced-motion: reduce) {
  /* Disable all named transitions */
  * { view-transition-name: none !important; }
}
```

**Important**: `view-transition-name` values must be **unique per visible element** at snapshot time. If two elements share the same name simultaneously, the browser will skip the transition for both. For list items (e.g. gear slots), always suffix with a unique identifier.

---

#### Layer 3 — Micro-interaction transitions

Apply `startViewTransition` to in-page state changes — not just route changes.

**3a. Finder filter apply**
When the user changes a filter (class, ascendancy, stat floor, sort) and the result list re-renders, wrap the results list update inside `startViewTransition`. Give the results container `view-transition-name: finder-results`. The list will cross-fade between old and new results instead of jumping. Keep the transition short (120ms).

**3b. Trade dialog open/close**
The Trade icon button in gear cards and the dialog itself: give the button `view-transition-name: trade-trigger-{slotKey}` and the dialog panel `view-transition-name: trade-trigger-{slotKey}` so it "flies out" from the button. Only if `TradeSearchDialog` is already a Mantine `<Modal>` — if the portal makes shared transitions unreliable, fall back to a simple fade for the dialog and note it.

**3c. Keyboard shortcuts overlay**
The `?` button and the `KeyboardShortcutsModal` — same shared-element pattern as the Trade dialog. Give both `view-transition-name: kbd-overlay-trigger`.

---

#### Architecture summary

```
apps/shell/src/
  hooks/
    useViewTransition.ts          ← new (or recreated from Step 34)
  components/
    ParticleCanvas.tsx            ← add data-particle-canvas attr
    analyze/GearCard.tsx          ← view-transition-name on cell + popover
    finder/FinderResults.tsx      ← view-transition-name on results container
    trade/TradeSearchDialog.tsx   ← view-transition-name on trigger + panel
    shell/KeyboardShortcutsModal.tsx ← view-transition-name on trigger + panel
  pages/
    ShellLayout.tsx               ← integrate useViewTransition into nav
  index.css                       ← all ::view-transition-* CSS
```

---

#### Fallback contract

Every `startViewTransition` call must be guarded:
```ts
function withViewTransition(cb: () => void | Promise<void>) {
  if (
    !('startViewTransition' in document) ||
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    return Promise.resolve(cb());
  }
  return document.startViewTransition(cb).finished;
}
```

Export this utility from `useViewTransition.ts` and use it everywhere — no raw `document.startViewTransition` calls scattered across components.

---

#### Patch Notes entry (mandatory, same commit)

Add to the top of `RELEASES` in `apps/shell/src/pages/PatchNotesPage.tsx`:

```ts
{
  version: "Step 36",
  date: "2026-05-19",
  title: { it: "Transizioni native del browser", en: "Native browser transitions" },
  summary: {
    it: "Navigazione e interazioni animate con la View Transitions API: route, elementi condivisi e micro-interazioni.",
    en: "Navigation and interactions animated with the View Transitions API: routes, shared elements, and micro-interactions."
  },
  bullets: [
    { it: "Transizioni di route con cross-fade nativo", en: "Route transitions with native cross-fade" },
    { it: "Shared element: GearCard si espande al popover", en: "Shared element: GearCard expands to popover" },
    { it: "Micro-interazioni: filtri Finder, Trade dialog, overlay scorciatoie", en: "Micro-interactions: Finder filters, Trade dialog, shortcuts overlay" },
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

All five must pass with zero errors.

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
