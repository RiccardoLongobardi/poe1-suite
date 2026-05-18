# CLAUDE.md — poe1-suite

Instructions for any Claude Code session working in this repo.
Read this file top-to-bottom before doing any work.

## Who the user is

- **Riccardo** — Italian PoE 1 player, builds tools for himself (ric.longobardi@outlook.it).
- Prefers conversation in **Italian**, technical identifiers/commands in **English**.
- Values: "niente fittizio" — no fake/mocked data. Every module ships with real fixtures and is end-to-end playable before the next one starts.

## Product direction (read this BEFORE planning new work)

FOB is a **dynamic** progression planner for PoE 1. It must cover **every class + every ascendancy + every reasonable build** the user can paste — not a curated subset.

**Design principle: synthesis over curation.** When you're tempted to hand-write knowledge for a specific build (templates, stage data, item lists), step back: that pattern doesn't scale to 7 classes × 19 ascendancies × N skills, and goes stale every league. Instead, derive the plan algorithmically from data we already have:

- **Target endgame** comes from the user's pasted PoB (their actual destination).
- **Progression backwards** = working from that endgame to leveling, applying budget/level/lab constraints.
- **Reference data** = poe.ninja ladder (popular skills per ascendancy, typical stat distributions per budget tier), bundled PoE 1 passive tree JSON, live pricing.

The 49 hand-written `BuildTemplate` classes in `poe1_fob.planner.templates` stay — but **only for**:
- Italian descriptive rationale per stage (free-form sentences).
- Build identity / labeling in the UI ("Cyclone Slayer").
- Fallback advice when the user has no pasted PoB.

Tree allocation, gear progression, gem level/quality progression — these are **NOT** to be hand-curated per template. They are derived dynamically (Steps 16-18 in the backlog).

## External data sources (use these, don't reinvent)

Research conducted 2026-05-14 mapped every public PoE 1 data source. The conclusion: **two upstream repos give us everything we need**, both MIT-licensed, both league-current. Don't add new sources without re-doing the research; here's what we evaluated:

| Need | Source we use | Why this one |
|---|---|---|
| **Passive tree** (nodes / edges / classes / ascendancies / masteries / cluster sub-trees) | `PathOfBuildingCommunity/PathOfBuilding` repo, file `src/TreeData/3_28/data.json`. Vendor a snapshot into `packages/fob/data/tree/3_28.json`. | Only complete + license-clean + league-current source. The same JSON PoB itself parses, so any tree we derive round-trips. Re-fetch with `scripts/update_tree_data.py` when GGG ships a new league. |
| **Gem data** (per-level stats, Awakened, alt-qualities) | Not needed yet for Step 18 (our math is deterministic on user's PoB values). When we do need it: vendor `repoe-fork/repoe` `gems.json` (JSON, one league behind) or fall back to PoB's `src/Data/Skills/*.lua`. | PoB has the per-level stat tables; repoe-fork is cleaner JSON; we'll only need this for the *advanced* gem advice (e.g. "Anomalous Empower at 21 gives +X%"). |
| **Item bases** (every base type, slot, requirements, implicits) | `repoe-fork/repoe` `base_items.json`. Vendor into `packages/fob/data/items/`. | Cleanest JSON keyed by base name. PoB's `src/Data/Bases/*.lua` is the same data in Lua — fallback if repoe-fork lags too far behind. |
| **Build population** (popularity per ascendancy, stat percentiles) | poe.ninja builds (we already fetch them). | Zero new HTTP integration — aggregator over data already in memory. Refreshes continuously per league. |

**Sources we evaluated and rejected**:

- **poedb.tw** — HTML-only, no JSON/API, no public dumps. Useful as a human cross-reference, NOT viable as a programmatic feed. Scraping is fragile and terms-of-use ambiguous.
- **GGG official developer API** (`pathofexile.com/developer/docs`) — Only publishes *user* data (characters, stashes, ladder, trade) behind OAuth. Does NOT publish tree, gem, or item-base definitions. May matter someday if we add "import character directly from your account" without the PoB paste step, but not before.
- **brather1ng/RePoE (original)** — Dead, stuck at 3.19 (Sep 2022). Use the `repoe-fork/repoe` fork instead.

**Vendor-or-fetch policy**: Bundle a snapshot of these JSON files inside the repo (e.g. `packages/fob/data/tree/3_28.json`). DON'T fetch them at runtime — adds an upstream dependency on github.com being up and re-introduces "external API drift" we just solved. A new league = one script invocation + one git commit. License is MIT on both upstream repos.

## What this repo is

`poe1-suite` is a uv workspace monorepo of Path of Exile 1 tools. FastAPI backend on port 8765, React/Mantine shell planned. Membership rules:

- `packages/*` → library packages (`poe1-core`, `poe1-shared`, `poe1-pricing`, `poe1-builds`, `poe1-fob`). Each exposes a FastAPI `make_router(settings)` when it has HTTP endpoints.
- `apps/*` → runnable apps. `apps/server/` mounts all routers. `apps/shell/` is the React frontend and is **excluded** from the uv workspace.

## Non-negotiable conventions

1. **Python 3.12**, Pydantic v2, FastAPI, httpx async. All Pydantic models are `frozen=True`. Use `populate_by_name=True` with `camelCase` aliases when serializing to JSON that matches external APIs.
2. **`uv` is the tool** — never `pip`, never `python -m venv`. Commands below.
3. **Test import mode is `importlib`** (configured in `pyproject.toml`). To avoid conftest namespace collisions between packages, each `packages/*/` dir has an empty `__init__.py` extending the dotted module path. Don't remove those.
4. **Ruff is strict** — `E W F I B SIM C4 UP ANN Q RUF` are enabled. Tests are exempt from `ANN`. `**/generated/**` is excluded entirely. Do **NOT** enable the `TCH` rules — they break Pydantic v2 (field annotations need to be importable at runtime).
5. **Mypy is `strict = true`** across 60+ source files. Every public function must be fully typed. `tests/*` has `disallow_untyped_defs = false` override.
6. **No fake data ever.** Tests use real fixtures captured from live poe.ninja / pobb.in. If you need new fixtures, capture them live and commit them under `packages/<pkg>/tests/fixtures/`.

## The gate (run before declaring anything done)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

All four must pass with zero errors. Current baseline: **704 tests green (2 skipped — integration/LLM), 121 files type-checked clean, 117 files formatted clean**. Frontend build 610 KB / 190 KB gzip.

## English support + uniform input font (2026-05-15) ✅

Two frontend-only changes; no backend / API change.

**1. Uniform input font.** Every `<TextInput>`/`<Textarea>`/`<Select>`/`<NumberInput>` (all share `.mantine-Input-input`) now uses `var(--mantine-font-family-monospace)` (Geist Mono) via one global rule in `index.css` — matching the Home/Analyze code aesthetic. The per-component `fontFamily: "monospace"` / `ff="monospace"` overrides on the Analyze and Planner inputs were removed so the global rule is the single source.

**2. Bilingual UI (IT / EN).** New lightweight i18n — no external dependency:

- **`apps/shell/src/i18n.tsx`** — `LangProvider` + `useLang()` + `useT()`. Translations are **co-located**, written inline as `t({ it: "...", en: "..." })` rather than a central key dictionary — no key bookkeeping, no missing keys, type-safe. The chosen language persists to `localStorage.fob_lang`.
- **`main.tsx`** — `<LangProvider>` wraps `<App>`.
- **Header** — a compact `IT | EN` `SegmentedControl` sits next to the theme toggle.
- Every page + component is translated: App nav, Home, Welcome, Finder (+ IntentCard, PopulationStatsPanel, BuildCard), Planner (+ StageCard), Analyze, Patch Notes (the full release history is bilingual), DonationModal, WarmupOverlay.
- **`ErrorBoundary`** is a class component (no hooks) — it reads `localStorage.fob_lang` directly via a small `lang()` helper for its two fallback strings.
- Module-level option arrays that held Italian labels (`SORT_OPTIONS` in FinderPage, `TARGET_OPTIONS` in PlannerPage) were converted to `{value, it, en}` key arrays and the `data` for the `Select`/`SegmentedControl` is built inside the component with `t()`.

**Pattern for future strings**: call `const t = useT();` in the component and wrap every user-facing string as `t({ it: "...", en: "..." })`. Game/PoE terms (skill names, "EHP", "DPS", enum values) stay untranslated.

## Patch Notes page (2026-05-15) ✅

New `/patch-notes` route — a static, data-driven changelog covering the full project history (Steps 1–23, the deploy phases, the dynamic-synthesis pivot, the redesign) newest-first.

- **`apps/shell/src/pages/PatchNotesPage.tsx`** — a `RELEASES` array (16 entries, Italian copy) mapped to `ReleaseCard`s: each is an ember-left-border `<Card>` with a date badge, title, optional summary, and bullet list.
- **`App.tsx`** — `/patch-notes` route + a low-prominence navbar entry: a `<Divider mt="auto">` pushes a small "Note di rilascio" `NavLink` (smaller font, muted colour, `IconHistory`) to the bottom of the navbar, visually secondary to the four main links.

Frontend-only, no backend change.

> **MANDATORY — keep the Patch Notes in sync.** Whenever a feature/fix
> ships, you MUST prepend a new entry to the `RELEASES` array in
> `apps/shell/src/pages/PatchNotesPage.tsx` **in the same commit** that
> updates `CLAUDE.md` / `CLAUDE_PERPLEXITY_WORKFLOW.md`. The Patch
> Notes are user-facing — write bilingual (`it` / `en`), user-friendly
> copy, NOT technical jargon (no file names, no internal step numbers).
> Updating the `.md` files without updating the Patch Notes is an
> incomplete step.

## Step 33 — Visual polish batch 1 (2026-05-18) ✅

Prompt 020. Four frontend-only "make it feel alive" changes. No backend, no new deps. Every animation respects `prefers-reduced-motion` and works in both colour schemes.

- **Canvas particle background.** New `apps/shell/src/components/ParticleCanvas.tsx` — a `React.memo` vanilla-Canvas2D component mounted once in `App.tsx`. **72 particles** drift, link to neighbours within 130 px, and are pushed away from the cursor (≤80 px). Ember-gold on void / ink on cream; the colour scheme is re-read live via a `MutationObserver` on `<html>`'s `data-mantine-color-scheme`. Opacity (post-QA): dark dots 0.40 / lines 0.13, light dots 0.34 / lines 0.16 (light mode was almost imperceptible at the original 0.10/0.05). Under reduced-motion nothing is drawn. Canvas is `position: fixed; z-index: 0; pointer-events: none` — it sits inside `#root` (which is `z-index: 1`, above the body noise layer); `index.css` makes `.mantine-AppShell-main` `background: transparent` in both schemes so the canvas shows through behind the cards (the body keeps `--vs-bg` as the base colour).
- **Rarity hover glow.** New `.vs-rarity` class + `data-rarity` attribute in `index.css` (post-QA revision — the original always-on gold `.vs-unique-shimmer` was replaced). A gear cell/row stays **inert until hovered**, then lights up with a diagonal shimmer sweep + a `box-shadow` glow in the **PoE rarity colour** — grey (normal) / blue (magic) / yellow (rare) / orange (unique), driven by per-`data-rarity` CSS vars (`--rarity-tint` / `--rarity-glow`). Applied to **every** `GearCell` in Analyze (`data-rarity={item.rarity}`) and every gear row in `StageCard`'s Gear tab (`kind` → rarity). Reduced-motion → glow without the sweep animation.
- **Count-up KPIs.** New `apps/shell/src/hooks/useCountUp.ts` — `requestAnimationFrame`, linear, animates on mount and on `target` change (current → new). Applied inside `AnalyzePage`'s `StatTile` so Life / ES / EHP / DPS / damage / Armour / Evasion count up; the compact formatter runs each frame. Reduced-motion → final value immediately.
- **Ember skeleton loaders.** New `.vs-skeleton` + `-text` / `-heading` / `-card` classes in `index.css` — a shimmer (`@keyframes vs-skeleton-shimmer`) over a `--vs-surface-*` gradient (flips per scheme automatically). FinderPage shows 5 stacked skeleton cards while `recommend` is pending (replaces the Mantine `<Loader>`); AnalyzePage shows a skeleton heading + 3 text rows while `analyze-pob` is pending.

Gate: 706 tests / 123 mypy / 318 ruff-format. Frontend build main 449 KB / 143 KB gzip.

## Bug — Trade dialog: unique name search + Instant Buyout default (2026-05-18) ✅ fixed

QA on the Trade dialog (Steps 31/32):

1. **Unique search by name returned nothing.** `/fob/trade-url` built `TradeQuery(name=item_name, type=None if item_name)` — it dropped the base type whenever a name was present, sending GGG a name-only query. A name-only query does not reliably resolve a unique. Fix: send **`name` + `type` together** (what the official trade site sends when you pick a unique from autocomplete). `TradeSearchDialog` now always includes `item_type`; `/fob/trade-url` passes both to `TradeQuery`.
2. **Search should default to Instant Buyout.** GGG's `/api/trade/data/filters` shows the buyout dropdown is the `status` filter — `securable` = "Instant Buyout". Added `TradeQuery.status_option` (overrides the `online_only` flag); `/fob/trade-url` sets `status_option="securable"` so every prefilled search opens on Instant Buyout. The pricer's own `TradeQuery` calls are untouched (no `status_option` → still `online`).

## Step 32 — Trade dialog: full GGG stat DB + all mods (2026-05-18) ✅

QA on Step 31: the dialog only listed mods recognised by the ~30-entry hand-written `MOD_PATTERNS` table — most of an item's mods (incl. unique-specific ones like Widowhail's quiver mod) never appeared, so the user couldn't toggle them. The dialog must show **every** mod and make as many as possible toggleable filters. Also: the modal must be bigger.

**New vendored data source — GGG's full Trade stat database.**

- `scripts/extract_trade_stats.py` — fetches `https://www.pathofexile.com/api/trade/data/stats` (~1.9 MB, every searchable stat grouped by domain), flattens it to a `{normalized_text: stat_id}` map preferring `explicit` > `implicit` > … (skips `pseudo`/`monster`), writes `packages/fob/data/trade/stats.json` (~9530 ids, 779 KB minified). Re-run per league: `uv run python scripts/extract_trade_stats.py`.
- `poe1_fob.trade_stats` — `normalize_mod_text()` (lower-case, numbers → `#`, drop `+`, strip trailing `(Local)`-style tags) makes a PoB mod line and a GGG stat template collapse to the same key. `resolve_mod()` / `resolve_mods()` then resolve any mod line to a `stat_id` (or `None`) by dict lookup. `first_number()` pulls the rolled value for the strictness slider.
- `POST /fob/extract-trade-mods` now uses `resolve_mods` instead of `MOD_PATTERNS` — it returns **every** mod line (PoB metadata lines dropped), each with `stat_id: str | None`. Coverage jumps from ~30 hand-written patterns to ~9.5k GGG stats. `ExtractedTradeMod.stat_id` / `.value` are now nullable.

**Frontend** — `TradeSearchDialog` is `size="xl"` (was `lg`); the mod list shows **all** of the item's mods. Resolved mods (a `stat_id`) are toggleable with the strictness slider; unresolved ones are listed under a "Non ricercabili su Trade" divider, dimmed. `ExtractedTradeMod` type made nullable; `value == null` mods send a presence-only filter (no `min`).

Gate: 706 tests / 123 mypy / 318 ruff-format.

## Step 31 — poe.ninja-style Trade-search dialog (2026-05-18) ✅

QA on Step 30: a plain name/base trade redirect is too coarse — for a corrupted/variable unique it returns every copy, not the user's. Replicates poe.ninja's configurable trade dialog. Backend + frontend.

**Backend (`packages/fob/src/poe1_fob/router.py`):**
- **Re-added `POST /fob/extract-trade-mods`** (removed in `b167cbc` with the old trade-search) — input `{mods: string[]}`, output `{mods: [{line, stat_id, value, label}]}`. Runs `MOD_PATTERNS` over the mod text; offline, no GGG call.
- **Extended `TradeUrlRequest`** with `stats: TradeStatFilterInput[]` (`{stat_id, min, max}` — explicit filters from the dialog, strictness already applied) and `min_links: int | None`. When `stats` is non-empty it's used verbatim (skips `mod_lines` extraction); `min_links` becomes a GGG `socket_filters` link constraint via `TradeQuery.extra_filters`.
- 2 new tests (`test_fob_router.py`): extract-trade-mods returns recognised rows; trade-url with `stats` + `min_links` reaches GGG's search body verbatim (asserts the stat id + `socket_filters.links.min`).

