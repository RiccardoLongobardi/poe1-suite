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
- **Baseline gate**: 704 tests green / 121 mypy / 117 format. Frontend build 585 KB / 181 KB gzip.
- **Working features (all QA-verified 2026-05-15)**:
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19). ✅ QA passed.
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA. ✅ QA passed.
  - "Importa stage in PoB": exports a stage-specific PoB code. Passes through the user's real `<Items>`/`<Skills>` verbatim (only the passive tree differs per stage). ✅ QA passed.
  - Trade redirect (client-side, no server-side GGG calls — GGG blocks Render's IP range). ✅ QA passed.
  - PoB Analyze → full build dashboard (Step 20, done 2026-05-15): character header + key stats, equipment grid with per-item tooltips, flasks, tree jewels, skill-link panel. ✅ QA passed.
  - Cold-start Divine Orb warmup overlay (Step 21, done 2026-05-15): full-viewport overlay with an animated inline-SVG PoE1 Divine Orb shown while the Render free-tier backend warms up.
- **Design system**: "Void Stone & Ember" (Step 22a, done 2026-05-15) — void-black warm backgrounds, ember-gold accent, parchment text, Cinzel/Cabinet Grotesk/Geist Mono type. Replaced the old Atlas-violet theme. Per-page redesigns: 22b (Finder) next, 22c (Planner + Analyze) queued.
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

- [ ] **Step 22b — Finder page redesign** — New layout + animations for FinderPage + FinderResultCard, on the Void Stone & Ember design system (22a, merged). See §8 Prompt — Step 22b.

### QUEUED (run in sequence after 22b)

- [ ] **Step 22c — Planner + Analyze redesign** — Timeline layout for Planner, sticky header + reveal animations for Analyze. Depends on 22b being merged. See §8 Prompt — Step 22c.

### CANDIDATE FUTURE WORK

- [ ] **Finder result-list polish** — sort indicator, "X% of meta" line, per-skill drill-down.
- [ ] **Pricing-aware gear classifier** — wire `PricingService.snapshot()` into stage-export router.
- [ ] **Bundle code-splitting** — Vite warns at 585 KB; lazy-split Planner/Finder routes.

### DONE

- [x] **Step 22a — Void Stone & Ember design system** (2026-05-15) — Replaced the Atlas-violet theme with the new system: `theme.ts` rewritten with `ember`/`blood`/`dark` Mantine ramps (overriding `dark` auto-themes void bg + parchment text + surfaces), `autoContrast` for readable ember buttons; `index.css` rewritten with `--vs-*` tokens, parchment-noise body overlay, Cinzel-forced H1/H2, and global `.mantine-*` rules for interactive states (Mantine v7 `styles` can't nest pseudo-selectors); `index.html` font links; `App.tsx` recoloured; all `astral`/`gold` colour props + hardcoded violet rgba recoloured to ember. System-level only — zero layout changes. Frontend-only. Verified in browser. 585 KB / 181 KB gzip.
- [x] **Step 21 — Divine Orb cold-start overlay** (2026-05-15) — `useServerWarmup` hook + `WarmupOverlay` component. Hand-authored inline-SVG PoE1 Divine Orb, CSS keyframe animation, `prefers-reduced-motion` aware. Mounted at `App.tsx` root. Frontend-only, no backend change. 585 KB / 181 KB gzip.
- [x] **Step 20 — Analyze page full redesign** (2026-05-15) — PoB-style dashboard. 581 KB / 180 KB gzip. ✅ QA passed.
- [x] **Steps 1-19** — See older entries below and `CLAUDE.md` for full detail.
- [x] **Bugfix — Finder blank page** (2026-05-15) — Mantine v7 grouped-data shape + ErrorBoundary. ✅
- [x] **Bugfix — Stage export fake items + `explodeSource`** (2026-05-15) — Passthrough wins. ✅
- [x] **Step 19 — Population stats in Finder** (2026-05-15). ✅
- [x] **Step 18 — Dynamic Gem Progression** (2026-05-14). ✅
- [x] **Step 17 — Dynamic Gear Progression** (2026-05-15). ✅
- [x] **Step 16 — Dynamic Tree Progression** (2026-05-14). ✅
- [x] **Step 15 — Finder search improvements** (2026-05-14). ✅
- [x] **Steps 1-14** — Core models, pricing, planner, PoB encoder/decoder, UI shell. ✅
- [x] **Production deploy live** — Render + Vercel, free tier.

### REJECTED / OBSOLETE

- ~~PostgreSQL data layer~~ → diskcache + poe.ninja.
- ~~poedb.tw scraping~~ → vendored JSON.
- ~~Server-side GGG Trade~~ → client-side redirect.
- ~~Hand-curated PROGRESSION registries~~ → dynamic synthesis (Steps 16-19).
- ~~New BuildTemplate subclasses per skill~~ → 49 templates frozen; stage data is dynamic.

---

## 7. Decision log

Reverse-chronological.

- **2026-05-15** — *Full frontend redesign: "Void Stone & Ember" theme.* The current Atlas-violet / purple-gradient theme (Mantine `astral` + `gold` palette, Inter body, starfield background) is generic AI-aesthetic and does not reflect PoE 1's visual identity. Decision: replace entirely with the "Void Stone & Ember" design system — near-black warm void backgrounds, amber-gold currency-orb accent (`#c8932a`), parchment text (`#e2d5b8`), dark blood accent (`#8b1a1a`), Cabinet Grotesk body, Cinzel headings only at H1/H2, Geist Mono for stat values. Glassmorphism used selectively on result cards (not everywhere). Animations via CSS keyframes only — no Framer Motion, no GSAP. Three sub-steps in sequence: 22a (design system), 22b (Finder), 22c (Planner + Analyze). Each sub-step must pass the full gate + deploy before the next begins. See §8 for the three prompts.
- **2026-05-15** — *Cold-start banner: Divine Orb theme.* See §9 Old Prompt 007.
- **2026-05-15** — *Analyze page full redesign.* See §9 Old Prompt 006.
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

### Prompt — Step 22b: Finder page redesign

```prompt
You are working inside the `poe1-suite` mono-repo. Read CLAUDE.md and CLAUDE_PERPLEXITY_WORKFLOW.md first. Step 22a (Void Stone & Ember design system) must already be merged before starting this step.

Read these files before touching anything:
- `apps/shell/src/pages/FinderPage.tsx`
- `apps/shell/src/components/IntentCard.tsx`
- `apps/shell/src/components/PopulationStatsPanel.tsx`
- `apps/shell/src/index.css`
- `apps/shell/src/theme.ts` (already updated by 22a)

## Context

The Finder is the primary page of the app — the oracle's interface. The current layout is a flat single-column form with stacked components. The redesign gives it the "oracle answers" feel: a large search input at the centre, results that are *revealed* rather than listed, and a sidebar for meta-statistics.

## Layout changes

### 1. Search area — oracle prompt

The current `<Textarea>` + `<Button>` form should be redesigned as a centred hero-style search:

```
┌────────────────────────────────────────────────────┐
│                                                  │
│   Consulta l'oracolo                             │  <- H2, Cinzel
│   Descrivi il build che cerchi in italiano       │  <- subtitle, muted
│                                                  │
│   ┌────────────────────────────────────────┐   │
│   │ "cerca RF con 6k life almeno"            │   │
│   └────────────────────────────────────────┘   │
│              [ Consulta l'Oracolo ]              │  <- ember button
│                                                  │
└────────────────────────────────────────────────────┘
```

After the user submits, the search area **collapses** (Mantine `<Collapse>` or CSS max-height transition) to a single compact row showing the query text + a "modifica" ghost button. This frees screen space for results.

### 2. Filter pill row

The class/ascendancy/stat-floor filters move to a compact horizontal pill row below the collapsed search. Filters are Mantine `<Select>` and `<NumberInput>` at reduced size (`size="xs"`). On mobile, this row scrolls horizontally.

### 3. Two-column layout (desktop) / single column (mobile)

Above 1024px, split into:

```
┌────────────────────────────────────────────────────────────┐
│                           │               │            │
│   Result cards (2/3)      │  Meta sidebar  │ (1/3)      │
│                           │  ───────────  │            │
│  ┌───────┐ ┌───────┐  │  PopStats    │            │
│  │ card  │ │ card  │  │  panel here  │            │
│  └───────┘ └───────┘  │              │            │
│  ┌───────┐ ┌───────┐  │              │            │
│  │ card  │ │ card  │  │              │            │
│  └───────┘ └───────┘  └──────────────┘            │
└────────────────────────────────────────────────────────────┘
```

The `PopulationStatsPanel` moves to the sidebar. On mobile (< 1024px) it appears above the results as before.

### 4. Result card redesign

Each result card (create or update the component that renders a single ranked build) must show:

- **Top row**: ascendancy badge (ember colour) + main skill name (bold, Cabinet Grotesk) + level `— Lv. 94` (mono, muted)
- **Stats row**: three stat chips in Geist Mono — Life `♥ 5 840`, DPS `⚡ 4.2M`, EHP `⚡ 12 400`. Use PoE1 rarity colours: life = `var(--vs-blood)`, dps = `var(--vs-ember)`, ehp = `#4fa8a8` (gem teal).
- **Character name** (bottom, faint, `var(--vs-text-faint)`)
- Right edge: rank badge `#1`, `#2` etc. in small Cinzel, ember gold

Card interaction:
- `background: var(--vs-surface-1)`, border `var(--vs-border)`.
- On hover: border becomes `var(--vs-ember)`, `box-shadow: var(--vs-shadow-lg)`. Transition `var(--vs-transition)`.
- Glassmorphism: add `backdrop-filter: blur(8px)` to the card. This works because the noise texture on `body::before` creates a visible background. Test that it doesn't degrade to a plain block on Firefox (provide a `@supports` fallback).

### 5. Reveal animation

When the result list mounts or updates (new query result arrives), each card appears with a staggered reveal:

```css
@keyframes vs-card-reveal {
  from {
    opacity: 0;
    transform: translateY(10px);
    clip-path: inset(0 100% 0 0);
  }
  to {
    opacity: 1;
    transform: translateY(0);
    clip-path: inset(0 0% 0 0);
  }
}

.vs-card-reveal {
  animation: vs-card-reveal 400ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

@media (prefers-reduced-motion: reduce) {
  .vs-card-reveal { animation: none; }
}
```

Apply `vs-card-reveal` to each result card with `animation-delay: calc(var(--card-index) * 50ms)` via an inline style `--card-index: N`.

### 6. Empty state

When no query has been submitted yet (initial page load), show a centred empty state instead of a blank space:

```
[ spark icon from lucide-react ]
"L'oracolo attende la tua domanda"
"Descrivi il build che cerchi — classe, skill, budget"
```

Icon: `<Sparkles>` or `<Eye>` from lucide-react (already a dependency? check; if not, use a simple inline SVG eye icon). Icon colour: `var(--vs-ember-border)`.

## Definition of done

- The Finder page renders with the hero search area, collapsing behaviour, pill filter row, 2-col desktop / 1-col mobile layout.
- Result cards show the 3-stat row with PoE1 rarity colours.
- Stagger reveal animation fires on each new result set.
- glassmorphism cards with `@supports` fallback.
- Empty state renders on initial load.
- PopulationStatsPanel is in the sidebar on desktop.
- All existing Finder functionality is preserved (NL extraction, class/asc/stat-floor filters, sort, population stats).
- Gate passes. Frontend build succeeds.
- Commit `feat(shell): Step 22b — Finder page redesign`, push to main.
- Update §1 + §6 in `CLAUDE_PERPLEXITY_WORKFLOW.md`.
```

---

### Prompt — Step 22c: Planner + Analyze redesign

```prompt
You are working inside the `poe1-suite` mono-repo. Read CLAUDE.md and CLAUDE_PERPLEXITY_WORKFLOW.md first. Steps 22a and 22b must already be merged before starting this step.

Read these files before touching anything:
- `apps/shell/src/pages/PlannerPage.tsx`
- `apps/shell/src/pages/AnalyzePage.tsx`
- `apps/shell/src/index.css`
- `apps/shell/src/theme.ts`

## Part A — Planner redesign

### Current state
The Planner page shows a form (query + PoB paste) that streams a `BuildPlan` via SSE, then renders 6 `StageCard` components stacked vertically.

### New layout: Roman numerals timeline

On desktop (≥ 1024px), replace the stacked cards with a horizontal timeline:

```
  I          II         III        IV          V          VI
  ●─────────○─────────○─────────○─────────○─────────○
[Oriath]  [Maps T1]  [Maps T6]  [Maps T11]  [Red Maps] [Endgame]
```

- The connecting line is `var(--vs-border)` (thin, ember-trace).
- Completed/active stages: the dot fills with `var(--vs-ember)`; the line segment behind it fills too (progress bar effect).
- Stages that haven't streamed yet: dot is `var(--vs-surface-3)`, label is `var(--vs-text-faint)`.
- Clicking a stage dot expands an inline panel below the timeline (not a modal) with that stage's tree/gear/gem tabs. Only one stage can be expanded at a time; clicking a different dot collapses the current one first.
- The inline panel expansion uses CSS `max-height` transition (0 → auto via a JS-assisted pattern, or Mantine `<Collapse>`).
- On mobile (< 1024px): keep the current vertical stacked card layout (no timeline).

### Stage labels

Use Roman numerals as the visual label for each stage dot (I, II, III, IV, V, VI). The human-readable stage name ("Oriath", "White Maps", etc.) appears below the dot as a subtitle in `var(--vs-text-muted)`, Cabinet Grotesk, `font-size: 0.75rem`.

### SSE streaming — progressive reveal

While the SSE stream is in progress, stages animate in one at a time. As each `stage_update` event arrives:
1. The dot for that stage transitions from faint to ember (CSS transition on `background-color`).
2. The connecting line segment progresses (update a CSS custom property `--progress` on the line element).
3. The stage card content fades in with `opacity: 0 → 1`, 300ms ease.

This replaces the current spinner/loading state with a visible oracle-is-computing metaphor.

### Input area

Same collapsing pattern as Finder (Step 22b): the input form collapses to a compact summary row after the plan starts streaming. The summary row shows the query text + a "modifica" ghost button.

## Part B — Analyze redesign

### Current state
Step 20 already rebuilt this into a PoB-style dashboard. The only changes needed are cosmetic: apply the new design tokens and add two micro-interactions.

### Changes

1. **Sticky character header**: the character header row (name, class, level, league) should become `position: sticky; top: 0; z-index: 10;` with `background: rgba(8, 6, 4, 0.9); backdrop-filter: blur(10px);` so it stays visible while the user scrolls through gear and skills.

2. **Rarity colours on item borders**: the equipment grid already has left-border rarity colours. Ensure the colours use the PoE1 rarity CSS variables defined in Step 22a:
   - Normal items: `var(--vs-normal)` (`#c8c8c8`)
   - Magic items: `var(--vs-magic)` (`#8888ff`)
   - Rare items: `var(--vs-rare)` (`#ffff77`)
   - Unique items: `var(--vs-unique)` (`#af6025`)

3. **Stat value fonts**: all numerical stat values in the key-stats grid must use the `.mono` class (Geist Mono) established in Step 22a.

4. **Section reveal on mount**: when the snapshot first loads, the four main sections (character header, left column, right column, skill panel) appear sequentially with a 100ms stagger using the `vs-card-reveal` animation class defined in Step 22b's CSS. Do not re-animate on re-render.

## Definition of done

- Planner: horizontal timeline on desktop, vertical stacked cards on mobile. Stage dots animate as SSE events arrive. Input collapses after stream starts.
- Analyze: sticky character header. Rarity border colours use the CSS variables. Numbers use Geist Mono. Section reveal on mount.
- All existing Planner + Analyze functionality preserved.
- Gate passes. Frontend build succeeds.
- Commit `feat(shell): Step 22c — Planner timeline + Analyze polish`, push to main.
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
