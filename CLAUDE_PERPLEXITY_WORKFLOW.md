# CLAUDE_PERPLEXITY_WORKFLOW

Coordination playbook between **Perplexity** (research / design / data-source surveys) and **Claude Code** (in-repo implementation) for the `poe1-suite` mono-repo.

This file's only job is to keep the two tools in sync — what each is responsible for, what's currently open, what's been decided. The source of truth for the codebase itself remains [`CLAUDE.md`](./CLAUDE.md) (architecture, conventions, gate, lessons learned).

> **Read this AND `CLAUDE.md` before starting any session.** This file is the workflow contract; `CLAUDE.md` is the project contract.

---

## 1. Where the project actually stands (read first)

Don't trust earlier versions of this file — the section below is the authoritative snapshot. As of **2026-05-15**:

- **FOB is live in production**, free tier:
  - Frontend: <https://fob-ten.vercel.app> (Vercel, auto-deploy from `main`).
  - Backend: <https://fob-api-rtgg.onrender.com> (Render, region Frankfurt, auto-deploy from `main`).
  - Cost: **$0/month**.
- **Baseline gate**: 704 tests green / 121 mypy / 117 format. Frontend build 586 KB / 182 KB gzip.
- **Working features (all QA-verified 2026-05-15)**:
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19). ✅ QA passed.
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA. ✅ QA passed.
  - "Importa stage in PoB": exports a stage-specific PoB code. Passes through the user's real `<Items>`/`<Skills>` verbatim (only the passive tree differs per stage). ✅ QA passed.
  - Trade redirect (client-side, no server-side GGG calls — GGG blocks Render's IP range). ✅ QA passed.
  - PoB Analyze → full build dashboard (Step 20, done 2026-05-15): character header + key stats, equipment grid with per-item tooltips, flasks, tree jewels, skill-link panel. ✅ QA passed.
  - Cold-start Divine Orb warmup overlay (Step 21, done 2026-05-15): full-viewport overlay with an animated inline-SVG PoE1 Divine Orb shown while the Render free-tier backend warms up.
- **Design system**: "Void Stone & Ember" (Step 22, done 2026-05-15) — void-black warm backgrounds, ember-gold accent, parchment text, Cinzel/Cabinet Grotesk/Geist Mono type. Replaced the old Atlas-violet theme. All three slices shipped: 22a (design system), 22b (Finder), 22c (Planner timeline + Analyze polish). QA verified. ✅
- **Light mode**: currently broken / effectively absent — Mantine `colorScheme` toggle exists in the header but the light colours are not defined and render white-on-white in many areas. Step 23 will fix this with the "Parchment" light-mode palette. See §8.
- **Dynamic-synthesis pivot complete** (Steps 16/17/18/19, all done).
- **Recently fixed (2026-05-15, all user-confirmed)**:
  - Build Finder blank-page bug — ErrorBoundary + Mantine v7 grouped-data shape for the class Select. ✅
  - Stage export emitted mod-less fake items + slot-labelled gem stubs + `explodeSource` PoB Lua crash — passthrough fix. ✅

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
| Trade search | GGG `/api/trade/search` | in-memory 8 min TTL | Client-side redirect only (Render IP blacklisted) |
| Passive tree | GGG vendored JSON | `packages/fob/data/tree/3_28.json` | Manual per league |
| Item bases | repoe-fork JSON | `packages/fob/data/items/base_items.json` | Manual per league |

Sources explicitly rejected (don't propose again): poedb.tw, GGG OAuth API for game data, brather1ng/RePoE (dead).

---

## 3. Roles

### 3.1 Perplexity — research & design

Owns: data-source surveys, algorithm design, comparative library reviews, long-form research, QA sessions (bug classification + fix prompts), UI/UX design direction and design system spec.

Does NOT: edit `.py` / `.ts` / `.json` files, modify Claude Code todos, update §6 implementation status.

### 3.2 Claude Code — implementation

Owns: all code under `packages/` + `apps/` + `scripts/`, test changes, gate enforcement, commits + pushes, updating both `CLAUDE.md` and this file's §6 / §7.

Constraints: no `--no-verify`, no secrets, must run full gate before declaring done.

### 3.3 The user (Riccardo)

Owns: strategic direction, manual QA in PoB Community, final-call on architectural trade-offs.

---

## 4. Collaboration rules

1. `CLAUDE.md` is the contract, this file is the playbook. When they conflict, `CLAUDE.md` wins.
2. No silent re-architecture — changes to stack / data sources / public API go in §7.
3. Prompts in this file are reusable templates, self-contained, runnable today without past-chat context.
4. Don't fetch GGG Trade from production (Render IPs blacklisted — HTTP 403).
5. Vendor data, don't fetch at runtime.

---

## 5. Open questions for Perplexity

- *(none as of 2026-05-15)*

---

## 6. Backlog & status

### IN PROGRESS

- *(nothing)*

### NEXT

- [ ] **Step 23 — Light mode "Parchment"** — Define a complete, QA-ready light-mode palette that pairs with the existing "Void Stone & Ember" dark mode. Warm cream backgrounds, ink-on-parchment text, ember gold as accent only (not text). See §8 Prompt — Step 23.

### CANDIDATE FUTURE WORK

- [ ] **Finder result-list polish** — sort indicator, "X% of meta" line, per-skill drill-down.
- [ ] **Pricing-aware gear classifier** — wire `PricingService.snapshot()` into stage-export router.
- [ ] **Bundle code-splitting** — Vite warns at 585 KB; lazy-split Planner/Finder routes.

### DONE

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

- **2026-05-15** — *Light mode "Parchment" palette.* The existing `colorScheme` toggle in the header exists but the light colours are effectively undefined — most areas render white-on-white or with leftover Mantine defaults that clash with the Void Stone & Ember identity. Decision: implement a dedicated "Parchment" light mode — warm cream (`#f2ece0`) base, ink-on-parchment text (`#2a1f0e` primary / `#6b5a3e` muted / `#9a8570` faint), ember gold (`#c8932a`) as interactive accent only (never as body text colour — fails WCAG 4.5:1 contrast on light surfaces), blood (`#8b1a1a`) for warnings/errors, parchment-layered surfaces. The theme toggle already exists; only the CSS variable values and Mantine `light` overrides need defining. Frontend-only, no backend change.
- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember" theme.* See §9 for archived prompt details.
- **2026-05-14** — *Server-side Trade search impossible on Render (GGG 403).* Client-side redirect.
- **2026-05-14** — *Dynamic synthesis over curated templates.* Steps 16-19.
- **2026-05-14** — *Vendor data, don't fetch at runtime.* Passive tree + base items vendored.
- **2026-05-14** — *External data source survey.* poe.ninja + repoe-fork + PoB Community. poedb + GGG OAuth out.
- **2026-05-14** — *No PostgreSQL, no ETL.* diskcache model.
- **2026-05-07** — *Backend migrated Fly.io → Render.* Free tier, ~30 s cold start.
- **2026-04-25** — *Pricing v2 closed* (Step 9).

---

## 8. Prompt library

Reusable templates. Self-contained — runnable today without past-chat context. When a prompt ships, move to §9.

---

### Prompt — Step 23: Light mode "Parchment"

```prompt
You are working inside the `poe1-suite` mono-repo. Read CLAUDE.md and CLAUDE_PERPLEXITY_WORKFLOW.md first, then read the following files before touching anything:
- `apps/shell/src/theme.ts`
- `apps/shell/src/index.css`
- `apps/shell/src/main.tsx` (or wherever MantineProvider is configured)

## Context

The "Void Stone & Ember" dark mode is complete and QA-verified (Step 22). A `colorScheme` toggle already exists in the header. The problem: the light mode is broken — Mantine falls back to its default light palette, producing white backgrounds, black text, and violet accents that clash entirely with the Void Stone & Ember identity. Many areas are white-on-white or otherwise illegible.

This step defines a complete "Parchment" light mode that pairs with the dark mode. It is **frontend-only, zero layout changes, zero new npm dependencies**.

## Design spec — "Parchment" light mode

### Colour philosophy

The Parchment theme is the daytime counterpart to Void Stone. Same PoE1 identity (parchment, ember gold, ink), different luminosity. Ember gold is used exclusively as an **interactive accent** (borders on hover, button backgrounds, badge colours) — never as body text, because `#c8932a` on a light cream surface fails WCAG 4.5:1 contrast. All body text uses warm dark ink tones.

### CSS variables — light mode overrides

In `index.css`, add a `[data-mantine-color-scheme="light"]` block (Mantine v7 uses this attribute on `<html>`) that overrides the `--vs-*` tokens defined in the dark `:root`:

```css
[data-mantine-color-scheme="light"] {
  /* Backgrounds — warm cream, layered parchment */
  --vs-bg:           #f2ece0;   /* base: aged parchment */
  --vs-surface-1:    #ede5d2;   /* primary card surface */
  --vs-surface-2:    #e8ddc8;   /* elevated surface (tooltips, modals) */
  --vs-surface-3:    #e2d5bc;   /* highest elevation */

  /* Ember gold — accent only, NOT text */
  --vs-ember:        #b07820;   /* darkened for light bg — still amber, now 4.6:1 on --vs-bg */
  --vs-ember-bright: #c8932a;   /* hover state */
  --vs-ember-dim:    rgba(176, 120, 32, 0.10);
  --vs-ember-glow:   rgba(176, 120, 32, 0.20);
  --vs-ember-border: rgba(176, 120, 32, 0.25);

  /* Blood — secondary accent */
  --vs-blood:        #7a1515;
  --vs-blood-dim:    rgba(122, 21, 21, 0.10);

  /* Text — ink on parchment */
  --vs-text:         #2a1f0e;   /* primary: dark walnut ink */
  --vs-text-muted:   #6b5a3e;   /* secondary: sepia */
  --vs-text-faint:   #9a8570;   /* tertiary: faded inscription */
  --vs-text-inverse: #f2ece0;   /* text on ember/dark backgrounds */

  /* Borders */
  --vs-border:       rgba(176, 120, 32, 0.25);  /* ember trace, visible on cream */
  --vs-border-faint: rgba(176, 120, 32, 0.12);
  --vs-border-stone: rgba(42, 31, 14, 0.08);    /* neutral ink divider */

  /* Stat colours — PoE1 rarity, adjusted for light background readability */
  --vs-normal:   #555555;  /* dark gray on cream */
  --vs-magic:    #4444cc;  /* dark blue */
  --vs-rare:     #8a7a00;  /* dark gold/yellow */
  --vs-unique:   #8b4513;  /* dark orange/saddle brown */
  --vs-gem:      #0d7a75;  /* dark teal */
  --vs-currency: #6b5a3e;  /* same as text-muted */

  /* Shadows — warm ink tint */
  --vs-shadow-sm: 0 1px 3px rgba(42, 31, 14, 0.12);
  --vs-shadow-md: 0 4px 16px rgba(42, 31, 14, 0.15);
  --vs-shadow-lg: 0 8px 32px rgba(42, 31, 14, 0.18), 0 0 64px rgba(176, 120, 32, 0.06);
}
```

### Noise texture in light mode

The `body::before` parchment noise overlay defined in the dark mode is already `position: fixed` and `opacity: 0.025`. In light mode, the same texture should be slightly more visible:

```css
[data-mantine-color-scheme="light"] body::before {
  opacity: 0.04;
}
```

### Mantine theme — light colour overrides in `theme.ts`

Mantine v7's `createTheme` supports `light`/`dark` object variants for component styles. Read the existing `theme.ts` carefully — it may already use `colorScheme`-conditional styles or it may use hardcoded `var(--vs-*)` tokens.

**If `theme.ts` uses `var(--vs-*)` tokens directly** (the preferred approach from Step 22a), then the CSS variable overrides above are sufficient — no changes to `theme.ts` are needed for most components, because the CSS vars cascade automatically.

**However**, some Mantine component styles may have hardcoded dark hex values (e.g. `background: "#080604"`, `color: "#e2d5b8"`) that were added as one-off fixes during Step 22. Find all such hardcoded dark values in `theme.ts` and replace them with the appropriate `var(--vs-*)` token so they adapt automatically to both modes.

Additionally, ensure the Mantine `MantineProvider` in `main.tsx` (or wherever it is configured) has:

```tsx
<MantineProvider theme={fobTheme} defaultColorScheme="dark">
```

The `defaultColorScheme="dark"` ensures new visitors see the dark mode. The existing header toggle already writes `data-mantine-color-scheme` to `<html>`.

### Body background in light mode

The current `index.css` likely sets `body { background-color: var(--vs-bg); }` globally. Since `--vs-bg` is now overridden in light mode, this should work automatically. Verify it does — if Mantine's `AppShell` overrides the body background with its own value, add:

```css
[data-mantine-color-scheme="light"] body,
[data-mantine-color-scheme="light"] .mantine-AppShell-main {
  background-color: var(--vs-bg) !important;
}
```

### Scrollbar in light mode

```css
[data-mantine-color-scheme="light"] ::-webkit-scrollbar-track {
  background: var(--vs-bg);
}
[data-mantine-color-scheme="light"] ::-webkit-scrollbar-thumb {
  background: var(--vs-ember-border);
}
[data-mantine-color-scheme="light"] ::-webkit-scrollbar-thumb:hover {
  background: var(--vs-ember);
}
```

### WarmupOverlay in light mode

The `WarmupOverlay` uses `rgba(8, 6, 4, 0.92)` as its overlay background — this is correct and intentional regardless of colour scheme (it's a full-screen takeover, not a surface). No change needed.

### BuildCard glassmorphism in light mode

The `.vs-glass` class uses `backdrop-filter: blur(8px)`. In light mode the noise texture is the backdrop; the blur effect will be subtle but visible. No change needed — the existing `@supports` fallback handles browsers without backdrop-filter.

## Verification checklist

After implementing, toggle the colour scheme and verify each of the following in the browser:

- [ ] Body background is warm cream (`#f2ece0`), not white and not purple.
- [ ] Cards render with `--vs-surface-1` (`#ede5d2`) background and a visible ember-trace border.
- [ ] Primary text (`--vs-text`, `#2a1f0e`) is readable on every surface — dark walnut ink.
- [ ] Muted text (`--vs-text-muted`, `#6b5a3e`) is readable — sepia tone.
- [ ] Ember buttons: background `#b07820`, text `--vs-text-inverse` (`#f2ece0`). Readable.
- [ ] Outline buttons: ember border visible, background cream.
- [ ] Inputs: background `--vs-surface-2`, border `--vs-border-faint`, focus ring ember.
- [ ] Badges: ember-dim background, ember text.
- [ ] PoE1 rarity colours (normal/magic/rare/unique/gem/currency) are all legible on cream.
- [ ] Finder stat chips (Life/DPS/EHP) are legible.
- [ ] Planner timeline dots use `--vs-ember` for active stages — visible on cream.
- [ ] Analyze sticky header: readable text, visible background.
- [ ] Dark mode is unaffected — toggling back to dark produces the original Void Stone look.
- [ ] No white-on-white or invisible text anywhere.

## Definition of done

- All verification checklist items pass.
- Gate passes: `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`.
- Frontend build succeeds (Vite `pnpm build` or equivalent).
- Commit `feat(shell): Step 23 — Parchment light mode`, push to main.
- Update §1 + §6 in `CLAUDE_PERPLEXITY_WORKFLOW.md`.
```

---

### Prompt — Step 17 scaffolding

*(kept for reference — already shipped, see §9)*

### Prompt — Step 19 scaffolding

*(kept for reference — already shipped, see §9)*

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
- **Old Prompt 010 (Step 22a — Void Stone & Ember design system)** — Shipped 2026-05-15. ✅ Replaced the Atlas-violet theme with the void-black / ember-gold / parchment design system (theme tokens + global CSS only, zero layout changes).
- **Old Prompt 011 (Step 22b — Finder page redesign)** — Shipped 2026-05-15. ✅ Hero search + collapse, filter-pill row, two-column results + meta sidebar, restyled BuildCard with rarity stat chips + staggered reveal + glassmorphism.
- **Old Prompt 012 (Step 22c — Planner timeline + Analyze polish)** — Shipped 2026-05-15. ✅ Planner horizontal Roman-numeral timeline (desktop) with click-to-expand stages + collapsing input; Analyze sticky character header, rarity CSS vars, Geist Mono stat values, section reveal. Completes the Step 22 frontend redesign.