**Frontend:**
- **New `TradeSearchDialog.tsx`** — a Mantine `<Modal>`: a *Search by* `SegmentedControl` (unique name vs base type), a *Links* selector (Any / 5L / 6L), and a *Mods* list — each recognised mod a `<Switch>` + a 50-100 % strictness `<Slider>` (default 80; the min sent = `rolled × strictness`). Mods come from `extractTradeMods()`. "Cerca su Trade" builds a `TradeUrlRequest` and opens the prefilled URL via `openTradeUrl`.
- **`tradeRedirect.ts`** — replaced `openTradeSearch(item)` with `openTradeUrl(req: TradeUrlRequest)` (blank-tab synchronous open → `fetchTradeUrl` → navigate; bare-page fallback). `TradeRedirectItem` / `tradeClipboardText` removed.
- **`api/fob.ts`** — new `extractTradeMods()` client; **`types.ts`** — `TradeStatFilterInput`, `ExtractedTradeMod`, `TradeModExtractResponse`, `TradeUrlRequest` extended.
- **Call sites** — the Trade icon on Planner Overview rows, Planner Gear-tab rows and every Analyze equipment/flask/jewel cell now **opens the dialog** instead of redirecting straight away. `StageCard` + `BuildDashboard` hold the open-item state and render one `<TradeSearchDialog>` (keyed per item).

Scope cut: poe.ninja's *property* filters (DPS/APS/crit) are not replicated — FOB doesn't parse computed weapon stats. Search-by + per-mod strictness + links is the faithful core.

Gate: 706 tests / 121 mypy / 316 ruff-format. Frontend build: `TradeSearchDialog` lazy chunk ~18 KB.

## Step 30 — Trade prefill via backend + Planner collapsed-input fix (2026-05-18) ✅

QA on Steps 28/29 found two regressions. Both fixed here. Frontend-only, no backend / API change, no new deps.

- **Trade prefill — done properly, via the backend.** Steps 28/29 tried to reach a prefilled trade URL purely client-side (`?redirect&source=` browser navigation) — that endpoint **does not exist**; GGG returns `{"error":{"code":6,"message":"Forbidden"}}` for any direct navigation to a `pathofexile.com/api/` path. The real prefill needs a `search_id` minted by a POST to GGG's `/api/trade/search/<league>`. **Re-tested live 2026-05-18: `POST /fob/trade-url` on the Render backend successfully POSTs to GGG and returns a real `/trade/search/<league>/<id>` URL** — the 2026-05-14 "Render IP blacklisted → 403" note is **stale** (GGG unblocked the range or Render's egress IP rotated). So `openTradeSearch()` now: opens a blank tab synchronously (inside the click gesture, popup-blocker-safe, with an "Apertura ricerca…" placeholder), calls the existing `fetchTradeUrl()` client → `POST /fob/trade-url` (rate-limited + ~8 min cached server-side), and navigates the tab to the prefilled URL. Unique → `item_name` (+ base type); rare → `item_type` only. Falls back to the bare league page + clipboard copy on backend error or GGG 429 (`source: "rate_limited"`).
- **Planner collapsed-input box ballooned.** After "Genera piano" the collapsed `<Code>` chip showed the full (multi-thousand-char) PoB string and **wrapped into a huge block** — `overflow:hidden`+`textOverflow:ellipsis` only truncate single-line text. Fixed: the `<Code>` now has `whiteSpace:"nowrap"` + `minWidth:0` (the flex item must be allowed to shrink below content size), so the code truncates to one ellipsised line.

> **`tradeRedirect.ts` history note**: the module no longer copies a search term as the *primary* action — it opens a genuinely prefilled trade search. Clipboard copy survives only on the fallback path. Steps 25/28/29's "prefilled URL impossible / clipboard-only" conclusions are **superseded** — they were wrong about the Render IP block, which no longer holds.

## Step 29 — Trade redirect 403 fix + Planner input parity (2026-05-18) ✅

Prompt 019. Two frontend-only QA fixes from Steps 27/28. No backend / API change, no new deps.

- **Trade redirect 403 fix.** Step 28's `openTradeSearch()` called `window.open(url, "_blank")`. In production (Vercel origin) GGG's Cloudflare front rejected it with `{"error":{"code":6,"message":"Forbidden"}}` — `window.open` to GGG's `/api/trade/search/...?redirect` sends a `Referer` Cloudflare doesn't whitelist. Fix: navigate via a **programmatic `<a>` click** (`createElement("a")` → `appendChild` → `.click()` → `removeChild`), which the browser treats as a user-initiated link navigation that Cloudflare accepts — the same pattern poe.ninja uses. Only the navigation call in `openTradeSearch` changed; the URL/query/league/fallback logic is untouched. The fallback path (`openTradeFallback`, bare `/trade/search/<league>` page) keeps `window.open` — that's a normal page load, not the API endpoint, and was QA-passed in Step 25.
- **Planner input parity with Analyze.** Step 27 swapped the Planner `Textarea` for a `TextInput` but left it full-width standalone with the action button in a separate row. The Planner editing form now mirrors Analyze exactly: the `TextInput` (`flex={1}`) sits in a `<Group align="flex-end" wrap="nowrap">` beside the "Genera piano" button, with the "Ctrl+Enter" hint as a dimmed `<Text size="xs">` below. The Planner-specific controls (target `SegmentedControl` + reverse-mode `Switch`) moved into a single row underneath.

## Step 28 — Trade redirect v2: prefilled URLs (2026-05-18) ✅

Prompt 018. The Trade redirect now opens a **prefilled** pathofexile.com/trade search instead of the bare league page + clipboard copy. Frontend-only, no backend / API change, no new deps.

**The mechanism** — GGG's browser-navigation redirect endpoint:

```
GET https://www.pathofexile.com/api/trade/search/<league>?redirect&source=<url-encoded JSON query>
```

Opened via `window.open` (a **top-level navigation, NOT a `fetch`**), GGG runs the POST search on its own infrastructure and 302s the tab to the fully prefilled `/trade/search/<league>/<id>` results page. Because it is a navigation and not an XHR, **CORS does not apply** and no backend is involved — this is how poe.ninja opens prefilled searches. This **supersedes the Step 25 conclusion** ("true prefilled URLs impossible"): that conclusion was about a *server-side* POST (still 403 from Render's IP) and a *browser `fetch`* (still CORS-blocked) — the `?redirect&source=` navigation sidesteps both.

- **`tradeRedirect.ts`** — new `openTradeSearch(item)` replaces `openTradeForItem`. `buildTradeQuery()` builds the JSON: uniques get `name` + `type` (base), rares/magics get `type` (base) only — a rare's roll-generated name returns nothing on Trade. `stats` is always `[{type:"and",filters:[]}]`. New `getResolvedLeague()` returns the league or `null` (no fallback substitution — must not point the user at the wrong league's trade site).
- **League source** — reuses the existing `prefetchLeague()` / cached-league machinery (fed by `/health` at app mount). **No `useLeague()` hook and no `/league` endpoint were added** — `getResolvedLeague()` is synchronous, which is required to keep `window.open` inside the user-gesture window (an async React-Query read could miss it and trip popup blockers).
- **Graceful fallback** — when the league hasn't resolved yet (Render cold start) or the item has no searchable name/base, `openTradeSearch` degrades to `openTradeFallback` (bare league page + clipboard copy of the search term) and shows a `@mantine/notifications` toast. `tradeClipboardText()` is kept for that path.
- **Call sites** — the Trade `ActionIcon` on the Planner Overview rows, Planner Gear-tab rows, and every Analyze equipment/flask/jewel cell now call `openTradeSearch`. Same icon/position; only the click behaviour changed. Tooltips updated ("Apri una ricerca pre-compilata…").

## Step 27 — QA batch fixes + Zustand state persistence (2026-05-18) ✅

Prompt 017. Five frontend-only fixes. No backend / API change, no new endpoint. New npm dependency: `zustand` 5.

- **Fix 1 — Finder "Copia link" copies the PoB code.** `BuildCard`'s copy action copied the poe.ninja profile URL. It now fetches the build's PoB code via `/builds/detail` (`getDetail`) and copies that. **Deviation from the prompt**: the prompt said copy `https://pobb.in/<code>` — but pobb.in mints short IDs server-side and does NOT resolve a raw base64 code in its path (such a link 404s), so we copy the raw PoB code, which pastes straight into PoB Community / pobb.in's import box. Button relabelled "Copia PoB" / "Copy PoB".
- **Fix 2 — Analyze accepts poe.ninja character URLs.** New `parsePoeNinjaCharacterUrl()` in `api/builds.ts` extracts `account` + `character` from a `.../character/<account>/<character>` URL. `AnalyzePage`'s mutation detects a poe.ninja URL, resolves it to a PoB code via the existing `/builds/detail` endpoint, then analyses. **No new backend endpoint needed** — `/builds/detail` already hydrates any character. Pure frontend.
- **Fix 3 — light-mode colours on Analyze + Planner.** `AnalyzePage` hardcoded `var(--mantine-color-dark-N)` (which do NOT flip per scheme) on gear cells, socket separators and skill-link strips, plus a `rgba(8,6,4,0.92)` sticky header — all dark patches on cream. Replaced with `var(--vs-*)` tokens; the sticky header now uses the `.vs-glass` class (whose light override already exists). `PlannerPage`'s `PlanSummary` card had `bg="dark.7"` → `bg="var(--vs-surface-2)"`.
- **Fix 4 — Planner compact input.** The oversized autosize `<Textarea>` is now a single-line `<TextInput>` matching Analyze. The Planner input also accepts poe.ninja URLs (same resolution as Fix 2, applied inside `start()` before streaming; the resolved code is stashed in `planner.resolvedCode` and passed to stage export as `userPobCode`).
- **Fix 5 — cross-route state persistence (Zustand).** New `apps/shell/src/store/pageStore.ts` — one Zustand store, three slices (`finder` / `analyze` / `planner`). Finder/Analyze/Planner replaced their local `useState` for query/result/filters/intent/editing/activeStage with store reads/writes, so navigating away and back no longer resets them. Transient flags (SSE `progress`, `error`, `running`, per-action loading) stay as local `useState` — they must reset. `persist` middleware mirrors the store to `sessionStorage` (survives in-session reload, not across sessions); a `resilientStorage` wrapper falls back to an in-memory `Map` when `sessionStorage` throws (private mode, sandboxed iframe).

Planner gotcha: `start()` gained an optional `codeOverride` arg so the `initialInput` effect (Finder "Pianifica →" lift) can drive a run without waiting for a store commit to round-trip. The effect skips auto-firing when the store already holds that same input (avoids re-running a restored plan on navbar-return).

Gate: 704 tests / 121 mypy / 316 ruff-format. Frontend build: main 440 KB / 140 KB gzip + a 29 KB `pageStore` chunk (zustand).

## Step 26 — Route-level code-splitting (2026-05-18) ✅

Prompt 016. The Vite build had been warning that the single bundle exceeded 500 KB. `App.tsx` now lazy-loads the three heaviest feature pages. Frontend-only, no behaviour change.

- **`App.tsx`** — `FinderPage`, `AnalyzePage`, `PlannerPage` are now `React.lazy(() => import(...).then(m => ({ default: m.XPage })))` (named-export adapter). The `<Routes>` is wrapped in `<Suspense fallback={<RouteFallback/>}>`. `HomePage` / `WelcomePage` / `PatchNotesPage` stay eager (small, and Home is the usual first render).
- **`RouteFallback`** — a small inline centred loader (Mantine `Loader color="ember"` + Cinzel "Evoco la pagina…" bilingual). Lives inside `AppShell.Main`, so the navbar/header stay put; it never overlaps the full-viewport `WarmupOverlay` (which sits at a higher z-index during the Render cold-start).

Result: initial bundle **616 KB → 438 KB** (gzip 192 → 139 KB), Vite chunk-size warning gone. Split chunks: `FinderPage` 91 KB, `PlannerPage` 35 KB, `AnalyzePage` 17 KB, plus shared `fob` / `ErrorBoundary` chunks.

## Step 25 — Trade redirect on Planner gear + Analyze equipment (2026-05-18) ✅

Prompt 015. Extends the existing client-side Trade redirect (already on the Planner *Overview* tab item rows) to two more surfaces. Frontend-only, no backend / API change.

- **`tradeRedirect.ts`** — new exported `tradeClipboardText(item)` picks the most useful search term: the **unique name** for uniques, the **base type** for rares/magics (a rolled rare name returns nothing on Trade — the base type is what the user actually searches). `openTradeForItem` now copies that smart term instead of always the name.
- **Planner Gear tab** (`GearPanel` in `StageCard.tsx`) — each `StageGearSlot` row gets a Trade `ActionIcon` for `kind ∈ {unique, leveling}` (real, searchable item names). `rare_craft` (a description, not a name) and `skip` get no link.
- **Analyze equipment** (`GearCell` in `AnalyzePage.tsx`) — every populated gear/flask/jewel cell gets a small Trade `ActionIcon` in its header. Uniques copy the name, rares copy the base type.

**Why no true prefilled Trade URL**: GGG's `/api/trade/search` (the call that mints a `search_id` for a prefilled `/trade/search/<league>/<id>` URL) returns HTTP 403 from Render's datacenter IP range, and a direct browser `fetch` to it from the SPA fails CORS. So a genuinely prefilled Trade link is unreachable from the deployed app. The redirect opens the bare league search page and pre-copies the search term to the clipboard — one paste away from the result. This limitation is documented at length in `tradeRedirect.ts`.

Build 616 KB / 192 KB gzip.

## Step 24 — Finder result-list polish (2026-05-18) ✅

Prompt 014. Three frontend-only enrichments on `/finder`, no backend / API change.

- **Active sort indicator.** When `sort_by != "score"` the result header shows a `<Badge>` (`IconSortDescending`) — e.g. "Ordinato per DPS ↓" — so the user sees the list isn't fit-ranked. The plain `<Divider>` count label was replaced by a `<Group justify="space-between">` header.
- **"X% del meta" per BuildCard.** `FinderPage` runs a `useQuery(["population-stats", ascCapitalised])` — **same query key as `PopulationStatsPanel`**, so TanStack dedupes and it adds no extra HTTP call. `enabled: !!result` (only after a search). The `top_skills` are flattened into a `Map<lowercased skill, pct>`; each `BuildCard` gets a `metaPct` prop and renders a small outline ember `<Badge>` "{pct}% del meta" next to the level when its main skill is in the ladder top-skills.
- **Per-skill drill-down.** The main-skill name on a `BuildCard` is now clickable (`.drill-skill` CSS hover → ember + underline). Clicking calls `onDrillSkill(skill)` → `FinderPage` `skillFilter` state filters the ranked list client-side to that skill. A removable `<Pill>` chip ("skill: X ✕") shows the active filter; clicking the same skill again toggles it off. No re-fetch — pure client-side filter over the existing result set.

`skillFilter` resets on every new extract / recommend. Build 615 KB / 192 KB gzip.

## Bug — Finder result cards muddy grey in light mode (2026-05-17) ✅ fixed

QA: the Build Finder result cards rendered as an embarrassing muddy
grey/brown on the cream parchment background in light mode. Root cause:
`.vs-glass` (the glassmorphism class on `BuildCard`) hardcoded a dark
void rgba `rgba(17, 16, 9, 0.62)` inside its `@supports (backdrop-filter)`
block — that dark translucent fill applied in **both** colour schemes.
On the cream light background it became a dim grey wash.

Fix (`index.css`, frontend-only): added a
`[data-mantine-color-scheme="light"] .vs-glass` override inside the same
`@supports` block that uses a translucent warm cream tint
`rgba(237, 229, 210, 0.78)`, so the card stays a light parchment surface
in light mode while dark mode keeps the void rgba.

## Step 23 — Parchment light mode (2026-05-15) ✅

The `colorScheme` toggle in the header existed but light mode was broken — Mantine fell back to its default white/black/violet palette, white-on-white in places. Step 23 defines the "Parchment" light mode that pairs with the "Void Stone & Ember" dark mode. Frontend-only, zero layout changes, no new deps.

- **`index.css`** — new `[data-mantine-color-scheme="light"]` block (Mantine v7 stamps that attribute on `<html>`) overrides every `--vs-*` token: warm cream backgrounds, dark-walnut ink text, ember gold *darkened* to `#b07820` so it clears WCAG 4.5:1 on cream (ember stays an accent, never body text). The whole design system cascades from those vars, so nothing else needed per-component changes for the main surfaces. Plus: stronger noise opacity (`0.04`) and an `!important` AppShell-main background pin for light mode.
- **Two fixes that also tighten dark mode**:
  - `.mantine-Input-input` now sets `background: var(--vs-surface-2)` / `border-color: var(--vs-border-faint)` / `color: var(--vs-text)` explicitly. Before, inputs took Mantine's per-scheme `white`/`dark` defaults — in light mode that surfaced the `white` theme token (`#e2d5b8`) instead of the cream surface.
  - `--mantine-color-dimmed` is remapped to `var(--vs-text-muted)` in the light block (`!important` — Mantine sets it at higher specificity). Mantine's default dimmed grey `#868e96` fails contrast on cream; sepia `#6b5a3e` passes.

**Mantine v7 colour-scheme-var gotcha**: Mantine sets its built-in CSS vars (`--mantine-color-dimmed`, etc.) on a higher-specificity selector than a plain `[data-mantine-color-scheme="light"]` block. To override one, use `!important` on the custom-property declaration (custom properties accept `!important`).

`theme.ts` needed no changes — its only hardcoded hex are the legitimate `ember`/`blood`/`dark` colour ramps + `black`/`white` base tokens; component styling lives entirely in `index.css` global rules keyed off `var(--vs-*)`.

## Bug — Step 22 QA: filter row clipped + Analyze stats hidden (2026-05-15) ✅ fixed

Two QA findings on the Step 22 redesign:

1. **Finder filter pill row clipped on wide screens.** `.finder-filter-row` used `overflow-x: auto` — on a large monitor the row didn't wrap and "Trova build" / "Reset" scrolled off the right edge, invisible. Fix: `flex-wrap: wrap` so every control wraps onto as many lines as needed and is always visible. Also bumped the app `<Container>` from `size="lg"` to `size="xl"` so the central content uses more of a wide screen.
2. **Analyze page hid Vita / Energy Shield / EHP.** The Step 22c sticky character header was a `position: sticky` Box **inside** the left dashboard card, with negative margins — once the page scrolled it overlaid the card's own first stat tiles. Fix: the character header is now a standalone full-width sticky bar **above** the `.analyze-dashboard` grid (no negative margins), so it never covers the stat tiles. All 7 key stats (Vita, ES, EHP, DPS, top damage, Armour, Evasion) render.

**Lesson**: a `position: sticky` element overlays siblings that scroll under it — never make a header sticky *inside* the same card whose content sits directly below it. Put the sticky header in its own element above the scrolling content.

## Step 22c — Planner timeline + Analyze polish (2026-05-15) ✅

Final slice of the frontend redesign. Frontend-only, no backend / API contract change.

**Planner** (`PlannerPage.tsx`):
- New `StageTimeline` component — on desktop (≥1024 px) the 6 stacked `StageCard`s become a horizontal Roman-numeral timeline (I–VI dots on an ember-trace line, stage name below each). Clicking a dot expands that stage's `StageCard` inline below the timeline; one open at a time, `vs-card-reveal` keyed on the active index so the panel re-animates on switch. Mobile (<1024 px) keeps the vertical stacked layout. Desktop/mobile split via `useMediaQuery("(min-width: 1024px)")` (defaults to desktop to avoid a flash).
- The input form collapses to a compact `<Code>` + "modifica" row once a plan starts streaming (same pattern as Finder/Analyze).
- Note: the SSE stream emits `PricingProgress` (per priced item), not per-stage events — the full `BuildPlan` only arrives on the `done` event. So the timeline dots fan in with a staggered CSS reveal when the plan renders rather than streaming stage-by-stage; the `PricingProgressBar` covers the streaming phase.

**Analyze** (`AnalyzePage.tsx`) — cosmetic polish:
- Character header is `position: sticky; top: 56px` (just below the AppShell header) with a blurred void background.
- `rarityColor()` now returns the `--vs-normal/magic/rare/unique` CSS variables instead of hardcoded hex.
- Key-stat values use the `.mono` (Geist Mono) class.
- The three dashboard cards carry `vs-card-reveal` (indices 0/2/4 → ~100 ms stagger).

## Step 22b — Finder page redesign (2026-05-15) ✅

Second slice of the frontend redesign, on top of the 22a design system. Rebuilds `FinderPage.tsx` into the "oracle" interface and restyles the result card. Frontend-only, no backend / API contract change.

- **`FinderPage.tsx`** — rewritten. Centred hero search (H2 "Consulta l'oracolo" + Textarea + ember button) that **collapses** to a compact `<Code>` query chip + "modifica" link after a successful extract (mirrors the AnalyzePage `editing` pattern). Filters moved to a single horizontal **pill row** (`.finder-filter-row`, `size="xs"` Selects/NumberInputs, scrolls horizontally on mobile) — replaces the old collapsible "Filtri avanzati" panel. Two-column layout via `.finder-grid` (results 2fr + meta sidebar 1fr at ≥1024 px, single column below). The `PopulationStatsPanel` lives in the sidebar — on mobile it sits above the results via CSS `order` (`.finder-sidebar`). New `OracleEmptyState` (eye icon + Italian copy) shown before any search and while no result set is loaded.
- **`BuildCard.tsx`** — result card restyled. Two-row header: row 1 = score ring + class badge (ember) + main skill + `— Lv. N` (Geist Mono) + rank `#N` (Cinzel ember, right edge); row 2 = three `StatChip`s (Life red, DPS ember, EHP gem-teal, values in Geist Mono) + the Pianifica / Apri PoB / Copia link actions. Accepts an `index` prop that drives the staggered reveal. Expand section (score breakdown + lazy main gems) unchanged.
- **`index.css`** — `.finder-grid` / `.finder-filter-row` / `.finder-sidebar` layout, `.vs-glass` glassmorphism (`backdrop-filter: blur(8px)` with an `@supports` solid fallback), `vs-card-reveal` keyframe + `--card-index` stagger (disabled under `prefers-reduced-motion`).

All existing Finder functionality preserved — NL extraction, class/asc/stat-floor filters, sort, population stats, the recommend flow.

## Step 22a — Void Stone & Ember design system (2026-05-15) ✅

First slice of the full frontend redesign. Replaces the old Atlas-violet theme with the "Void Stone & Ember" design system — system-level tokens only, **zero layout changes** (per-page redesigns are Steps 22b/22c). Frontend-only, no backend change, no new npm deps.

- **`theme.ts`** — rewritten. Three Mantine colour ramps: `ember` (primary, shade 6 `#c8932a`), `blood` (rare-tier / warnings), and **`dark`** — overriding Mantine's built-in `dark` tuple is what auto-themes the void background, parchment text, warm card/input surfaces and borders without per-component CSS. `autoContrast: true` + `luminanceThreshold: 0.3` so filled ember buttons get near-black text (the gold accent sits just above the threshold). Fonts: Cabinet Grotesk (body), Cinzel (headings), Geist Mono (numbers).
- **`index.css`** — rewritten. `:root` design tokens (`--vs-*`), void body background + a CSS-only parchment-noise `body::before` overlay, `h1/h2` forced to Cinzel (over Mantine's Title class), ember scrollbar/selection. **Mantine-v7 gotcha**: the `styles` prop takes flat CSS properties only — no `&:hover`/`&:focus` nesting — so interactive states (card ember border + hover glow, input focus ring, button hover glow) live here as global rules against `.mantine-*` classes.
- **`index.html`** — added `<link>`s for Cabinet Grotesk (Fontshare), Cinzel + Geist Mono (Google Fonts).
- **`App.tsx`** — header/navbar recoloured to `var(--vs-*)` tokens, brand "FOB" in Cinzel ember.
- Recoloured every `color="astral"` / `color="gold"` prop across components to `color="ember"`, and the hardcoded violet `rgba(110,38,255,…)` values in Home/Welcome to ember — colour-only, no structural change.

**Mantine v7 default-Button gotcha**: a `<Button>` with no explicit `variant` (default "filled") emits **no** `data-variant` attribute. CSS that targets filled buttons must use `.mantine-Button-root:not([data-variant])` as well as `[data-variant="filled"]`.

## Step 21 — Divine Orb cold-start overlay (2026-05-15) ✅

Render's free tier spins the backend down after 15 min idle; the first request then takes ~30 s. New users saw no feedback and assumed the site was broken. Added an app-level loading overlay. Frontend-only — no backend change.

- **`apps/shell/src/hooks/useServerWarmup.ts`** — fires one `GET /health` probe on mount. Returns `"probing"` → `"cold"` (probe still pending after 3 s) → `"warm"` (probe settled, ok/error/non-2xx alike — a failed probe never traps the user behind the overlay).
- **`apps/shell/src/components/WarmupOverlay.tsx`** — full-viewport `fixed` overlay (z-index 9999) shown only on `"cold"`, fades out over 600 ms once `"warm"`. The loading indicator is a hand-authored inline SVG **Divine Orb** (PoE 1 currency aesthetic — golden radial-gradient sphere, classical female face in bas-relief, 14 ornamental studs, specular highlight). No external image, no animation library.
- **`index.css`** — `@keyframes` for the orb pulse / glow / orbiting-ring; all disabled under `prefers-reduced-motion`.
- Mounted in `App.tsx` at the root, above every route (welcome + shell branches).

**Verification note**: the cold-start path can't be cleanly exercised in the local preview harness — editing a hook file triggers a full Vite reload that wipes any in-page `window.fetch` patch, so the delayed-`/health` simulation resets before the probe runs. Verified instead by (a) forcing the hook to `"cold"` and confirming the overlay renders with the correct SVG/styles/text via DOM inspection, and (b) confirming the warm path (fast probe → no overlay).

## Step 20 — Analyze page full redesign (2026-05-15) ✅

QA flagged `/analyze` as low-value — it showed only four badges (class, ascendancy, main skill, level). Fully rebuilt `apps/shell/src/pages/AnalyzePage.tsx` into a PoB-style dashboard. Frontend-only — `POST /fob/analyze-pob` already returns the full `PobSnapshot`; no backend / API contract change.

- **`apps/shell/src/api/types.ts`** — the opaque `snapshot: Record<string, unknown>` is replaced by typed interfaces mirroring `poe1_fob.pob.models`: `PobGem`, `PobSkillGroup`, `PobItem`, `PobJewel`, `PobPassiveTree`, `PobPantheon`, `PobConfigOption`, `PobSnapshot`. Snake_case keys, no aliases (the Pydantic models define none).
- **`AnalyzePage.tsx`** — compact single-line `<TextInput>` that collapses to a `<Code>` chip + "modifica" link after a successful analysis. Two-column dashboard (`.analyze-dashboard`, single column < 768 px):
  - Left: character header + key-stats grid (Life / ES / EHP / DPS / top damage type / Armour / Evasion read from `snapshot.stats`), passive-tree link, build notes in an `<Accordion>`.
  - Right: equipment grid via CSS `grid-template-areas` (helmet centred, weapons flanking body, etc.), 3px left-border rarity colour (normal grey / magic blue / rare gold / unique brown), `<Tooltip>` per item with implicits/explicits, socket dots, corrupted "C" badge. Flask row + tree-jewel grid below.
  - Full-width skill-link panel: one strip per enabled `PobSkillGroup`, active gems filled / supports outlined, disabled gems at 40% opacity.
- The whole result is wrapped in `<ErrorBoundary>`.

**Gotcha — `PobSkillGroup.is_main` is NOT "the main group".** The parser sets `is_main` from PoB's per-`<Skill>` `mainActiveSkill` attribute, which PoB stamps on *every* group that has a main active skill selected — so it is true on almost all groups. The single main group is `PobSnapshot.main_skill_group_index` (1-based, matched against `socket_group`). Use that, not `is_main`, to highlight the main skill.

**Mantine nesting gotcha**: a `<Badge>` (renders `<div>`) inside a `<Text>` (renders `<p>`) trips React's `validateDOMNesting`. Put the badge as a sibling inside a `<Group>`, not nested in the `<Text>`.

> Note: a stale `.clone/worktrees/...` directory may exist locally from
> earlier Claude sessions and trip ruff on its placeholder file. Run the
> gate from a fresh checkout, or pass `--exclude .clone` /
> `--ignore=.clone` to the relevant tools — it is *not* a real repo file.

## Bug — Finder blank page (2026-05-15) ✅ fixed (took two passes)

QA found the Build Finder going blank after "Analizza query": `TypeError: Cannot read properties of undefined (reading 'map')` unmounted the entire `FinderPage` subtree because the page had no `ErrorBoundary`.

**Root cause (pass 2)**: `<Select data={CLASS_OPTIONS}>` in the filter panel was receiving Mantine v6's flat grouped data shape `[{value, label, group}, ...]`. Mantine v7 requires the new grouped shape `[{group, items: [{value, label}, ...]}, ...]` — when v7 sees `group` on a flat item it tries to `.map` the (nonexistent) `items` array on the internal `useMemo` and crashes BEFORE our render runs, so the first round of ErrorBoundaries (which wrapped IntentCard / PopulationStatsPanel) never got a chance to catch it.

Frontend-only defensive fix (no backend / API contract change):

- **`apps/shell/src/components/ErrorBoundary.tsx`** new — generic React error boundary. Renders a Mantine `<Alert color="red">` with the error message instead of letting an exception propagate up to the AppShell. Logs to `console.error` so the stack is still visible in DevTools.
- **`apps/shell/src/components/IntentCard.tsx`** — defaults `intent.hard_constraints`, `intent.content_focus`, `intent.confidence`, and `intent.parser_origin` against `undefined`/`null` payloads (older deploys, broken caches, ad-blocker JSON rewrites). `ContentFocusPills` accepts `items | null | undefined`.
- **`apps/shell/src/components/PopulationStatsPanel.tsx`** — `stats.top_skills` and `stats.total_builds` defaulted.
- **`apps/shell/src/pages/FinderPage.tsx`** —
  - `result.ranked` and `result.total_candidates` defaulted.
  - `CLASS_OPTIONS` rewritten to Mantine v7's grouped data shape — this was the actual root cause.
  - The entire `{intent && …}` block is now wrapped in a top-level `<ErrorBoundary>` (with two nested ones around the intent card and population panel) so a crash anywhere in the post-extract panel — including in `<Select>` / `<Collapse>` — renders an inline alert instead of blanking the page.

**Mantine v7 grouped-data invariant**: when a `<Select>`, `<MultiSelect>`, or `<Autocomplete>` needs option groups, the `data` prop must be `[{group: "X", items: [{value, label}, ...]}, ...]`. **Never** pass a flat array with a `group` field per item — Mantine v7 will crash on a `useMemo` during the very first render and your ErrorBoundary won't help unless it wraps that subtree too.

Frontend build 567 KB / 176 KB gzip.

**PoB import QA — confirmed working 2026-05-14**: real PoB → planner → "Importa stage in PoB" → paste in PoB Community 3.28 desktop → full build loads (tree 123/123 nodes including cluster jewel subgraph, mastery effects, items, gems, config, pantheon). Took 7 commits to debug, all guided by reading PathOfBuildingCommunity Lua source. Key learnings captured below.

## Bug — Stage export emitted fake items + mis-labelled gems + PoB calc crash (2026-05-15) ✅ fixed

QA found "Importa stage in PoB" producing a build where items were mod-less placeholders (a "Crafted Helmet" with no stats; uniques with `Implicits: 0` and no explicit block) and gem groups showed the gear slot ("Body Armour") as the Main Skill instead of the actual gem. A second QA pass found PoB Community v2.65.0 also **crashing on import** in its DPS-calc phase: `Data/Skills/other.lua:5364: attempt to index field 'explodeSource' (a nil value)`.

**Root cause**: `encode_pob_code` inverted the precedence. When a user PoB was passed, the encoder still let the synthesised `gear`/`gems` parameters win — and since `derive_gear_progression` / `derive_gem_progression` *always* return something for a snapshot, the encoder *always* synthesised placeholder items + slot-labelled gem stubs and *never* passed through the user's real `<Items>`/`<Skills>`. That also silently dropped cluster jewels (the passthrough is what carries them).

Fix in `packages/fob/src/poe1_fob/pob/encode.py`:

- **Passthrough wins.** When `passthrough_user_pob` is supplied, the user's real `<Items>` and `<Skills>` are copied verbatim — real mods, real gem links, cluster jewels intact. The per-stage `gear`/`gems` parameters now only synthesise a block in the **no-PoB case**. Only the passive `tree` differs per stage; the exported build stays playable. The per-stage gear/gem *advice* still lives in the StageCard "Gear"/"Gems" tabs.
- **Synth-path gem label fixed.** The no-PoB synth path stamped the gear slot name into `<Skill label>`, making PoB show "Body Armour" as the skill name. Now emits `label=""` so PoB auto-derives the group name from the first active gem.

2 new tests in `test_pob_encode.py` verify the user's real items/skills survive even when a conflicting `gear`/`gems` param is also passed.

**This also resolves the `explodeSource` PoB crash.** That crash fired during PoB's offence calc — the only synthesised XML feeding the calc was the `<Skills>` block, and a synthesised gem group PoB couldn't resolve made it index `explodeSource` on a nil skill table. Passing through the user's real `<Skills>` (which by definition calc cleanly — they came from PoB) removes the crash source. No separate fix was needed; pending a user re-QA to confirm in PoB Community.

## Step 19 — Population stats in Finder (2026-05-15) ✅

Closes the dynamic-pivot quadrant. Surfaces aggregated `poe.ninja` ladder stats in the Build Finder so the user can see "what does the current Slayer meta look like" before committing to a recommend pool.

- New `poe1_builds.population` module — pure aggregator (no HTTP, no state). Three Pydantic envelopes:
  - `SkillPopularity(skill, count, pct)` — one row of the top-skills table.
  - `StatDistribution(sample_size, p25, p50, p75, p90)` — quantile snapshot for one stat.
  - `PopulationStats(ascendancy, total_builds, top_skills, life, energy_shield, ehp, dps, level)` — full envelope.
- `compute_population_stats(refs, *, ascendancy=None, top_n_skills=10)` aggregates over a tuple of `RemoteBuildRef`:
  - Skill popularity via `collections.Counter`; percentages computed over the with-skill subset (refs missing `main_skill` are excluded from the rank table but still counted in `total_builds`).
  - Stat distributions via nearest-rank percentile (no interpolation — integer outputs read better in the UI; zero values are dropped before sorting).
- New endpoint `GET /builds/population-stats?ascendancy=&top_n_per_class=&top_n_skills=&league=` in `poe1_builds.router`. Reuses `BuildsService.fetch_refs` so the underlying ladder fetch hits the existing `diskcache` 15 min TTL — zero new HTTP cost on cache hits.
- Frontend:
  - New `apps/shell/src/components/PopulationStatsPanel.tsx` — TanStack-Query-backed panel rendered above the Finder filter row when an ascendancy filter is active. Shows top-5 skills as Mantine `<Badge>`s (first one filled astral, rest light gray) + a 5-row stat table (Vita / ES / EHP / DPS / Livello) with p25 / p50 / p75 / p90 columns. Compact-number formatter (`5.5k`, `1.2M`).
  - `getPopulationStats(ascendancy?)` client in `apps/shell/src/api/builds.ts`.
  - `FinderPage` shows the panel under the parsed `IntentCard` and reacts to the user's class/ascendancy override (so changing the dropdown in "Filtri avanzati" instantly updates the panel via the TanStack cache key).
- **11 new tests** (`packages/builds/tests/test_population.py`) — empty pool, top-skills ordering + cap, missing-main-skill exclusion, quantile correctness on a hand-verified DPS distribution, zero-value drops, ascendancy passthrough, all-zero-stats envelope returns None.

Baseline: 702 verdi / 119 mypy / 117 format. Frontend build 566 KB / 172 KB gzip (+14 KB raw for the panel + types).

## Step 17 — Dynamic Gear Progression (2026-05-15) ✅

Third slice of the dynamic-synthesis pivot. Replaces `gear_progression_for(template_name)` for any build with a pasted PoB. The dynamic-pivot trio (16 / 17 / 18) is now complete; only Step 19 (population data) remains.

- New `scripts/extract_base_items.py` — fetches `repoe-fork/repoe-fork.github.io` `base_items.json` (7.3 MB, 5052 entries), filters to **released gear bases only** (1034 entries spanning every PoB slot), slims schema to {name, item_class, drop_level, tags, implicits, inherits_from, requirements}, writes minified `packages/fob/data/items/base_items.json` (~357 KB).
- New `poe1_fob.gear.base_items` — lazy-cached loader exposing:
  - `BaseItem` dataclass with PoE name + item_class + slot mapping + tags.
  - `get_base_catalogue()` → all 1034 bases.
  - `base_for_name("Stygian Vise") → BaseItem` (canonical-name lookup).
  - `bases_for_slot(ItemSlot.BODY_ARMOUR) → tuple[BaseItem, ...]` (substitution picker source).
- New `poe1_fob.gear.dynamic.derive_gear_progression(snapshot, prices=None)`:
  1. Classify each user item into one of 8 tiers (`mirror` / `mageblood` / `high` / `mid` / `cheap` / `leveling` / `cluster` / `rare_craft`). Cluster-jewel detection via base-type name; uniques classified by `prices[name]` when supplied, else by name-signature heuristic over ~40 famous uniques (Mageblood, Headhunter, Kaom's Heart, Goldrim, Tabula Rasa, …).
  2. Per-stage tier ceiling (`leveling` → `cheap` → `mid` → `high` → `mirror` → `mirror`). User item fits ⇒ keep. Otherwise substitute.
  3. Substitution: stage 1-2 → canonical leveling unique per slot (Goldrim, Wanderlust, Tabula Rasa, …); stage 3+ → generic rare-craft placeholder describing the typical mod set ("rare body 6L (life + 2 res)").
  4. Pricing is **optional** — when `prices=None`, the deterministic name-signature path covers the ~40 expensive uniques. Async pricing fetch is the caller's responsibility (router doesn't fetch on the hot path to keep stage-export network-free).
- **Router wiring**: `_compose_stage_export` prefers `derive_gear_progression` over `gear_progression_for` when a snapshot is available. Same pattern as Steps 16+18: registry stays as fallback for the no-PoB case.
- **27 new tests** (`test_gear_dynamic.py`) — base catalogue shape, slot-mapping lookup, tier classification with + without prices, cluster detection, stage budget thresholds (parametrised), end-to-end on the real fixture (high_investment covers every user slot; early_campaign substitutes mid+ uniques with leveling placeholders).
- **pre-commit** `check-added-large-files` already at 5000 KB ceiling from Step 16; base_items.json (357 KB) fits comfortably.

Baseline: 691 verdi / 117 mypy / 115 format.

Operational note: re-run `python scripts/extract_base_items.py` after each PoE league to refresh the catalogue. The upstream `repoe-fork/repoe-fork.github.io` lags one league behind 3.28 — acceptable since gear bases rarely change between minor patches.

## Step 16 — Dynamic Tree Progression (2026-05-14) ✅

Second slice of the dynamic-synthesis pivot. Replaces hand-curated `PROGRESSION_REGISTRY` for any build where the user pastes a PoB.

- New `scripts/extract_tree_data.py` — pulls GGG's `passiveSkillTreeData` JS variable from `https://www.pathofexile.com/passive-skill-tree`, brace-matches the embedded `{...}`, validates as JSON, writes `packages/fob/data/tree/<version>.json`. 4.7 MB pretty-printed; 3338 regular tree nodes + 7 classes + 19 ascendancies + ~350 mastery nodes.
- New `poe1_fob.tree.tree_data` — lazy loader cached via `lru_cache`. Builds:
  - `nodes_by_id: dict[int, TreeNode]` with type flags (`is_keystone`/`is_notable`/`is_mastery`/`is_ascendancy_start`), name, ascendancy membership, outgoing edges.
  - `class_starts: dict[class_index, node_id]` — 0=Scion, 1=Marauder, ..., 6=Shadow.
  - `ascendancy_starts: dict[ascendancy_name, node_id]` — Juggernaut, Berserker, Chieftain, etc.
  - **Symmetric `adjacency: dict[int, frozenset[int]]`** — GGG stores `in`/`out` separately but the tree is undirected, so the loader pre-unions both sides. Verified asymmetric edges = 0.
- New `poe1_fob.tree.dynamic.derive_tree_progression(snapshot) -> TreeProgression | None`:
  1. Partition user's `node_ids` into regular / ascendancy / mastery / cluster (>= 65536).
  2. BFS the regular subgraph from `class_starts[class_id]` — distances reflect natural allocation order.
  3. Bucket regular nodes into 6 cumulative supersets at coverage 10% / 25% / 50% / 70% / 85% / 100%.
  4. Ascendancy: BFS from `ascendancy_starts[name]`, distribute in lab order (lab 1 → stage 2, ..., lab 4 → stage 5), 2 points per lab.
  5. Mastery nodes only appear from stage 4 onward (you don't socket masteries while leveling).
  6. Cluster-jewel notables: stage 6 only (PoB generates these subgraphs, not in GGG data).
- **Router wiring**: `_compose_stage_export` now prefers dynamic synthesis over the curated registry when a `user_pob_code` is provided. Priority is `dynamic` > `progression` > `user_pob` (verbatim fallback) > `empty`. The new `tree_source="dynamic"` value is documented in `StageExportResponse.tree_source`.
- **14 new tests** (`test_tree_dynamic.py`) — loader shape + symmetric adjacency + class-to-ascendancy edges + bucket monotonicity + coverage fractions + end-to-end on real fixture (6 monotone supersets summing to user's exact 134-node allocation; cluster nodes only in final stage; mastery effects propagated).

Baseline: 664 verdi / 114 mypy / 112 format.

Operational note: after each PoE league change, re-run `python scripts/extract_tree_data.py` and commit the new JSON. The script fetches from GGG's official `/passive-skill-tree` page (no auth, no rate-limit). Per CLAUDE.md "External data sources" section: vendor-not-fetch, MIT-licensed via GGG's public-facing data.

## Step 18 — Dynamic Gem Progression (2026-05-14) ✅

First slice of the dynamic-synthesis pivot. Replaces the hand-curated `gem_progression_for(template_name)` lookup with `derive_gem_progression(snapshot: PobSnapshot)` — works for **every** build the user can paste, not just `rf_pohx`.

- New module `packages/fob/src/poe1_fob/gems/dynamic.py`. Per gem in the user's PoB, projects six `GemSpec` snapshots across the campaign→endgame curve via `_project_level_quality(user_level, user_quality, stage_index)`.
- **Awakened normalisation**: stages 0-2 substitute `Awakened X Support` with the base `X Support` (Awakened gems don't exist at lvl 30). Stage 3 emerges Awakened lvl 1, stage 4 lvl 3, stage 5 the user's actual level.
- **Vaal normalisation**: stages 0-1 strip the `Vaal ` prefix (the Vaal corruption is a late-game step). Stage 2+ keeps the Vaal variant.
- **Trigger gems** (`Cast When Damage Taken`, `Cast On Critical Strike`, `Cast While Channelling`, `Cast On Death`): level **pinned across all stages** to the user's chosen value. Their mechanical threshold (CWDT damage breakpoint) breaks if we downscale.
- **Aura-like gems** (Clarity / Vitality / heralds / purity auras / Hatred / Determination / …): mild downscale only (50% / 70% / 85% of user's level for stages 0-2).
- **Parser fix**: `<Skill slot="Body Armour">` was being parsed into `PobSkillGroup.label` (which is empty in real PoB exports — they use `slot`, not `label`). Added `slot: str | None` to `PobSkillGroup` so the dynamic engine can map gem groups to gear slots accurately.
- **Router wiring**: `_compose_stage_export` now decodes the user PoB once at the top and prefers the dynamic gem progression over the curated registry. Registry stays as the fallback for the no-PoB case.
- **21 new tests** (`test_gems_dynamic.py`) — level/quality projection math, Awakened/Vaal/trigger handling, slot mapping, end-to-end against the real fixture (Spectre Necro, 9 skill groups including 2 Awakened supports, alt-quality Companionship, Vitality aura). The `high_investment` stage's gem set must equal the user's actual gem set verbatim.

Baseline: 649 verdi / 111 mypy / 109 format.

## Step 15 — Finder search improvements (2026-05-14) ✅

Added filter / sort / class-filter to the Build Finder, plus extended the NL intent extractor:

- **`BuildIntent` new fields**: `class_filter` (base class OR ascendancy), `min_life` / `min_es` / `min_ehp` / `min_dps` / `min_level` / `max_level`, `sort_by: SortKey` enum (`score` | `dps` | `life` | `ehp` | `level`).
- **`RankingEngine`** extended: `filter_stat_floors()` post-filter drops refs below the intent's stat floors; `_sort_key_for()` swaps the primary sort dimension when `intent.sort_by != SCORE`, keeping fit-score as tiebreaker.
- **`IntentExtractor` rules**: new synonym tables for ascendancies (Juggernaut/Berserker/.../Ascendant) + base classes (Marauder/Witch/...), sort phrases ("ordina per dps", "max ehp"), and regex-based stat-number parser supporting `k`/`m` suffixes + `minimo`/`almeno`/`at least`/`>=` prefixes. Queries like *"spectre necromancer per bossing, almeno 1m dps e 8000 ehp, ordina per ehp"* extract cleanly.
- **Frontend**: `FinderPage` shows a collapsible "Filtri avanzati" panel after the intent is parsed — user can refine class, min Life/ES/EHP/DPS, level range, and sort. The panel auto-opens when the extractor surfaced a non-default filter from the NL query, so the user sees what was extracted at a glance. `IntentCard` renders the new fields as colored badges.
- **20 new tests** (12 ranking + 8 rule extractor) cover the floor filters, ascendancy-vs-base-class matching, sort_by override, and combined natural-language queries.

### Lessons from the PoB-import-debug sprint

1. **`<Build targetVersion>` is `3_0`, NOT the league.** That attribute tags "this is a PoE 1 build" (vs PoE 2). The league/tree version lives on `<Spec treeVersion>` (currently `3_28`). Setting targetVersion to the league number triggers PoB's "Game Version" conversion dialog.
2. **`<PathOfBuilding>` root has NO attributes.** Adding `version="2"` made PoB treat the code as foreign-format.
3. **Tree URL v6 header is 7 bytes, byte 6 = nodeCount.** PoB's `DecodeURL` reads exactly nodeCount * 2 bytes for the regular-node section. Header layout: `[ver:u32be][class:u8][ascendancyIds:u8][nodeCount:u8]` then nodes (u16be), then clusterCount + cluster nodes (u16be each), then masteryCount + mastery pairs (effect:u16be + node:u16be).
4. **PoB uses `<Spec nodes>` attribute over `<URL>` when both present** — the URL is mostly cosmetic for the website preview. The attribute is authoritative.
5. **Cluster jewel notable node IDs are >= 65536** and live in a separate section of the URL. They survive on the attribute. PoB allocates them only when the matching cluster jewel ITEM is present in `<Items>`.
6. **Mastery nodes are silently dropped** from `<Spec nodes>` unless the same node id appears in `<Spec masteryEffects>` as `{node,effect}`. Round trip both or PoB shows ~30% of allocated points missing.
7. **PoB's "patch-the-user-PoB" pattern wins**: instead of synthesizing every section (Calcs, Party, Config, Import, TreeView, …), the encoder accepts `passthrough_user_pob` and deep-copies those elements verbatim from the user's input. Curated stage progressions (gear/gems) can still override on a per-section basis.

## What's built (state as of 2026-05-14, Step 14 T5 — Pohx-style stage UI)

| Module | Package | Routes | Status |
|---|---|---|---|
| Domain models | `poe1-core` | — | done (Build, Intent, Plan, Item, League, enums) |
| HTTP/config/logging | `poe1-shared` | — | done (httpx + tenacity + diskcache, pydantic-settings, structlog) |
| PoB ingest + parser + mapper | `poe1-fob` | `POST /fob/analyze-pob` | done (raw / pobb.in / pastebin; full XML parse; Build mapping) |
| poe.ninja economy (currency, uniques, cluster, jewels, …) | `poe1-pricing` | `GET /pricing/quote`, `GET /pricing/snapshot` | done |
| poe.ninja ladder builds | `poe1-builds` | `GET /builds/list`, `GET /builds/detail` | done (protobuf columnar search + JSON hydration, 19 ascendancy fan-out, `main_skill` / `defense_type` filters) |
| IntentExtractor | `poe1-fob` | `POST /fob/extract-intent` | done (hybrid rule-based IT+EN + Anthropic Haiku tool-use fallback; 15 fixture cases; confidence threshold 0.70) |
| Ranking Engine | `poe1-fob` | `POST /fob/recommend` | done (SourceAggregator fan-out → hard-constraint filter → 6-dim weighted scorer → top-N; 49 unit tests) |
| **Planner v2** | `poe1-fob` | `POST /fob/plan`, `POST /fob/plan/stream` | done — 6-stage layout (Early/Mid/End Campaign + Early/End Mapping + High Investment), variant-aware unique pricing + Trade-API rare pricing, BuildTemplate registry (RfPohx detailed, GenericTemplate fallback), SSE streaming con progress + ETA |
| UI shell | `apps/shell` | — | done (React 18 + Vite 5 + Mantine v7 + TanStack Query; Build Finder + PoB Analyzer + Planner; `npm run dev` on :5173) |

Server: `uv run poe1-server` → <http://127.0.0.1:8765>. `/health`, `/version`, plus all the routes above.
Shell dev: `cd apps/shell && npm run dev` → <http://127.0.0.1:5173> (proxies API to :8765).

## What's next (Step 9 — Pricing v2)

In progress: pricing affidabile con confidence ≥60-75 % anche per uniques con varianti e rari custom-craftati.

- **9.1 — variant-aware uniques** ✅ done (2026-04-25). HelmetEnchant + Oil categorie nuove; `PriceSnapshot.by_name_and_variant`/`variants_of`; `PricingService.quote_unique_variant`/`quote_variants`; modulo `poe1_pricing.variants` con resolver protocol + registry + resolver per Forbidden Shako, Forbidden Flame, Forbidden Flesh, Impossible Escape (35 nuovi test).
- **9.2 — GGG Trade API source** ✅ done (2026-04-25). Nuovo `TradeSource` async in `poe1_pricing.sources.trade`: search → fetch → trimmed-median pricing in chaos. `RateLimitState` parser sui header `X-Rate-Limit-Ip`, sleep proattivo a 80% di headroom + `Retry-After` honoring sui 429. `TradeQuery` + `StatFilter` per query stat-aware. `HttpClient` esteso con `post_json` e `request_json` (no-cache) generici. 32 nuovi test con `httpx.MockTransport`.
- **9.3 — PoB mod extraction** ✅ done (2026-04-25). Due nuovi moduli in `poe1_fob.pob`: `uniques.unique_variant()` (item → registry → variant string) e `rares.{clean_mods, valuable_stat_filters}` (filtra metadata PoB tipo `Item Level:`, `Sockets:`, influence tags + estrae StatFilter dai mod chiave). `MOD_PATTERNS` con ~30 stat-id GGG per Life/ES/Mana, resistenze, suppression, level of socketed gems, attributi, crit, cast/attack speed. 35 nuovi test (variant resolution, metadata filtering, pattern matching, full pipeline su PoB reale).
- **9.4a — integrazione planner + SSE + UI loader** ✅ done (2026-04-25). `PricingPort` esteso con `quote_unique_variant`. `PlannerService` riscritto con `plan_with_progress()` async generator che emette `PricingProgress` (start/item_started/item_done/done) con ETA dinamico (heuristic upfront → average osservato dopo il primo item). Variant resolver via `Item.mods` text. `plan()` rimane wrapper sync. Endpoint `POST /fob/plan/stream` con SSE (`text/event-stream`, `data:` frames). Frontend `planBuildStream()` async generator + `<PricingProgressBar>` con Mantine `<Progress>`, ETA countdown live (~10 Hz). `HttpClient.post_json`/`request_json` generici. 12 nuovi test (lifecycle eventi, ETA, variant integration). Baseline 457 verdi, 89 mypy, 87 format.
- **9.4b — rare-via-Trade** ✅ done (2026-04-25). Mapper PoB esteso per promuovere rari high-value a `KeyItem` (≥2 stat filter riconosciuti tra `MOD_PATTERNS`). Nuovo `TradePort` Protocol nel planner (opzionale). `PlannerService` dispatch: UNIQUE→ninja con variant, RARE→Trade con `TradeQuery(type=base_type, stats=...)` percentile pricing. Helper `quote_trade_range()` stampa `PriceSource.TRADE_API`. ETA upfront contabilizza `n_trade × 6s`. Router wire `TradeSource(http, league)` accanto a `PricingService`. `valuable_stat_filters_from_mods()` accetta `Iterable[str]` direttamente. 4 nuovi test (Trade dispatch, skip senza port, skip < 2 mod, ETA mix). Baseline 461 / 89 / 87.

## Step 9 completo

Step 9 (Pricing v2) chiuso. Cosa abbiamo:
- Variant-aware unique pricing per Forbidden Shako/Flame/Flesh, Impossible Escape (4 resolver registrati)
- GGG Trade API rate-limit aware client per rari custom-craft
- PoB mod extraction con 30+ pattern → stat-id GGG
- Streaming planner (SSE `/fob/plan/stream`) con progress + ETA dinamico
- UI con barra di caricamento + countdown ETA in tempo reale

## Step 10 completo

Step 10 (Planner v2) chiuso. Cosa abbiamo:
- **6 fasi**: Early/Mid/End Campaign + Early/End Mapping + High Investment, ognuna con range di divines, rationale di default, content focus, trigger to advance. Bucketing items per divine midpoint con clamp che preserva l'invariante monotone-midpoint del `BuildPlan`.
- **`BuildTemplate` system** in `poe1_fob.planner.templates`: protocol + registry-based dispatch (`pick_template(build)`). `GenericTemplate` come fallback (deriva content da main_skill + support_gems), `RfPohxTemplate` come reference fully-detailed (Holy Flame Totem early → Unflinching switch → Kaom's Heart → Mageblood). 5 nuovi test sui template.
- `PlannerService.template_override` kwarg per i test.
- Aggiornati i test esistenti per il nuovo layout 6-stage (40 verdi nel modulo planner).

Templates futuri da aggiungere: Vortex, Spectre, Spark, Bone Spear, Cyclone (struttura già pronta, serve solo riempire i 6 metodi `for_stage` per ognuno).

## Step 11 completo

Step 11 (UI overhaul) chiuso. Cosa abbiamo:
- **Tema astrale viola** (`apps/shell/src/theme.ts`): palette `astral` + `gold` come custom Mantine colors, `primaryColor=astral`, primaryShade 5/6 dark/light. Headings su Cinzel/Marcellus serif, body su Inter.
- **`index.css`**: background astrale (3 radial gradients viola), animation primitives `astral-pulse` / `astral-fade-in` / `astral-twinkle` / `astral-rotate-slow`, classi `.fob-feature-card` con hover-grow + glow.
- **Welcome page** (`/`): logo orb pulsing, tagline "FOB · Frusta Oracle Builder", CTA "Inizia" con stagger animation. Star-field di 24 punti twinkling. Setta `localStorage.fob_seen_welcome` al click → visite future skippano direttamente a `/home`. State helper in `state/welcome.ts`.
- **Home page** (`/home`): hero + 3 feature card (Build Finder, Analizza PoB, Planner) con icona, descrizione, esempio in monospace, hover-glow. Card "Cosa puoi fare" con 4 esempi pratici. Card "Supporta" gold-bordered con CTA → modale donation.
- **DonationModal**: copy in italiano, 2 sezioni icon+testo (cosa cambia / quanto donare), CTA gold "Apri PayPal — paypal.me/riclong" con `target=_blank rel=noopener`.
- **Routing react-router-dom**: BrowserRouter wraps la app, Routes per `/` `/home` `/finder` `/analyze` `/planner` + 404→/home redirect. AppShell solo sulle route non-welcome. Navbar usa `useLocation` per attive states; lift-to-planner ora via `navigate('/planner')` invece che state-based. "Supporta" button anche nella navbar.

## Step 12 completo

Step 12 (Templates aggiuntivi + UI BuildCard upgrade) chiuso. Cosa abbiamo:
- **17 template totali** in `poe1_fob.planner.templates`. RfPohx + 16 nuovi:
  - Caster: Vortex Occultist, Spark Inquisitor, Bone Spear Necro, Hexblast Mines, Detonate Dead Necro, Bane Occultist
  - Attack: Cyclone Slayer/Berserker, Lightning Strike Raider, Tornado Shot Deadeye, Frost Blades Raider, Toxic Rain Pathfinder
  - Minion: Raise Spectre Necro, Skeleton Mages, Animate Weapon
  - Totem: Holy Flame Totem Hierophant (non-RF), Shrapnel/Lancing Ballista Deadeye
  - Ognuno ha advice mirato per Early Campaign / Mid Campaign / Early Mapping / End Mapping (gli stage non sovrascritti cadono su `GenericTemplate.for_stage`)
- `_matches_skill(*needles)` helper per matcher case-insensitive substring.
- `pyproject.toml`: per-file-ignore E501 per `templates.py` (testo italiano descrittivo).
- 4 nuovi test (registry coverage, Vortex/Cyclone/Spectre signature advice).
- **BuildCard upgrade**: EHP visibile accanto a Life/ES e DPS, pulsante "Copia link" che mette in clipboard l'URL pubblico poe.ninja del personaggio (con feedback "Copiato"), main gems lazy-fetched dal `/builds/detail` quando l'utente espande la card. Nuova API `getDetailFull(account, name)` espone anche `skills: SkillGroup[]`.

## Step 13.A1+A2 completo

Step 13.A — poe.ninja-style item Trade search integration (parte 1, MVP).

**Backend** (`/fob/trade-search`):
- Nuovo endpoint POST con `TradeSearchRequest` (item_name + item_type + tuple di `TradeSearchModFilter` con stat_id+min+max + online_only + min_links 1-6) → `TradeSearchResponse` (league + search_id + url + total_listings).
- Internamente costruisce un `TradeQuery` (riusando la stessa abstraction di Step 9.2), chiama `TradeSource.search()`, riformatta come `https://www.pathofexile.com/trade/search/<league>/<search_id>` da aprire in nuova tab.
- Validation 422 quando il payload non ha né nome né tipo né mod (no-empty-query rule).
- 6L / 5L socket constraint passato via `extra_filters.socket_filters` di GGG. 10 nuovi test sui validators Pydantic.

**Frontend**:
- Nuovo client `tradeSearch(req)` in `api/fob.ts` + tipi `TradeSearchModFilter` / `TradeSearchRequest` / `TradeSearchResponse` in `types.ts`.
- Nuovo componente `TradeSearchDialog` (Mantine `<Modal>`):
  - Header con item name/base in badge.
  - Lista mod toggleable (Switch) con strictness slider 50-100% (default 80%, marker visivo a 80 e 100).
  - Computed live: per ogni mod attivo mostra il `min` calcolato (`rolled_value × strictness/100`).
  - Optional 5L/6L socket constraint quando il caller passa `allowLinks=true`.
  - "Apri su Trade" → POST → `window.open(url, '_blank', 'noopener,noreferrer')`.
- `StageCard` integrato: ogni `ItemRow` ha un `<ActionIcon>` "Cerca su Trade" con `<IconSearch>` che apre il dialog. Per uniques passa `itemName=name`; allowLinks=true per body armour.

**Note sui limiti dell'MVP**: oggi `CoreItem` non porta `mods`/`base_type`, quindi per i rari del Plan il dialog ha la lista mod vuota (la ricerca sarà solo per slot/base se aggiunto). Step 13.A3 estenderà `CoreItem` con questi campi e popolerà il dialog con i mod estratti.

Baseline: 480 test verdi / 90 mypy / 88 format. Build frontend 508 KB / 159 KB gzip.

## Step 13.A3 completo

Step 13.A3 — popolamento dialog Trade-search dalla mod text del PoB.

**Modello core**:
- `CoreItem` esteso con `base_type: str | None = None` e `mods: tuple[str, ...] = ()`. Defaults vuoti per backward-compat con plan serializzati pre-A3.
- `_key_item_to_core_item()` nel planner service popola entrambi i nuovi campi dal `KeyItem.item.base_type` + `KeyItem.item.mods` (tuple di mod text).

**Backend** (`POST /fob/extract-trade-mods`):
- Nuovo endpoint stateless: prende `{mods: list[str]}` e ritorna `{mods: list[ExtractedTradeMod]}` con `(line, stat_id, value, label)` per ogni mod riconosciuto da `MOD_PATTERNS`.
- Internamente: `clean_mod_lines()` (nuovo helper pubblico in `pob/rares.py` che espone `_clean()` per stringhe) → `extract_mods()` → dedupe by `stat_id`.
- Zero HTTP esterni — serve solo per il pattern matching client-friendly.
- 5 nuovi test sui modelli Pydantic.

**Frontend**:
- Tipi `ExtractedTradeMod`, `TradeModExtractRequest`, `TradeModExtractResponse` in `types.ts`. `CoreItem` esteso con `base_type` e `mods` opzionali.
- Client `extractTradeMods(mods)` in `api/fob.ts`.
- `TradeSearchDialog` ora accetta sia `mods` (rows pre-extracted) sia `rawMods` (text); su `opened=true` con `rawMods` non vuoto fa `useEffect` fetch all'endpoint preview e popola la lista. Loader Mantine durante l'estrazione, fallback "non riconosciuti" se il match table non trova nulla.
- `StageCard` passa `tradeItem.base_type` come `itemType` e `tradeItem.mods` come `rawMods` — il dialog ora ha la lista mod popolata automaticamente per qualsiasi item del Plan, **non solo per gli unique**.

Baseline: 485 test verdi / 91 mypy / 89 format. Frontend build 508 KB / 159 KB gzip.

## Step 13.B completo

Step 13.B — Watcher's Eye combo pricing via Trade.

- **`MOD_PATTERNS` esteso con 26 pattern Watcher's Eye** in `pob/rares.py`: Hatred (cold conv / inc cold / adds cold), Anger (fire), Wrath (lightning), Discipline (ES recharge / onslaught / ES from body), Precision (crit chance / multi), Malevolence (DoT / avoid cold), Determination (armour / phys reduction), Grace (dodge / max ES), Vitality (life leech), Haste (cooldown / atk-cast speed), Pride (phys taken aura), Zealotry (spell crit / faster ailments). Stat ID GGG verificati contro `awakened-poe-trade/data/trade-stats.json`.
- **`_TRADE_PRICED_UNIQUES`** (`{"Watcher's Eye"}`) frozenset in `planner/service.py`. Quando un unique in questo set è in build E TradePort è disponibile, si entra nel path `_price_combo_unique`: `valuable_stat_filters_from_mods` + `TradeQuery(name=name, type="Prismatic Jewel", stats=...)` + percentile median. Risultato stampato `PriceSource.TRADE_API`.
- **Fallback graceful**: se Trade ritorna None (zero listing, currencies sconosciute), il planner cade su poe.ninja `quote_unique_range` per cheapest-variant.
- **4 nuovi test** (Trade dispatch, fallback su Trade None, skip senza TradePort, skip se nessun mod riconosciuto). Anche un Watcher's Eye con mod fittizia non rompe il piano.
- `pyproject.toml` per-file-ignore E501 esteso a `pob/rares.py` (regex Watcher's Eye lunghi).

Baseline: 489 test verdi / 91 mypy / 89 format.

## Step 13.D completo

Step 13.D (Templates per ogni classe) chiuso. **49 template totali nel registry**, 7 per ognuna delle 7 classi PoE1 (Marauder / Duelist / Ranger / Witch / Templar / Shadow / Scion). Iniziato da 17 template (T1) → +32 template in 12 turni.

Pattern matcher esteso oltre lo skill-keyed `_matches_skill(*needles)`:
- **Predicate-keyed** (count/heuristic su Build): `_matches_aurabot` (≥5 auras in support_gems).
- **Item-keyed** (lookup in `key_items`): `_matches_coc_cospri` (Cospri's Malice), `_matches_mjolner` (Mjolner). Stessa firma `Callable[[Build], bool]`, registrati prima dei matcher skill perché build item-keyed (CoC, Mjolner) carry main_skill come Cyclone/Static Strike che andrebbe a template skill-keyed sbagliato.

Lessons learned sui matcher (catturati dal gate durante i turni):
- Substring greedy: matcher "vortex" cattura "Blade Vortex"; "cyclone" cattura "Ngamahu Cyclone"; "reap" cattura "Summon Reaper". Mitigazione: matcher più specifici prima nel registry, oppure sostituzione con skill alternativa (Reap → Forbidden Rite).
- Stesso skill su più classi (Boneshatter Jugg/Berserker/Champion, Cyclone Slayer/Berserker): un singolo template che menziona tutte le ascendancy nelle advice è più robusto del routing per ascendancy (matcher non guarda `Build.ascendancy`).

Mappa coverage attuale (post-Turno 1):

| Classe | Count | Template registrati |
|---|---|---|
| Marauder | 7/7 ✅ | RF Jugg, Boneshatter, Earthshatter Jugg, Tectonic Slam Chieftain, Molten Strike Chieftain, Ground Slam Jugg, Volcanic Fissure Jugg |
| Duelist | 7/7 ✅ | Cyclone Slayer, Reave Slayer, Lacerate Gladiator, Splitting Steel Gladiator, Sunder Champion, Static Strike Gladiator, Spectral Throw Champion |
| Ranger | 7/7 ✅ | LS Raider, TS Deadeye, FB Raider, TR Pathfinder, Ballista Deadeye, Ice Shot Deadeye, Poisonous Concoction Pathfinder |
| Witch | 7/7 ✅ | Vortex Occ, Bone Spear Necro, DD Necro, Bane Occ, Spectre Necro, Skel Mages, Ball Lightning Elementalist |
| Templar | 7/7 ✅ | Spark Inq, HFT Hiero, Penance Brand Inq, Crackling Lance Inq, Arc Hierophant, Smite Guardian, Aurabot Guardian |
| Shadow | 7/7 ✅ | Hexblast Mines, Poison BV Assassin, Cobra Lash Assassin, Pyroclast Mines Saboteur, Cold DoT Trickster, Blade Blast Trickster, Soulrend Trickster |
| Scion | 7/7 ✅ | CoC Cospri Cyclone, Power Siphon, Storm Brand, Mjolner Discharge, Spectral Helix, Forbidden Rite, Wave of Conviction |

**Turno 1 (Marauder)** ✅ done (2026-05-01). 3 nuovi template + matchers + test signature:
- `BoneshatterTemplate` (matcher "boneshatter") — Jugg/Berserker, trauma stack mechanic, Sunder/Ground Slam levelling → switch a level 28, Heatshiver cold-conv variant.
- `EarthshatterJuggTemplate` (matcher "earthshatter") — slam phys + spike detonation, Tukohama's Coffer, +2 to Slam Skills crafting.
- `TectonicSlamChieftainTemplate` (matcher "tectonic slam") — fire slam consumando EC, Tukohama War's Herald + Ngamahu True Flame, Magnate belt + Kaom's Way ring.

Baseline 492 test verdi / 91 mypy / 89 format.

**Turno 2 (Marauder)** ✅ done (2026-05-01). Marauder coverage 4/7 → 7/7 (chiusa). 3 nuovi template:
- `MoltenStrikeChieftainTemplate` (matcher "molten strike") — phys-to-fire melee strike + projectile, Tukohama War's Herald lab1, Avatar of Fire keystone, Hrimsorrow + Ngamahu's Flame transition.
- `GroundSlamJuggTemplate` (matcher "ground slam") — slam phys signature day-1 Marauder, Resolute Technique, Marohi Erqi 2H → +2 to Slam Skills craft, Ground Slam of Earthshaking transfigured variant.
- `VolcanicFissureJuggTemplate` (matcher "volcanic fissure") — slam fire travelling fissure, Avatar of Fire opzionale, Combustion + Awakened Fire Pen endgame.

NOTA: in Turno 2 swappato il pianificato "Ngamahu Cyclone Chieftain" con `VolcanicFissureJuggTemplate` perché il matcher su `main_skill` non distingue Ngamahu Cyclone (item-keyed) dal generico Cyclone Slayer (skill-keyed) — sarebbe servito un refactor del matcher per guardare anche `key_items`.

Baseline 495 test verdi / 91 mypy / 89 format.

**Turno 3 (Duelist)** ✅ done (2026-05-01). Duelist coverage 1/7 → 4/7. 3 nuovi template:
- `ReaveSlayerTemplate` (matcher "reave") — sword phantom blade stacks AoE, Headsman lab1, Paradoxica/Foil endgame, Vaal Reave per single-target burst.
- `LacerateGladiatorTemplate` (matcher "lacerate") — sword 2H/DW slash + bleed, Painforged + Gratuitous Violence corpse explode, Crimson Dance keystone (DW variant), Lacerate of Haemorrhage transfigured opzionale.
- `SplittingSteelGladiatorTemplate` (matcher "splitting steel") — phys ranged-melee con secondary projectiles, Steel Skills cluster, Painforged (Glad) o Worthy Foe + Inspirational (Champion).

Baseline 498 test verdi / 91 mypy / 89 format.

**Turno 4 (Duelist)** ✅ done (2026-05-01). Duelist coverage 4/7 → 7/7 (chiusa). 3 nuovi template:
- `SunderChampionTemplate` (matcher "sunder") — slam phys signature day-1, Worthy Foe + Inspirational lab1, Marohi Erqi → +2 to Slam Skills 2H mace endgame, Sunder of Earthbreaking transfigured.
- `StaticStrikeGladiatorTemplate` (matcher "static strike") — lightning melee + chained beams, Versatile Combatant (Glad block) o Inspirational (Champion), Saviour shield + Paradoxica/Foil crit weapon.
- `SpectralThrowChampionTemplate` (matcher "spectral throw") — boomerang projectile day-1 Duelist, Worthy Foe + Inspirational, Awakened GMP + Slower Projectiles bossing, Vaal ST burst.

Baseline 501 test verdi / 91 mypy / 89 format.

**Turno 5 (Ranger)** ✅ done (2026-05-01). Ranger coverage 5/7 → 7/7 (chiusa). 2 nuovi template:
- `IceShotDeadeyeTemplate` (matcher "ice shot") — bow phys→cold conversion + cone secondary AoE, Endless Munitions lab1, Lioneye's Glare transition → +1/+2 socketed bow craft o +3 bow + Voltaxic Rift endgame.
- `PoisonousConcoctionPathfinderTemplate` (matcher "poisonous concoction") — flask-thrown chaos hit + poison massiccio, Master Surgeon (sustain) + Nature's Reprisal (poison multi), Mageblood endgame.

Baseline 503 test verdi / 91 mypy / 89 format.

**Turno 6 (Templar)** ✅ done (2026-05-01). Templar coverage 2/7 → 5/7. 3 nuovi template:
- `PenanceBrandInquisitorTemplate` (matcher "penance brand") — brand caster phys/lightning, Inevitable Judgment + Pious Path, Awakened Brand Recall + Awakened Lightning Pen endgame.
- `CracklingLanceInquisitorTemplate` (matcher "crackling lance") — lightning beam multistage, Inevitable Judgment + Augury of Penitence, Replica Conqueror's Efficiency + +1 power charge body.
- `ArcHierophantTemplate` (matcher "arc") — chain lightning day-1 Templar, Conviction of Power + Sanctuary of Thought, Mind Over Matter + Arcane Cloak, Awakened Chain endgame.

NOTA: matcher "arc" è una substring potenzialmente collisiva (matcherebbe "Arctic Breath", "Arctic Armour" se mai apparissero come main_skill). Tollerabile in pratica perché Arctic Armour è una buff aura (mai main_skill DPS) e Arctic Breath è skill morta. Se in futuro serve distinguere, mettere matcher più specifico prima di "arc".

Baseline 506 test verdi / 91 mypy / 89 format.

**Turno 7 (Templar)** ✅ done (2026-05-01). Templar coverage 5/7 → 7/7 (chiusa). 2 nuovi template + nuova sliding-rule matcher:
- `SmiteGuardianTemplate` (matcher "smite") — lightning melee + party aura buff radius, Radiant Crusade lab1, Aegis Aurora shield + Sublime Vision amulet, Time of Need ascendancy.
- `AurabotGuardianTemplate` (matcher CUSTOM `_matches_aurabot`) — support build aura stacking party, Radiant Crusade + Time of Need + Unwavering Crusade, Crown of the Tyrant + Sublime Vision + Awakened Generosity ovunque, Skin of the Lords + Aegis Aurora.
- Nuovo helper `_matches_aurabot(build)` che conta gli aura nei `support_gems` (≥5 → aurabot). Frozenset `_AURA_GEMS` con 19 nomi base. Registrato PRIMA dei matcher skill, perché un Aurabot con throwaway Smite/Spark va comunque a AurabotGuardian.

Pattern di matcher esteso: oltre allo skill-keyed `_matches_skill(*needles)`, ora supportiamo predicate-keyed (es. count auras). Utile per future match item-keyed (CoC Cospri, Mjolner) tramite `key_items` lookup.

Baseline 509 test verdi / 91 mypy / 89 format.

**Turno 8 (Shadow)** ✅ done (2026-05-01). Shadow coverage 1/7 → 4/7. 3 nuovi template:
- `PoisonBladeVortexAssassinTemplate` (matcher "blade vortex") — chaos blade orbit + poison stack, Mistwalker + Noxious Strike + Toxic Delivery, Cospri's Will body + Cold Iron Point dagger.
- `CobraLashAssassinTemplate` (matcher "cobra lash") — chaos projectile chain + poison, Toxic Delivery, Awakened Chain + Awakened Vile Toxins endgame, Vaal Cobra Lash boss.
- `PyroclastMinesSaboteurTemplate` (matcher "pyroclast") — fire AoE mines bossing, Pyromaniac + Bombardier + Demolitions Specialist, Bottled Faith consacrated ground.

NOTA matcher ordering: `_matches_skill("blade vortex")` deve venire **prima** di `_matches_skill("vortex")` perché "vortex" è substring di "blade vortex". Sezione registry "Casters" riordinata di conseguenza.

Baseline 512 test verdi / 91 mypy / 89 format.

**Turno 9 (Shadow Tricksters)** ✅ done (2026-05-01). Shadow coverage 4/7 → 7/7 (chiusa). 3 nuovi template + 2 matcher splits:
- `ColdDotTricksterTemplate` (matcher "cold snap") — pure cold DoT alternativo a Vortex Occultist, Patient Reaper + Soul Drinker, Cold Snap of Power transfigured opzionale.
- `BladeBlastTricksterTemplate` (matcher "blade blast") — detona Blade Fall blades, Escape Artist + Patient Reaper, dual-wield daggers spell skill.
- `SoulrendTricksterTemplate` (matcher "soulrend") — chaos+cold projectile DoT spell, Patient Reaper + Soul Drinker, Wither/Despair curse setup.

**Matcher refactor**:
- `_matches_skill("vortex", "cold snap")` → split in 2: `_matches_skill("cold snap")` per ColdDotTrickster + `_matches_skill("vortex")` per VortexOccultist (più puro).
- `_matches_skill("bone spear", "soulrend")` → split in 2: `_matches_skill("soulrend")` per SoulrendTrickster + `_matches_skill("bone spear")` per BoneSpearNecro.

Baseline 515 test verdi / 91 mypy / 89 format.

**Turno 10 (Scion)** ✅ done (2026-05-01). Scion coverage 0/7 → 3/7. 3 nuovi template + nuovo matcher item-keyed:
- `CocCospriCycloneScionTemplate` (matcher CUSTOM `_matches_coc_cospri`) — Cyclone CoC trigger Frostbolt+Ice Nova socketed in Cospri's Malice. Matcher cerca "Cospri's Malice" in `key_items`. Registrato PRIMA di `_matches_skill("cyclone")` perché i build CoC carry main_skill='Cyclone'.
- `PowerSiphonScionTemplate` (matcher "power siphon") — wand attack + Power Charges + crit, Deadeye + Assassin Ascendant, dual +2 lightning wand craft endgame.
- `StormBrandScionTemplate` (matcher "storm brand") — chain lightning brand caster, Inquisitor + Elementalist Ascendant, +1 power charge body. Registrato prima di "arc" per leggibilità (nessuna substring collision effettiva).

Pattern matcher esteso a item-keyed (`_matches_coc_cospri`): stessa firma `Callable[[Build], bool]` di `_matches_aurabot`, ma legge `build.key_items[*].item.name`. Riutilizzabile per Mjolner Discharge (T11).

Baseline 519 test verdi / 91 mypy / 89 format.

**Turno 11 (Scion)** ✅ done (2026-05-01). Scion coverage 3/7 → 6/7. 3 nuovi template + nuovo matcher item-keyed:
- `MjolnerDischargeScionTemplate` (matcher CUSTOM `_matches_mjolner`) — Mjolner unique mace triggera spell on melee hit, Cyclone + CWDT + Discharge + Ball Lightning, Inquisitor + Champion Ascendant. Stesso pattern di `_matches_coc_cospri`.
- `SpectralHelixScionTemplate` (matcher "spectral helix") — sword/axe boomerang con curva sinusoidale, Slayer + Deadeye Ascendant, Paradoxica + Saviour shield endgame.
- `ForbiddenRiteScionTemplate` (matcher "forbidden rite") — chaos+ele self-cast spell con life cost, Low Life Pain Attunement, Pathfinder + Trickster Ascendant, Shavronne's Wrappings o Solaris Lorica.

NOTA cambio piano: invece di "Reap" (matcher "reap" collisivo con "Summon Reaper" minion skill) ho usato Forbidden Rite — distinto e altrettanto iconico Scion.

Baseline 523 test verdi / 91 mypy / 89 format.

**Turno 12 finale (Scion +1 + Witch swap)** ✅ done (2026-05-01). Step 13.D **chiuso 7×7 = 49 template** ✅. 2 nuovi + 1 rimosso:
- `WaveOfConvictionScionTemplate` (matcher "wave of conviction") — fire+lightning wave AoE con exposure stacking, Inquisitor + Elementalist Ascendant. Chiude Scion 7/7.
- `BallLightningElementalistTemplate` (matcher "ball lightning") — slow lightning orb + Shaper of Storms shock + Mastermind of Discord. Sostituisce AnimateWeaponNecro nel set Witch (porta diversità con un Elementalist; prima 7 ma tutti Occultist/Necro).
- **Rimosso**: `AnimateWeaponNecroTemplate` (classe + matcher + `__all__` + dict canonical entry).

Coverage finale: tutte 7 classi a 7/7 ✅. Baseline 525 verdi / 91 mypy / 89 format.

## Step 13.C completo (Reverse-progression engine)

Step 13.C chiuso — **derivare** la upgrade ladder dal PoB endgame dell'utente, anziché applicare un template hardcoded basato su main_skill (Step 13.D). Affianca il template engine, non lo sostituisce: due `KeyItem` endgame diversi sullo stesso skill ora producono advice diversi.

**T1 — Skeleton engine** ✅ done (2026-05-01). Nuovo subpackage `packages/fob/src/poe1_fob/reverse/`:
- `models.py` — `LadderStep` (Pydantic frozen, `stage_key + item_name + kind + budget_div_max + rationale`) e `UpgradeLadder` (target_name + tuple di rungs ordinata cheap→endgame, helper `stage_keys()` / `for_stage(spec)`).
- `degrader.py` — `ItemDegrader` Protocol + `HardcodedDegrader` prima implementazione. Tabella per 6 uniques iconici (Mageblood, Headhunter, Kaom's Heart, Watcher's Eye, Forbidden Flame, Forbidden Flesh). Fallback "endgame only" single-rung quando l'item non è in tabella. Lookup case-insensitive via casefold.
- `__init__.py` — re-export `LadderStep`, `UpgradeLadder`, `ItemDegrader`, `HardcodedDegrader`.
- `tests/test_reverse.py` — 10 nuovi test: model frozenness, ladder ordering, ladder lookup, 6 ladder casi (Mageblood 3-rung, Headhunter 3-rung, Kaom's Heart 3-rung early-only, Watcher's Eye con substitution, Forbidden pair routing, fallback unknown), case-insensitivity.

**No integrazione con `PlannerService`** in T1: solo skeleton + dummy engine + test offline. L'integrazione (PlannerService accetta `mode='reverse'`, fonde gli output del degrader nei `gem_changes`/`tree_changes` per stage) è T2.

Baseline 535 test verdi (+10 reverse) / 95 mypy (+4 nuovi file) / 91 format.

**T2 — Integrazione `PlannerService.plan_reverse()`** ✅ done (2026-05-02). Aggiunge:
- `PlannerService.__init__(... degrader: ItemDegrader | None = None)` — opzionale, retrocompatibile.
- `PlannerService.plan_reverse(build, target_goal=...)` — wrapper su `plan()` baseline + post-processing: per ogni `KeyItem` chiama `degrader.degrade(ki)` → `UpgradeLadder`, indicizza i rung per `stage_key`, e per ogni `PlanStage` appende ai `gem_changes` esistenti una riga `[target_name] {rung.rationale}`. Pydantic models frozen → `model_copy(update=...)` per ricostruire il piano.
- Helper `_stage_key_from_label(label)` per convertire `StageSpec.label` → `key` (i `PlanStage` carry il label umano, i rung il key snake_case).
- Test: `plan_reverse` senza degrader → `ValueError` (fail-fast); con degrader appende le rationale nei stage corretti; senza key_items il piano è identico al template-only. 538 test verdi (+3 T2).

**T3 — AwakenedGemDegrader + CompositeDegrader** ✅ done (2026-05-02). Aggiunge:
- `AwakenedGemDegrader` — pattern-keyed su 36 nomi Awakened gems (frozenset `_AWAKENED_GEM_NAMES`). Ladder 3-rung: regular support gem (Mid Campaign, ~0.5 div) → Awakened level 1 entry (Early Mapping, ~2 div) → Awakened level 5 corrupted (High Investment, no cap). Strip del prefix "Awakened " per derivare il regular base name (es. "Awakened Empower" → "Empower Support"). Items non-Awakened → fallback single-rung.
- `CompositeDegrader` — chain di degrader. Prova ognuno in ordine, ritorna il primo multi-rung match. Single-rung "endgame only" conta come miss così il prossimo degrader tenta. Costruzione tipica: `[AwakenedGemDegrader(), HardcodedDegrader()]`. 544 test verdi (+6 T3).

**T4 — ForbiddenJewelLadder ascendancy-aware** ✅ done (2026-05-02). Aggiorna `_forbidden_pair_ladder` (HardcodedDegrader) per leggere il mod text e estrarre il notable allocato:
- Riusa `keystone_allocates_resolver` da `poe1_pricing.variants` (regex "Allocates X" già canonico per il variant registry).
- Quando il notable è estratto: il rung name + rationale lo menzionano esplicitamente (es. "Forbidden Flame matched pair (Avatar of Fire)" + "il prezzo esplode in base alla notable scelta").
- Fallback gracioso: senza "Allocates X" mod → label "(any notable)" + copy generico originale.
- 546 test verdi (+2 T4).

**T5 — Endpoint `POST /fob/plan/reverse`** ✅ done (2026-05-02). Aggiunge:
- Nuovo endpoint stesso shape di `POST /fob/plan` (input PoB, output `PlanResponse`), ma internamente wira un `CompositeDegrader([AwakenedGemDegrader(), HardcodedDegrader()])` e chiama `planner.plan_reverse(...)`.
- Logging `fob_plan_reverse_ok` con `key_items` count + stage count + cost range.
- Test integrazione in `apps/server/tests/test_fob_router.py`: smoke test che l'endpoint è registrato (rejects empty input → 422, rejects garbage → 400 stesso comportamento di `/fob/plan`).
- 547 test verdi (+1 T5).

**T6 — UI toggle reverse mode** ✅ done (2026-05-02). Aggiorna `apps/shell`:
- Client `planBuildReverse(input, targetGoal)` in `api/fob.ts` — POST a `/fob/plan/reverse`.
- `PlannerPage.tsx`: nuovo state `reverseMode: boolean` + `<Switch>` con tooltip esplicativo (multiline, 320px wide). Quando attivo, branch a `planBuildReverse` (non-streaming, niente progress bar — il request blocca). Quando OFF mantiene il flow SSE esistente. `useCallback` deps aggiornate.
- Note: streaming reverse (SSE su `/fob/plan/reverse/stream`) è out of scope T6, eventualmente T7 futuro.

Step 13.C **chiuso** con tutti i 6 turni. Baseline 547 test verdi / 95 mypy (95 file con i 4 nuovi reverse) / 93 format.

**Migliorie post-T6** ✅ done (2026-05-02):
- **A — Espansione `_LADDER_TABLE`**: aggiunti 11 uniques (Loreweave, Ashes of the Stars, Bottled Faith, Aegis Aurora, Sublime Vision, Crown of the Tyrant, Brass Dome, Shavronne's Wrappings, Cospri's Will, The Saviour, Crystallised Omniscience). Tabella ora copre 17 uniques. 1 nuovo test smoke che verifica multi-rung su tutti gli 11.
- **B — UI grouping ladder per stage**: in `StageCard.tsx` separati i `[target] rationale` (reverse mode) dal template gem advice. Sub-block "Upgrade ladder" con `IconStairsUp`, raggruppa per `target_name` con Mantine `Badge`. Render solo quando ci sono rung tag.
- **C — Test E2E reverse mode con PoB reale**: in `apps/server/tests/test_fob_router.py` nuovo test `test_plan_reverse_e2e_with_real_pob` che monkey-patcha `HttpClient.__aenter__` con `MockTransport`. Stub minimo per `/data/index-state` (lega Standard) + `{"lines": []}` su `/economy/stash/.../overview` + Trade API stub. Verifica shape 6-stage + main_skill + char class + presence di gem advice.
- **E — Frontend smoke build**: `npm install` + `npm run build` verde. Bundle 510 KB / 160 KB gzip.

**Migliorie pre-deploy D+F+H** ✅ done (2026-05-02):
- **D — Streaming SSE per reverse mode**: `PlannerService.plan_reverse_with_progress` async generator riusa `plan_with_progress` e applica il post-processing `_merge_ladder_advice` solo al `done` event. Nuovo endpoint `POST /fob/plan/reverse/stream` (`StreamingResponse` text/event-stream), client TS `planBuildReverseStream` + helper `streamPlanEndpoint(path, ...)` deduplica fetch+ReadableStream tra `/plan/stream` e `/plan/reverse/stream`. `PlannerPage.tsx` reverse mode ora usa SSE invece di non-streaming → progress bar + ETA anche per reverse. 2 nuovi test (lifecycle eventi + fail-fast senza degrader).
- **F — InfluenceItemDegrader**: nuovo degrader pattern-keyed su `Item.influence` non-vuoto + slot in (helmet/body/gloves/boots/amulet/ring). Ladder 3-rung: essence craft (Mid Campaign, ~0.3 div) → single influence + +1 socketed gems (Early Mapping, ~5-15 div) → double influence custom craft (High Investment, no cap). Influences label esposto in item_name + rationale (es. "body_armour Crusader + Warlord (single influence...)"). 4 nuovi test. Default `CompositeDegrader` esteso a `[AwakenedGem, Hardcoded, Influence]` in entrambi gli endpoint reverse.
- **H — Request coalescer in `HttpClient`**: nuovo `_inflight: dict[str, asyncio.Future[Any]]` in HttpClient. In `_cached_get`, dopo cache miss, se la stessa key ha un Future in volo, await quello invece di duplicare la call upstream. Critical per multi-utente: 5 utenti che cercano "Mageblood" in burst → 1 sola call a poe.ninja, gli altri 4 attendono lo stesso Future + scrivono cache 1 volta sola. Errori cleanup correttamente (no stuck futures). 2 nuovi test (5 concurrent → 1 upstream call, errore non blocca retry).

Step 13.C migliorie chiuse. Pronti per production deploy.

Baseline: 557 verdi / 95 mypy / 93 format. Frontend build 510 KB / 160 KB gzip.

## Production deploy — Fase 1: hardening ✅ done (2026-05-02)

Applicato in `claude/brave-johnson-5eb01e` per supportare deploy multi-utente:

- **`Settings.environment`** (`development` | `production`): nuovo enum. Quando `production`, `create_app` forza `log_format=json` automaticamente.
- **`Settings.cors_allowed_origins`** (`list[str]`): comma-separated nell'env (es. `CORS_ALLOWED_ORIGINS=https://fob.vercel.app,https://fob.tools`). Il `field_validator` con `Annotated[..., NoDecode]` bypassa il default JSON parser di pydantic-settings. Empty list in dev → CORS middleware non montato (Vite proxy gestisce). Production deve listare l'URL Vercel.
- **`Settings.http_max_concurrent_per_host`** (default 4): limit semaphore per upstream host. `HttpClient._host_sema(url)` lazy-creates one `asyncio.Semaphore(N)` per `httpx.URL(url).host`. In `_do_get` e `_request_json` le chiamate net wrappano `async with sema` solo durante la parte network (release prima del body parse). Multi-user safety: 10 utenti concorrenti che pianificano una build → max 4 calls simultanee a poe.ninja, le altre fanno coda.
- **`/health` arricchito**: ritorna `{status, environment, league, version, uptime_seconds, timestamp}` invece del minimale `{status: "ok"}`. Sufficiente per Fly.io health checks + UptimeRobot.
- **`run()` accetta env `HOST` e `PORT`**: defaults `127.0.0.1:8765` per dev, ma Fly.io setta `PORT=8080` e dobbiamo bind a `0.0.0.0`.
- **CORS middleware**: mounted solo se `cors_allowed_origins` non-empty. `allow_credentials=False` (no cookies), `allow_methods=["GET","POST"]`, `allow_headers=["Content-Type","Accept"]`, `max_age=3600`.
- **`.env.example` aggiornato + nuovo `.env.production.example`**: secrets template per Fly.io secrets set.

Test: +6 in `test_config.py` (environment default/prod, cors csv parse, cors empty, cors default empty, http concurrent default/override) + +2 in `test_fob_router.py` (health enriched, cors disabled when empty, cors enabled with origin).

Baseline: 565 verdi (+8 da 557) / 95 mypy / 93 format.

## Production deploy — Fase 2: containerization ✅ done (2026-05-02)

Aggiunto Dockerfile multi-stage + `.dockerignore` + `docs/DEPLOY.md`:

- **`Dockerfile`** in repo root, due stage:
  - **Builder**: `python:3.12-slim-bookworm` + uv 0.5.4 statico via `ghcr.io/astral-sh/uv`. `uv sync --locked --no-dev` installa il workspace completo. Cache mount su `/root/.cache/uv` per build veloci ripetuti.
  - **Runtime**: stessa base slim, copia `.venv` + `packages/` + `apps/server/` dal builder. User non-root (`app`, uid 1000). Default env: `HOST=0.0.0.0 PORT=8080 ENVIRONMENT=production LOG_FORMAT=json CACHE_DIR=/data/.cache_http`. EXPOSE 8080. HEALTHCHECK Docker-native via stdlib `urllib` (no curl/wget needed).
  - CMD: `["poe1-server"]` — la console script registrata da `apps/server/pyproject.toml` (chiama `run()` che legge HOST/PORT da env).
- **`.dockerignore`** strict: esclude `.venv/`, `.cache_http/`, `**/__pycache__/`, `apps/shell/`, `**/node_modules/`, `**/dist/`, `**/tests/`, `**/test_*.py`, `**/conftest.py`, `.git/`, `.github/`, `.vscode/`, build artifacts, `.env*` (whitelist `.env.example` + `.env.production.example`), `.claude/`. Build context piccolo, image piccola.
- **`docs/DEPLOY.md`**: playbook operazionale completo per Fly.io (backend) + Vercel (frontend). Include: install flyctl, `fly launch --no-deploy --copy-config --name fob-api --region fra`, `fly secrets set ENVIRONMENT=production LOG_FORMAT=json POE_LEAGUE=Mirage CORS_ALLOWED_ORIGINS=https://fob.vercel.app`, optional persistent volume mount per cache, `fly deploy`. Vercel: import repo + Vite framework preset + root `apps/shell` + env `VITE_API_BASE`. Custom domain wireup ($10/anno opzionale). Smoke test checklist + rollback procedure.
- **`README.md`**: aggiunto link a `DEPLOY.md` + comandi quick local Docker check.

NB: build Docker locale non testato (Docker Desktop non installato in shell). Sarà testato direttamente da Fly.io builder remoto in Fase 3.

## Production deploy — Fase 3: live ✅ done (2026-05-07)

FOB **live in production**:

- **Backend**: https://fob-api.fly.dev (Fly.io app `fob-api`, region `fra` Frankfurt, shared-cpu-1x 256MB free tier, auto-stop quando idle)
- **Frontend**: https://fob-ten.vercel.app (Vercel free hobby tier, build automatica al push su main, ~510 KB gzip)
- **CORS**: `access-control-allow-origin: https://fob-ten.vercel.app` allow-listed lato Fly
- **HTTPS**: Let's Encrypt automatico su entrambi
- **Costo**: $0/mese

Setup:
- `fly.toml` al root del repo: app=fob-api, region=fra, internal_port=8080, http_service health probe /health, auto_stop_machines='stop' per risparmiare free-tier hours.
- Dockerfile: uv 0.5.4 → 0.11.7 (la 0.5.4 ha un bug nel verificare `--locked` contro lockfile prodotto da uv recenti — il build remote falliva).
- Vercel: Framework=Vite, Root=`apps/shell`, Build=`npm run build` (dopo aver rimosso un override `nmp` typo'd), env `VITE_API_BASE=https://fob-api.fly.dev`.
- Default branch GitHub: cambiato da `claude/friendly-kowalevski-9d17f8` a `main` perché Vercel seguiva il default branch del remote.

Fly secrets set:
- `POE_LEAGUE=Mirage` (cambiabile con `fly secrets set POE_LEAGUE=...`)
- `CORS_ALLOWED_ORIGINS=https://fob-ten.vercel.app`

Smoke test risultati:
- `/health` 200 OK con env=production, league=Mirage, uptime tracking ok
- `/version` ritorna mappa sub-package versions
- CORS preflight ritorna `access-control-allow-origin` corretto

## Migrazione backend Fly.io → Render (2026-05-07)

Fly.io trial scaduto e richiede carta di credito anche per il free tier. Migrato il backend a **Render** che ha free tier permanente:

- **Backend nuovo**: https://fob-api-rtgg.onrender.com (Render free tier, region Frankfurt, 512MB RAM, spin-down dopo 15 min idle, ~30s cold start dopo wake)
- **`render.yaml`** al root del repo: blueprint Render che provisiona un web service `fob-api` dal `Dockerfile` esistente. `autoDeploy: true` → push su main = redeploy.
- **Dockerfile invariato**: stesso multi-stage uv 0.11.7 builder che usavamo su Fly. Render rebuilda dalla blueprint.
- **`fly.toml` rimosso** dal repo (non più rilevante).
- **`.env.production.example`** aggiornato (CACHE_DIR=/tmp/.cache_http, no più volume mount; tutto ephemeral).
- **`docs/DEPLOY.md`** riscritto end-to-end per il flusso Render (sign-up → New Blueprint → connect repo → set POE_LEAGUE + CORS_ALLOWED_ORIGINS dal dashboard).
- **Vercel `VITE_API_BASE`**: da aggiornare a `https://fob-api-rtgg.onrender.com` dopo che Render ha fatto il primo deploy + ridistribuire la prod build.

Secrets da settare su Render (dashboard service → Environment):
- `POE_LEAGUE=Mirage`
- `CORS_ALLOWED_ORIGINS=https://fob-ten.vercel.app`

Trade-off vs Fly: Render free tier va in spin-down dopo 15 min senza traffico → prima richiesta dopo idle = ~30s di cold start. Per uso multi-utente di FOB tollerabile (l'utente vede una progress bar o un loader mentre il container si scalda).

`docs/DEPLOY.md` aggiornato con URL reali. README.md ha link live in alto.

## Bug bash post-launch (2026-05-07)

Round 1-3 di fix dopo il deploy live:
- `apps/shell/src/api/builds.ts` BASE='' hardcoded (uguale al bug fob.ts) → `import.meta.env.VITE_API_BASE`. Main gems lazy fetch ora funziona.
- Aggregator.fetch_candidates: pool top-25 DPS + top-25 EHP (40 unique dedup) per intercettare sia bossing-tier sia DoT-degen builds. Concurrency 8→3 per non bucare il rate-limit poe.ninja /character endpoint.
- BuildCard: nuovo bottone "Apri PoB" (`IconExternalLink`, color blue) che apre poe.ninja profile in tab nuova. "Copia link" da subtle→light per visibilità.
- BuildCard.useEffect: rimossi `detailLoading` e `detailGroups` dalle deps — race condition causava loader infinito (setDetailLoading re-fired effect, cleanup cancellava la promise).
- BuildIntent.main_skill_hint nuovo campo + 45 skill canonical pattern matcher in rules.py + ninja source forwarda BuildFilter.main_skill come server-side `skills=` param. Query "righteous fire" → solo RF builds. Skill matching server-side reduces pool to ~20 ref → no hydrate needed → ~1s response.
- ninja.py decoder: quando filter `skills=` attivo, poe.ninja rinomina la colonna `dps` in `dps-<SkillName>`. Fallback search per qualsiasi `vl.id.startswith("dps-")`.
- IntentCard: nuovo Badge grape `skill: <hint>` quando intent.main_skill_hint set.
- ContentFocus.BOSSING synonyms estesi: aggiunti `bosser`, `ammazza boss`, `single target`.
- vercel.json esplicito framework="vite" per disambiguare auto-detect Python (Vercel CLI 51.6.1 vede pyproject.toml e tenta build come app Python). Aggiunto rewrites `/((?!assets/).*) → /index.html` per SPA routing direct-URL su /finder, /planner, /analyze.
- Trade router: 429 catturato e tradotto in messaggio user-friendly italiano "aspetta 30-60 secondi".
- Planner stages.py: `stages_for_target_goal()` modula stage layout — `mapping_only` skippa High Investment, `uber_capable` rephraseggia per mirror-tier crafts. PlannerService legge `target_goal` e usa solo le stage attive.

Baseline post-bugbash: 565 verdi / 95 mypy / 93 format.

## Step 14 — Pohx-style stage-by-stage build (in corso)

Big upgrade del planner: per ogni stage l'utente vede una build COMPLETA — items su ogni slot, skill tree allocato, gem links, note, e il risultato è un **PoB code importabile**. Vedi `docs/STEP14-pohx-style-planner.md` per design + 7-turni roadmap.

**T1 — Tree progression model + RfPohx + endpoint** ✅ done (2026-05-07).

Nuovo subpackage `packages/fob/src/poe1_fob/tree/`:
- `models.py` — `StageTree` (Pydantic frozen, `stage_key + node_ids + notables + ascendancy_nodes + pob_url`) auto-sort/dedup. `TreeProgression` (target_name + tuple stages, validator monotone strict + unique stage_keys).
- `pob_url.py` — `encode_pob_tree_url(node_ids, character_class, ascendancy)` produce URL `https://www.pathofexile.com/passive-skill-tree/<urlsafe-b64>`. Formato v6: header u32+u8+u8 + node-section u16be each + zero trailing. Deterministic, class+asc-aware.
- `progressions.py` — `RF_POHX_PROGRESSION` 6-stage hand-curated (placeholder node IDs da rifinire in T1.5 con cattura tree fixture). Registry `PROGRESSION_REGISTRY` + `progression_for(template_name)`.
- 11 nuovi test (StageTree dedup/frozen, TreeProgression monotone/unique/lookup, encode URL deterministic+class-aware+asc-aware+empty-edge).

Endpoint:
- `GET /fob/tree-progression/{template_name}` → `TreeProgression | null`. Falls back to null per template senza progressione.
- `GET /fob/tree-progression/{template_name}/{stage_key}/url?character_class=X&ascendancy=Y` → `{url: string | null}` con tree URL pronto per pathofexile.com.

Baseline: 576 verdi (+11 da 565) / 100 mypy file / 99 format file.

Note tecniche:
- Node IDs in `RF_POHX_PROGRESSION` sono placeholder integers che seguono la numerazione canonica PoE 1; **non verificati live**. T1.5 catturerà i veri node IDs da un PoB export reale per produrre URL importabili in PoE.
- Cluster jewel + mastery encoding (v7+) non supportati — il tree URL v6 carry solo regular passive nodes. Gli step T4 (PoB XML encoder) li gestiranno via PoB desktop format.

**Prossimi turni**: T2 gear suite per stage, T3 gem links structured, T4 PoB XML encoder, T5 UI tabs StageCard, T6+ estensione altri template.

**T1.5 — Capture node IDs reali da fixture** ✅ done (2026-05-07).

Il PoB fixture esistente (`packages/fob/tests/fixtures/pob_YNQeadFwNBmX.txt`, Marauder Chieftain con 143 nodes Spectre Necro) è stato usato per derivare la nuova `SPECTRE_NECRO_PROGRESSION`:
- 143 node IDs **reali** importati dal PoB import → split monotone in 6 sub-set (22, 40, 70, 95, 120, 143).
- Stage chunks scelti per match canonico Pohx-style chunking.
- `_stage_chunk(n)` helper per consistenza.
- I node IDs sono GARANTITI di caricare in PoE perché vengono da un import reale → URL pathofexile.com generated è valido copy-paste.
- Registry estesa: `spectre_necromancer` template ora ha progressione viva.

`RF_POHX_PROGRESSION` resta con node IDs placeholder (per ora) — sostituire con un PoB RF reale è un follow-up T1.6.

**T2 — Gear suite per stage + endpoint** ✅ done (2026-05-07).

Nuovo subpackage `packages/fob/src/poe1_fob/gear/`:
- `models.py` — `StageGearSlot` (Pydantic frozen, slot+item_name+kind+notes+budget_cap), `GearKind` Literal (`unique`/`rare_craft`/`leveling`/`skip`), `StageGearSet` (stage_key + tuple slots + overall_notes), `GearProgression` (target_name + tuple stages, validator unique stage_keys).
- `progressions.py` — `RF_POHX_GEAR_PROGRESSION` 6-stage hand-curated. Ogni stage ha 8-10 slots completi: helmet/body/gloves/boots/belt/amulet/ring/weapon_main/weapon_offhand + jewel a high investment. Notes italiane Pohx-style (es. "Springleaf shield essenziale post-RF switch", "+8% max fire res permette over-cap 89%").
- `_slot()` helper per readability nelle hand-curated stages.
- 9 nuovi test (slot lookup, kind validation, registry hit, RF endgame include Mageblood, RF early include Tabula).

Endpoint:
- `GET /fob/gear-progression/{template_name}` → `GearProgression | null`.

Baseline: 585 verdi (+9 da T1) / 104 mypy file / 102 format file.

**T3 — Gem links structured + RfPohx + endpoint** ✅ done (2026-05-07).

Nuovo subpackage `packages/fob/src/poe1_fob/gems/`:
- `models.py` — `GemSpec` (name + level 1-40 + quality 0-23 + alt_quality `divergent`/`phantasmal`/`anomalous`/None + is_support + notes), `GemLink` (slot + sockets 1-6 + color_pattern R/G/B/W + ordered gems + validator socket_count==len(gems) + color_pattern.length==sockets), `StageGemLinks` (stage_key + tuple links + notes per stage banner), `GemProgression` (validator unique stage_keys).
- `progressions.py` — `RF_POHX_GEM_PROGRESSION` 6-stage Pohx-style. Ogni stage ha 3-5 link group (body 4L→6L, helm 4L, gloves 4L CWDT, boots 4L aura, weapon 4L). Progressione: Holy Flame Totem 4L (early) → RF 6L (mid lab+1) → Awakened Burn 2 (end campaign) → 21/20 corrupted (early mapping) → Awakened 5 (end mapping) → Awakened 5 corrupted Divergent + Mirror-tier body+ Ashes (high investment, level effettivo 33+).
- `_g()` helper compatto.
- 12 nuovi test (model defaults, alt_quality + quality validation, sockets/color_pattern validators, link_for_slot lookup, RF endgame include Awakened Burning Damage + Empower, unknown returns None).

Endpoint:
- `GET /fob/gem-progression/{template_name}` → `GemProgression | null`.

Baseline: 597 verdi (+12 da T2) / 108 mypy file / 106 format file.

**T4 — PoB XML encoder + /fob/stage-export endpoint** ✅ done (2026-05-14).

Nuovo `packages/fob/src/poe1_fob/pob/encode.py`:
- `encode_pob_code(*, character_class, ascendancy, tree, gear?, gems?, level=90)` → codice PoB url-safe-base64 + zlib, importabile in PathOfBuilding desktop.
- `_build_xml()` costruisce `<PathOfBuilding version="2">` con `<Build>`, `<Tree><Spec nodes URL/>`, `<Skills>`, `<Items>` (placeholder per ogni slot non-skip), `<Notes>`.
- Class IDs map (Scion=0..Shadow=6) + Ascendancy IDs map (Juggernaut=1, Berserker=2, ...).
- `_quality_id` mappa `alt_quality` → PoB `qualityId` (Default/Alternate1/2/3 = Anomalous/Divergent/Phantasmal).
- `_slot_to_pob_label` mappa `ItemSlot` enum a PoB labels ("Helmet", "Body Armour", "Weapon 1", ecc).
- `encode_minimal_tree_pob()` wrapper tree-only (per affordance "Apri tree in PoB" senza items/gems).

Bug fix collaterale in `tree/pob_url.py`: l'header del tree URL era 6 byte (`>IBB`) invece di 8 — i node ID cadevano 2 byte prima rispetto a quello che il parser PoE/PoB legge (offset 8). Aggiunti 2 flag bytes a 0 dopo class+ascendancy.

Endpoint:
- `GET /fob/stage-export/{template_name}/{stage_key}?character_class=&ascendancy=&level=` → `{template_name, stage_key, code}`. Compone Tree + Gear + Gem progression dello stage in un singolo codice PoB. Tree obbligatorio (null se template senza progression); gear+gems opzionali.

12 nuovi test (`test_pob_encode.py`): basic shape (url-safe no padding), `encode_minimal_tree_pob` wrapper, roundtrip class+ascendancy+level via decode_export+parse_snapshot, roundtrip node IDs via tree URL, full encode con gear+gems, gem attributes preservati, kind='skip' onorato, no-ascendancy supportato, unknown class fallback, valid base64 invariant, roundtrip per tutte le 7 classi, garbage → PobParseError.

Baseline: 609 verdi (+12 da T3) / 110 mypy file / 108 format file.

**T5 — UI tabs StageCard + Importa in PoB** ✅ done (2026-05-14).

Backend:
- `PlanStage.stage_key` (snake_case, optional) → la UI sa quale slice di Tree/Gear/GemProgression chiedere. Default None per backward-compat.
- `PlanResponse.template_name` + `PricingProgress.template_name` + `PricingProgress.build` sull'evento `done` SSE → il client streaming ha tutto senza un secondo analyze-pob round-trip.
- `/fob/plan`, `/fob/plan/reverse`, `/fob/plan/stream`, `/fob/plan/reverse/stream` populano `template_name` via `pick_template(build).name`.

Frontend:
- 4 nuovi API client in `apps/shell/src/api/fob.ts`: `fetchTreeProgression`, `fetchGearProgression`, `fetchGemProgression`, `fetchStageExport`. Helper `get<T>(path)` per le GET.
- Tipi corrispondenti in `types.ts`: `StageTree`, `StageGearSet`, `StageGemLinks`, `TreeProgression`, `GearProgression`, `GemProgression`, `StageExportResponse`, `GearKind`, `AltQuality`, `GemSpec`, `GemLink`, `StageGearSlot`.
- StageCard riscritta con `<Tabs variant="pills">`: **Overview** (rationale + items + gem ladder come prima) / **Tree** (count nodi + notables + ascendancy + link tree URL) / **Gear** (tabella per-slot con kind badge + note) / **Gems** (card per ogni link group con sockets/colori + lista gemme con level/quality/alt-quality/note).
- Lazy fetch: ogni tab chiama il suo endpoint solo al primo click. Stati `undefined` (non chiesto) / `null` (template senza progression) / oggetto (dati pronti).
- **Bottone "Importa stage in PoB"**: scarica il codice da `/fob/stage-export`, lo copia nel clipboard, mostra preview Code block dei primi 240 caratteri + `<CopyButton>` per ri-copiare. Gestione errori in italiano.
- `PlannerPage` cattura `template_name` + `build` dall'evento SSE done e li passa a StageCard.

Baseline: 609 verdi / 110 mypy / 108 format. Frontend build 526 KB / 165 KB gzip.

**Prossimi: T6 espandi template (Vortex Occultist + Spark Inquisitor + Bone Spear Necro + Cyclone Slayer + Spectre Necro), T1.6 rimpiazza node ID placeholder RF con cattura PoB reale, eventuale T4.5 emissione items completa nel PoB (non solo placeholder).**

Pattern di degrader esteso oltre il table lookup:
- **Table-keyed** (`HardcodedDegrader`): mapping name → rung factory. Buono per uniques iconici noti.
- **Pattern-keyed** (`AwakenedGemDegrader`): regex/frozenset match su nome. Buono per famiglie con upgrade chain ovvio.
- **Mod-aware** (Forbidden pair): legge `Item.mods` per estrarre dettagli (notable allocato, variant, ecc.).
- **Composite** (`CompositeDegrader`): chain multi-strategy con first-match-wins.

## What comes after (post Step 15)

Production deploy is live, PoB import works end-to-end, Finder filters/sort/NL search shipped. The backlog from here is **the dynamic pivot**: stop hand-curating progression templates, start synthesizing them per-user.

### Backlog (in implementation order)

#### Step 16 — Dynamic Tree Progression *(2-3 days, high impact)*

Replace the curated `PROGRESSION_REGISTRY` (currently 2 of 49 templates) with an algorithm that derives the 6-stage tree from any user PoB. The registry stays as a fallback when no PoB is provided.

Algorithm:
1. Bundle PoE 1 passive tree data (nodes + edges + class starting nodes). PoB Community ships this as a JSON we can re-distribute.
2. For each node in `snapshot.tree.node_ids`, BFS-compute its distance from the class start node.
3. Sort by distance ascending; bucket into 6 stages with progressive weights (10% / 25% / 50% / 70% / 85% / 100% of allocated nodes).
4. Ascendancy nodes: bucket by lab order — Normal → Stage 2, Cruel → Stage 3, Merciless → Stage 4, Uber → Stage 5.
5. Mastery effects: only emit from Stage 4 onward (you typically respec masteries late).
6. Cluster jewel notables (id ≥ 65536): Stage 6 only.

Deliverable: `derive_tree_progression(snapshot: PobSnapshot) -> TreeProgression` in `poe1_fob.tree.dynamic`. The stage-export endpoint prefers this over the registry when a `user_pob_code` is provided. Hand-curated `RF_POHX_PROGRESSION` / `SPECTRE_NECRO_PROGRESSION` stay but become fallbacks for the no-PoB case.

Test target: feed the existing `pob_YNQeadFwNBmX.txt` fixture, get back 6 monotone supersets summing to the user's 134 nodes, all importable by PoB.

#### Step 17 — Dynamic Gear Progression *(3-4 days, high impact)*

Replace `gear_progression_for(template_name)` with `derive_gear_progression(snapshot: PobSnapshot, pricing: PricingService) -> GearProgression`.

Algorithm:
1. Classify each user item into a cost tier using the live pricing service:
   * **Mirror-tier** rare: 4+ T1 mods + complex craft signatures (very expensive)
   * **Mageblood-tier** unique: >100 div
   * **High** unique: 20-100 div (Crown of the Tyrant, +1 spell skill amulets)
   * **Mid** unique: 5-20 div (Kaom's Heart, Bottled Faith)
   * **Cheap** unique: <5 div (Goldrim, Springleaf)
   * **Leveling** unique: <1 div (Wanderlust, Brightbeak, Tabula)
   * **Cluster jewel**: always endgame
   * **Rare-craft**: budget-tier classification by socket count + mod count
2. Stage budget thresholds (divines): Stage 1 ≤0.5, Stage 2 ≤2, Stage 3 ≤10, Stage 4 ≤50, Stage 5 ≤200, Stage 6 = no cap.
3. For each user item above the stage's threshold, substitute with a cheaper equivalent from a small substitution table (e.g. Stage 4 Mageblood → "Stygian Vise rare T1 life + 2 res + flat life").

Deliverable: `derive_gear_progression` + a small substitution table per slot (~100 lines, covers all common slots — not per-build).

Test target: PoB with Mageblood → Stage 1 produces Tabula+Wanderlust+Goldrim; Stage 6 produces user's actual gear; intermediate stages produce items that exist on poe.ninja for that budget.

#### Step 18 — Dynamic Gem Progression *(1-2 days, low complexity)*

Replace `gem_progression_for(template_name)` with `derive_gem_progression(snapshot: PobSnapshot) -> GemProgression`.

Algorithm (per gem in user PoB):
* Stage 1 (≈ lvl 30): level `max(1, user_level - 12)`, quality 0.
* Stage 2 (≈ lvl 55): level `max(8, user_level - 8)`, quality 0.
* Stage 3 (≈ lvl 75): level `max(16, user_level - 4)`, quality `max(0, user_quality - 10)`.
* Stage 4 (≈ lvl 85): level 20, quality 20.
* Stage 5 (≈ lvl 95): level `min(21, user_level)`, quality 20.
* Stage 6: user's actual level/quality.

Awakened support gems: stages 1-3 substitute with the base name (strip "Awakened " prefix), Stage 4 Awakened lvl 1, Stage 5 Awakened lvl 3, Stage 6 user's actual.

Vaal versions: emit from Stage 3+ when the user has one.

Deliverable: `derive_gem_progression` + a gem-canonical-name normalization helper (Awakened ↔ base).

Test target: PoB with "Awakened Burning Damage 5 / 20" → Stage 1 emits "Burning Damage Support 8 / 0", Stage 6 emits user's actual.

#### Step 19 — Population data in Finder *(1 day, UX polish)*

Use the poe.ninja ladder data we already fetch to enrich the Finder:
* "Most popular main skills for Marauder Juggernaut this league" — top 3 with %
* "Build stat distribution for Slayer Cyclone" — life/dps/ehp percentile ranges
* Show as a small panel above the recommend results, refresh-cached per league per day.

Deliverable: `/builds/population-stats?ascendancy=X` endpoint + Finder UI panel.

### What we are explicitly NOT doing

* **Adding more hand-curated `*Progression` registries**. The current `RF_POHX_PROGRESSION` / `SPECTRE_NECRO_PROGRESSION` / `RF_POHX_GEAR_PROGRESSION` / `RF_POHX_GEM_PROGRESSION` stay as fallbacks for builds without a PoB, but **do not add new ones**. If a user pastes a PoB, Step 16/17/18 algorithms produce the progression dynamically.
* **Adding more `BuildTemplate` subclasses for new skills**. The 49 existing templates already cover every reasonable build for descriptive purposes. New skills should be matched into existing templates or fall through to `GenericTemplate`.
* **Hand-tuning per-league item prices**. Pricing comes from poe.ninja live data via `PricingService`.

## Project-specific gotchas (learned the hard way)

- **poe.ninja post-PoE2 endpoints:** `/poe1/api/economy/stash/{version}/...` for prices, `/poe1/api/builds/{version}/search` (protobuf) for ladder. `league=` param wants the **display name** ("Mirage"), not the URL slug. The old `/api/data/currencyoverview` scheme is dead.
- **pytest conftest collision:** Always `--import-mode=importlib`. The `packages/__init__.py` + `packages/<pkg>/__init__.py` empty files exist specifically to make conftests resolve as `packages.builds.tests.conftest` etc.
- **uv workspace `packages/*` glob** will pick up `packages/__pycache__` once Python compiles the namespace package. `pyproject.toml` excludes it explicitly — don't remove that exclude.
- **Aliased Pydantic fields in JSON responses**: FastAPI serializes by alias by default (`response_model_by_alias=True`). So `path_of_building_export` surfaces as `pathOfBuildingExport` in JSON; `class_name` surfaces as `class`; `defensive_stats` as `defensiveStats`. Tests that assert on the response dict must use the aliased keys.
- **diskcache has no `py.typed`** → mypy override `ignore_missing_imports = true`.
- **Protobuf generated file** at `packages/builds/src/poe1_builds/generated/ninja_builds_pb2.py` is ignored by ruff and mypy. Regenerate with `grpcio-tools` if the upstream schema changes; keep the raw `.proto` source under that dir too.

## How to pick up a new Step

1. Read the latest `docs/architecture.md` if it exists.
2. Run `uv run pytest -q` — if anything's red, fix that first.
3. Create a new `packages/<name>/` following the pricing/builds template: `src/poe1_<name>/{__init__.py, models.py, service.py, sources/*.py, router.py}`, `tests/{conftest.py, fixtures/, test_*.py}`, `pyproject.toml` declaring the package and its deps.
4. Capture real fixtures first, then write models to match them, then write the source adapter, then the service facade, then the router.
5. Close the step by running the full gate and updating this file's "What's built" table.
6. **Update the Patch Notes** — prepend a user-facing bilingual entry to the `RELEASES` array in `apps/shell/src/pages/PatchNotesPage.tsx`. This is NOT optional: the Patch Notes must ALWAYS be updated together with `CLAUDE.md` / `CLAUDE_PERPLEXITY_WORKFLOW.md`, in the same commit.
7. Commit and **push** the worktree branch: `git push origin claude/friendly-kowalevski-9d17f8`. This is mandatory after every step — don't ask, just do it.

## Environment

- `POE_LEAGUE=Mirage` (current league as of 2026-04-24).
- `ANTHROPIC_API_KEY` — only needed when Step 5A (IntentExtractor) lands.
- `POESESSID` — optional, only for authenticated GGG Trade calls.
- `.env.example` at the repo root shows the full list. Never commit `.env`.
