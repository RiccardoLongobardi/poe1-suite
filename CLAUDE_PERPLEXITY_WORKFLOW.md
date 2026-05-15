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
- **Baseline gate**: 704 tests green / 121 mypy / 117 format. Frontend build 567 KB / 176 KB gzip.
- **Working features**:
  - PoB analyze → Build summary.
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19).
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA.
  - "Importa stage in PoB": exports a stage-specific PoB code. As of 2026-05-15 the exported code passes through the user's real `<Items>`/`<Skills>` verbatim (only the passive tree differs per stage) — see "Recently fixed" below.
  - Trade redirect (client-side, no server-side GGG calls — GGG blocks Render's IP range).
- **Dynamic-synthesis pivot complete** (Steps 16/17/18/19, all done):
  - Step 16 (Dynamic Tree Progression) — ✅ done 2026-05-14.
  - Step 17 (Dynamic Gear Progression) — ✅ done 2026-05-15.
  - Step 18 (Dynamic Gem Progression) — ✅ done 2026-05-14.
  - Step 19 (Population data in Finder) — ✅ done 2026-05-15.
- **Recently fixed (2026-05-15)**:
  - Build Finder blank-page bug — defensive frontend fix landed (ErrorBoundary + Mantine v7 grouped-data shape for the class Select). See §9 archive.
  - Stage export emitted mod-less fake items + slot-labelled gem stubs — `encode_pob_code` now passes through the user's real `<Items>`/`<Skills>`. **This also resolves the QA "explodeSource" PoB Lua crash**: that crash fired in PoB's DPS-calc phase, and the only synthesised XML feeding the calc was the `<Skills>` block — now replaced by the user's real (PoB-valid) skills. Pending a user re-QA in PoB Community to confirm.

If anything you read in this file or in `CLAUDE.md` contradicts the above, **the above wins** and the older text needs correcting.

---

## 1bis. Where to verify the *current* state (read before any planning)

The §1 snapshot is hand-maintained — it might lag a few hours after a feature lands. Before drafting prompts, doing research, or assuming anything about the codebase, **always re-check the live sources** below. Everything here is public HTTP, no auth needed.

### Repo (GitHub, branch `main`)

- **Browse the repo**: <https://github.com/RiccardoLongobardi/poe1-suite>
- **Latest commit on main** (one-liner with subject, hash, date):
  ```sh
  curl -s https://api.github.com/repos/RiccardoLongobardi/poe1-suite/commits/main | jq -r '"\(.sha[0:7]) \(.commit.author.date) \(.commit.message | split("\n")[0])"'
  ```
- **Recent commit log** (last 20 commits, subject lines):
  ```sh
  curl -s 'https://api.github.com/repos/RiccardoLongobardi/poe1-suite/commits?per_page=20&sha=main' | jq -r '.[] | "\(.sha[0:7])  \(.commit.message | split("\n")[0])"'
  ```
- **Raw file at HEAD** (any path; example for the project contract):
  ```
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE.md
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE_PERPLEXITY_WORKFLOW.md
  https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/packages/fob/src/poe1_fob/router.py
  ```
- **File tree at HEAD** (full recursive listing):
  ```sh
  curl -s 'https://api.github.com/repos/RiccardoLongobardi/poe1-suite/git/trees/main?recursive=1' | jq -r '.tree[].path' | head -50
  ```

### Live backend (Render)

- **Health probe** — confirms backend is up + which league it's serving:
  ```sh
  curl -s https://fob-api-rtgg.onrender.com/health | jq .
  ```
  Returns `{"status":"ok","environment":"production","league":"Mirage","version":"…","uptime_seconds":…,"timestamp":"…"}`. **Note: first request after ~15 min idle takes ~30 s** (Render free-tier cold start).
- **Version map** — sub-package versions, useful to confirm what got deployed:
  ```sh
  curl -s https://fob-api-rtgg.onrender.com/version | jq .
  ```
- **OpenAPI schema** — full enumerated endpoint surface:
  ```
  https://fob-api-rtgg.onrender.com/openapi.json
  ```

### Live frontend (Vercel)

- <https://fob-ten.vercel.app> — the deployed SPA. `/finder`, `/analyze`, `/planner` are the three main flows.

### Reading order for a new session

When Perplexity (or any human) sits down to plan new work, scan these in order — they're cheap and fast:

1. **`CLAUDE.md`** ([raw](https://raw.githubusercontent.com/RiccardoLongobardi/poe1-suite/main/CLAUDE.md)) — the project contract. Sections most likely to be relevant:
   - "Product direction" (the dynamic-synthesis pivot)
   - "External data sources" (what to use, what to skip)
   - "The gate" baseline (current test/mypy/format counts — gives you "is the project healthy")
   - "What's built" table near the top
   - the most recent `## Step N — …` block (latest closed step + its lessons)
2. **This file's §1, §6, §7** — current snapshot, backlog status, decision log.
3. **Latest 10 commits on `main`** (curl recipe above) — confirms what physically landed since the snapshot in §1 was written. Any commit message starting `feat(…)` or `fix(…)` is a delta worth understanding.
4. **`/health` on the live backend** — verifies deployment matches the repo's `main` (the `version` field is stamped at build time).

### Don't assume; verify

If §1 says "Step 18 done 2026-05-14" but the latest commit is two days newer, **the latest commit wins**. The hand-maintained sections drift — the live sources don't. Same rule as §1's tie-breaker: more-recent reality > stale narrative.

---

## 2. Stack & data sources (no PostgreSQL, no ETL)

We are deliberately **not** building a relational data warehouse for this project. Earlier drafts of this file proposed Postgres + ETL pipelines; that direction was rejected. The actual data layer:

| Layer | Source | Caching | Refresh |
|---|---|---|---|
| Live economy (currency / unique / cluster / oils / jewels) | `poe.ninja` `/poe1/api/economy/stash/{version}/...` (JSON) | `diskcache` 15 min TTL on `HttpClient` | Per-request, automatic. |
| Build ladder + per-character snapshots | `poe.ninja` `/poe1/api/builds/{version}/search` (protobuf) | `diskcache` 15 min TTL | Per-request, automatic. |
| Per-item Trade search (Mageblood etc.) | GGG `/api/trade/search/<league>` (JSON) | In-memory TTLCache 8 min by query hash | Per-request, automatic. *(Note: blocked from Render's IP range; runtime fallback to bare-URL redirect.)* |
| PoE 1 passive tree definition | GGG `passiveSkillTreeData` JS variable on `pathofexile.com/passive-skill-tree` | Vendored as `packages/fob/data/tree/3_28.json` (2.8 MB) | Manual via `scripts/extract_tree_data.py` once per league. |
| Item base types (for Step 17) | `repoe-fork/repoe` `base_items.json` (planned vendor) | TBD vendor under `packages/fob/data/items/` | Manual once per league. |

Sources we evaluated and rejected (don't propose them again):

- **poedb.tw** — HTML scrape only, no API/dumps, fragile, terms ambiguous.
- **GGG official developer API** (OAuth) — only user-data (characters, stashes, trade); does not publish tree/gem/base definitions.
- **brather1ng/RePoE** — dead since league 3.19 (Sep 2022); use the `repoe-fork/repoe` fork instead.

Reference: `CLAUDE.md` → "External data sources (use these, don't reinvent)".

---

## 3. Roles

### 3.1 Perplexity — research & design

What Perplexity is uniquely good at and should own:

- **Data-source surveys** — when we hit a wall, Perplexity researches what data exists (e.g. the analysis that produced the §2 table above).
- **Algorithm design** — drafting BFS / clustering / ranking strategies for new features before code is written.
- **Comparative reviews** — "is library X or Y better for use case Z" with sources.
- **Long-form research reports** that summarise multiple sources with citations.
- **QA sessions** — manual QA of the live app, classification of bugs, and production of fix prompts for Claude Code.

What Perplexity **does not** do in this workflow:

- Edit code files in the repo (`.py`, `.ts`, `.lua`, `.sql`, `.json`).
- Modify Claude Code's session state or todos.
- Update this file's *implementation status* (the §6 backlog) — only Claude Code updates that, since Claude Code is the one actually doing the work.

Perplexity **may** propose updates to §5 (open questions) and §7 (decision log) when its research surfaces a decision point the project needs to settle. Perplexity **also** writes fix prompts to §8 when QA surfaces bugs.

### 3.2 Claude Code — implementation

What Claude Code owns:

- All code changes under `packages/`, `apps/`, `scripts/`, `docs/`.
- All test changes and gate enforcement.
- Commits, pushes, deploy-triggering merges to `main`.
- Updating **both** `CLAUDE.md` (project contract, baselines, lessons) and `CLAUDE_PERPLEXITY_WORKFLOW.md` (workflow status — §6 backlog, sometimes §7 decision log).
- Reading external data via WebFetch / curl when needed for a specific task (Claude Code already does this routinely; Perplexity is reserved for *deep* research, not every one-off fetch).

Constraints on Claude Code:

- Cannot bypass the pre-commit gate without explicit user instruction (no `--no-verify`).
- Cannot commit secrets, `.env` files, or other items in the `.gitignore` exclusion list.
- Must run the full gate (`uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest`) before declaring a step done.

### 3.3 The user (Riccardo)

What the user owns:

- Strategic direction (the dynamic-synthesis pivot was a user decision, recorded in §7).
- Manual QA in PoB Community desktop (we cannot automate the round-trip from a script).
- Final-call on architectural trade-offs surfaced by either Perplexity or Claude Code.
- Curating which Perplexity research findings get adopted vs ignored.

---

## 4. Collaboration rules

1. **`CLAUDE.md` is the contract**, this file is the playbook. When they conflict, `CLAUDE.md` wins and this file needs correcting.
2. **No silent re-architecture**. Decisions that change the stack, the data sources, or the public API surface go in §7. Don't add Postgres / ETL / new languages without an explicit decision-log entry first.
3. **Prompts in this file are reusable templates**, not one-shot tasks. Each one should be runnable today without context from a past chat. Time-bound tasks live in §6.
4. **Don't fetch GGG Trade from production.** Render's IP range is blacklisted by GGG's anti-bot — calling `/api/trade/search` from the deployed backend returns 403 every time. Server-side trade calls are reserved for local development; production flows go via the client-side redirect helper (`apps/shell/src/api/tradeRedirect.ts`).
5. **Vendor data, don't fetch at runtime.** When we depend on a public dataset (PoE tree, item bases), commit a snapshot to the repo and refresh manually per league via a `scripts/` utility. No runtime HTTP to GitHub raw or similar — adds an availability dependency we don't need.

---

## 5. Open questions for Perplexity

Use this section to park "go research X" items. Claude Code can flag candidates here when a question surfaces mid-implementation that Perplexity is better placed to answer.

- **Analyze page — redesign or remove?** QA 2026-05-15 flagged the `/analyze` page as low-value in its current form. Decision pending: (a) remove the route entirely, (b) repurpose it as a PoB-paste entry point that feeds directly into the Planner (bypassing the Finder), or (c) keep as-is. Riccardo to decide before the next planning session.

---

## 6. Backlog & status

Authoritative status of the dynamic-synthesis pivot. Updated by Claude Code after each step closes.

### IN PROGRESS

- *(nothing in progress between sessions — the explodeSource PoB-import crash is addressed by the stage-export passthrough fix, see DONE. Awaiting user re-QA.)*

### NEXT

- *(to be decided — see §5 for the Analyze page open question)*

### CANDIDATE FUTURE WORK

These are *opportunities*, not commitments. Discuss with the user before promoting to NEXT.

- [ ] **Finder result-list polish** — sort indicator showing which sort key produced the order; "this ascendancy is 47% of the meta this league" line from population stats; per-skill drill-down panel.
- [ ] **Pricing-aware gear classifier** — currently `derive_gear_progression` uses a name-signature heuristic for unique tiers when no `prices` map is provided. Wire `PricingService.snapshot()` into the router so the live prices feed the classifier (one extra async fetch per stage-export request, cacheable).
- [ ] **Cold-start UX banner** — Render's free tier spins down after 15 min idle; first request takes ~30 s. Frontend should detect long pending `/health` probes and surface "warming up the server" so users don't think it's broken.
- [ ] **Bundle code-splitting** — Vite build warns at 566 KB. Splitting Planner / Finder routes into lazy chunks would knock the initial JS to <300 KB.
- [ ] **Analyze page redesign or removal** — see §5 open question.

### DONE

- [x] **Step 1-13** — Core domain models, PoE Ninja + Trade pricing, ranking engine, planner v2 reverse-mode, UI shell. (See `CLAUDE.md` for per-step detail.)
- [x] **Step 14 T1-T5** — Tree + gear + gem progression scaffolding, PoB XML encoder + decoder, StageCard tabs UI, "Importa stage in PoB" button.
- [x] **PoB import QA** (2026-05-14) — Verified the export-then-paste flow against Path of Building Community 3.28 desktop. Took 7 commits to debug the tree URL header, mastery effects, cluster jewel passthrough — see `CLAUDE.md` "Lessons from the PoB-import-debug sprint".
- [x] **Step 15 — Finder search improvements** (2026-05-14) — Class + ascendancy filter, stat-floor filters (Life/ES/EHP/DPS), level range, sort_by, natural-language extraction extended with k/m suffix + "almeno X" / "ordina per Y" phrases.
- [x] **Step 18 — Dynamic Gem Progression** (2026-05-14) — `derive_gem_progression(snapshot)` projects six GemSpec snapshots per gem; handles Awakened normalisation, Vaal normalisation, trigger-gem pinning, aura-like soft downscale. Replaces hand-curated `gem_progression_for(template_name)` for any build with a pasted PoB.
- [x] **Step 16 — Dynamic Tree Progression** (2026-05-14) — Vendored GGG passive tree JSON (`packages/fob/data/tree/3_28.json`); `derive_tree_progression(snapshot)` BFSes the user's allocated subgraph from class start, buckets into 6 cumulative supersets at coverage 10/25/50/70/85/100; ascendancy distributed by lab order; cluster jewels stage 6 only.
- [x] **Step 17 — Dynamic Gear Progression** (2026-05-15) — Vendored repoe-fork base-item catalogue (`packages/fob/data/items/base_items.json`, 357 KB minified, 1034 released gear bases). `derive_gear_progression(snapshot, prices=None)` tier-classifies user items (mirror / mageblood / high / mid / cheap / leveling / cluster / rare_craft), per-stage tier ceiling, substitutes over-budget items with canonical leveling uniques in stage 1-2 / generic rare-craft placeholders in stage 3+. Pricing is optional — name-signature heuristic covers the 40+ famous expensive uniques.
- [x] **Bugfix — Stage export: fake items + mis-labelled gems + `explodeSource` PoB crash** (2026-05-15) — "Importa stage in PoB" produced mod-less placeholder items (uniques with no explicit block, "Crafted Helmet" rares with no stats) and gem groups labelled by gear slot ("Body Armour") instead of the gem; PoB Community also crashed on import with `Data/Skills/other.lua:5364: attempt to index field 'explodeSource' (a nil value)` in the DPS-calc phase. **Root cause**: `encode_pob_code` let the synthesised `gear`/`gems` params win over the user's pasted PoB; since `derive_gear/gem_progression` always return data for a snapshot, the encoder always synthesised placeholder items + gem stubs and never passed through the real `<Items>`/`<Skills>` (also dropping cluster jewels). The synthesised `<Skills>` block was the only synthesised XML feeding PoB's offence calc → the `explodeSource` nil crash. **Fix**: passthrough now wins — real items/gems/clusters copied verbatim, only the passive tree differs per stage; synth path only runs in the no-PoB case; synth-path `<Skill label>` set to `""` so PoB auto-labels from the gem. 704 tests / 121 mypy / 117 format. See `CLAUDE.md` for detail. Pending user re-QA in PoB Community to confirm the crash is gone.
- [x] **Bugfix — Finder blank page after intent extract** (2026-05-15, took two passes) — **Root cause**: `<Select data={CLASS_OPTIONS}>` was using Mantine v6's flat `{value,label,group}` shape; Mantine v7 needs the grouped `{group, items: [...]}` shape and crashes inside its internal `useMemo` before our render runs. Pass 1 added null-safe defaults + ErrorBoundary around IntentCard / PopulationStatsPanel / results, but the Select was outside those boundaries → still blank. Pass 2 rewrote `CLASS_OPTIONS` to the v7 grouped shape AND wrapped the entire post-intent block in a top-level ErrorBoundary so any future render error degrades to an inline alert instead of blanking the whole page. Frontend build 567 KB / 176 KB gzip. See §9 for the original QA prompt + Mantine v7 invariant in `CLAUDE.md`.
- [x] **Step 19 — Population stats in Finder** (2026-05-15) — `compute_population_stats(refs)` aggregator (no HTTP, no state): top-N skill popularity + p25/p50/p75/p90 distributions for Life / ES / EHP / DPS / Level. Endpoint `GET /builds/population-stats?ascendancy=&top_n_per_class=&top_n_skills=&league=` reuses `BuildsService.fetch_refs` (15 min diskcache hit). Frontend `PopulationStatsPanel` rendered in `FinderPage` above the filter row when an ascendancy is selected (manually or extracted by intent); reacts to the dropdown override via TanStack-Query cache key.
- [x] **Production deploy live** — Render (backend) + Vercel (frontend) on free tier. See `docs/DEPLOY.md`.

### REJECTED / OBSOLETE

These were in earlier versions of this file or earlier backlogs; they are explicitly not on the roadmap and shouldn't reappear:

- ~~Build a PostgreSQL data layer for prices.~~ → Replaced by live `poe.ninja` + `diskcache`. Decision 2026-05-14 (see §7).
- ~~Scrape PoEDB for static game data.~~ → Replaced by vendored JSON from GGG / `repoe-fork`. Decision 2026-05-14.
- ~~Pre-fill GGG Trade searches server-side.~~ → GGG blacklists Render IPs (HTTP 403 every request). Replaced by client-side redirect to `pathofexile.com/trade/search/<league>` with item name in clipboard. Decision 2026-05-14.
- ~~Hand-curate `*_PROGRESSION` registries for the remaining 47 BuildTemplate classes.~~ → Replaced by the dynamic-synthesis pivot (Steps 16-19). Decision 2026-05-14, see `CLAUDE.md` "Product direction".
- ~~Add new `BuildTemplate` subclasses for new skills.~~ → The existing 49 templates already cover every reasonable build for *descriptive* purposes; new skills should match into existing templates or fall through to `GenericTemplate`. Stage data is dynamic, not template-keyed.

---

## 7. Decision log

Reverse-chronological. Every decision that changes architecture, stack, or scope gets a line. Add (don't rewrite) past entries.

- **2026-05-14** — *Server-side Trade search is impossible on Render.* GGG returns HTTP 403 from datacenter IP ranges (verified via direct curl). Removed `/fob/trade-search` + `/fob/extract-trade-mods` endpoints; frontend redirects directly to `pathofexile.com/trade/search/<league>` with item name in clipboard. The `/fob/trade-url` endpoint stays in the code (works in local dev) but the frontend doesn't call it from production. Re-attempt requires moving the backend to a non-blocked host.
- **2026-05-14** — *Dynamic synthesis over curated templates.* Steps 16-19 replace `*_PROGRESSION` registries (only `rf_pohx` + `spectre_necromancer` were ever curated). Tree progression derives from BFS on the user's PoB; gem progression projects level/quality with Awakened-substitution; gear progression will classify by price tier; the 49 `BuildTemplate` classes stay for descriptive Italian rationale text + UI labels only.
- **2026-05-14** — *Vendor data, don't fetch at runtime.* The PoE 1 passive tree JSON is committed at `packages/fob/data/tree/3_28.json` and refreshed manually per league via `scripts/extract_tree_data.py`. Same pattern will apply to `repoe-fork/base_items.json` for Step 17.
- **2026-05-14** — *External data source survey.* PoB Community (GitHub) is the primary source for tree + gem level tables + item bases (MIT licensed, league-current). `repoe-fork/repoe` is the JSON alternative when we'd rather parse JSON than Lua (one league behind). `poe.ninja` is the only source for live economy + build population data. PoEDB and GGG's developer API are explicitly out (HTML-only / user-data-only respectively). Full breakdown in `CLAUDE.md` "External data sources".
- **2026-05-14** — *No PostgreSQL, no ETL.* Earlier drafts of this file proposed a relational data warehouse. Rejected: the live HTTP-with-cache model (`diskcache` 15 min TTL on `poe.ninja`, in-memory 8 min TTL on GGG Trade) covers all current use cases without operational overhead.
- **2026-05-07** — *Backend migrated from Fly.io to Render.* Fly's trial ended; Render's free tier is permanent. `render.yaml` blueprint + Dockerfile. Trade-off: Render spins down after 15 min idle (~30 s cold start on first request after wake).
- **2026-04-25** — *Pricing v2 closed* (Step 9). Variant-aware unique pricing + GGG Trade API source for rare custom-craft + PoB mod extraction + streaming planner with SSE progress & ETA.

---

## 8. Prompt library

Reusable templates. Each prompt should be self-contained — runnable today without context from a past chat. When a prompt becomes obsolete (e.g. the feature ships), move it to §9 archive instead of deleting it, so future Perplexity sessions see why it's no longer here.

### Prompt — Step 17 scaffolding

```prompt
You are working inside the `poe1-suite` mono-repo. Read CLAUDE.md (project contract) and CLAUDE_PERPLEXITY_WORKFLOW.md (workflow + decisions) first. The dynamic-synthesis pivot is in progress: Steps 16 + 18 closed, Step 17 (Dynamic Gear Progression) is next.

Goal: implement `derive_gear_progression(snapshot, pricing)` in `packages/fob/src/poe1_fob/gear/dynamic.py`. Same shape as `poe1_fob.gems.dynamic.derive_gem_progression` and `poe1_fob.tree.dynamic.derive_tree_progression`.

Algorithm (per the §6 backlog entry):

1. For each item in `snapshot.items_by_slot`, classify into a cost tier:
   - "mirror" — rare, 4+ T1 mods + specific influence combos (compute via existing `valuable_stat_filters_from_mods` count).
   - "mageblood" — unique with poe.ninja chaos-equivalent > 100 div.
   - "high" — unique 20-100 div.
   - "mid" — unique 5-20 div.
   - "cheap" — unique < 5 div.
   - "leveling" — unique < 1 div.
   - "cluster" — Large/Medium/Small Cluster Jewel (always endgame).
   - "rare_craft" — non-unique non-cluster rare.

2. Stage budget thresholds (divines): Stage 1 ≤ 0.5, Stage 2 ≤ 2, Stage 3 ≤ 10, Stage 4 ≤ 50, Stage 5 ≤ 200, Stage 6 = no cap.

3. For each slot, at each stage:
   - If the user's item's tier fits the stage budget: keep it.
   - Otherwise substitute with a cheaper-tier placeholder using the vendored `repoe-fork/base_items.json` to pick a canonical base type for the slot, then describe the substitution as a `StageGearSlot(kind="rare_craft", item_name="rare X (life + 2 res)", notes=...)`.

4. The pricing service is the existing `PricingService` (`packages/pricing/src/poe1_pricing/`); use the same patterns as `poe1_fob.planner.service._key_item_to_core_item`.

Vendor `repoe-fork/base_items.json` first at `packages/fob/data/items/base_items.json` (write a small `scripts/extract_base_items.py` that fetches it from the upstream release URL). Bump the pre-commit `check-added-large-files` maxkb if needed.

Write unit tests in `packages/fob/tests/test_gear_dynamic.py` covering: tier classification per item; stage budget filtering; substitution selection per slot; end-to-end on the existing fixture `packages/fob/tests/fixtures/pob_YNQeadFwNBmX.txt`.

Wire `_compose_stage_export` in `packages/fob/src/poe1_fob/router.py` to prefer `derive_gear_progression` over `gear_progression_for(template_name)` when a snapshot is available, mirroring the dynamic-tree priority order.

Run the full gate, commit, push. Baseline should land at ~680 tests, 116 mypy.
```

### Prompt — Step 19 scaffolding

```prompt
You are working inside the `poe1-suite` mono-repo. Read CLAUDE.md and CLAUDE_PERPLEXITY_WORKFLOW.md first. Step 19 (Population data in Finder) is the last open item in the dynamic-synthesis pivot.

Goal: surface aggregated `poe.ninja` ladder statistics in the Build Finder UI.

Backend:

1. New endpoint `GET /builds/population-stats?ascendancy=<name>` in `packages/builds/src/poe1_builds/router.py`. Output shape:
   ```json
   {
     "ascendancy": "Slayer",
     "total_builds": 4231,
     "top_skills": [
       {"skill": "Cyclone",      "count": 1183, "pct": 27.9},
       {"skill": "Boneshatter",  "count": 920,  "pct": 21.7},
       {"skill": "Tornado Shot", "count": 612,  "pct": 14.5}
     ],
     "stat_distributions": {
       "life":  {"p25": 4200, "p50": 5800, "p75": 7300, "p90": 8900},
       "ehp":   {"p25": 5500, "p50": 8300, "p75": 11200, "p90": 14800},
       "dps":   {"p25": 800000, "p50": 2_400_000, "p75": 7_000_000, "p90": 18_000_000}
     }
   }
   ```

2. Aggregator: fetch the ladder via the existing `BuildsService` (which already speaks `poe.ninja` protobuf), group by ascendancy, compute top-N skills and stat percentiles. Cache the aggregated result per league per ascendancy for 24 h (use `diskcache` via `HttpClient`).

Frontend:

3. New `PopulationStatsPanel` component shown above the result list in `apps/shell/src/pages/FinderPage.tsx` when an ascendancy is selected (manually or extracted by intent).
4. Render top-3 skills as Mantine `<Badge>`s with the percentage; render stat distribution as a small Mantine `<RangeSlider>` showing p25-p90 with markers.

Tests: backend aggregator unit tests (synthetic ladder fixture); router smoke test (200 + valid shape).

Run the full gate, commit, push.
```

---

## 9. Prompt archive

Closed prompts kept for context. Don't run these — they reflect earlier project shape.

- **Old Prompt 001 (Core DB schema)** — proposed a PostgreSQL schema (`dim_league`, `dim_currency`, `dim_base_item`, `fact_economy_snapshot`). **Rejected 2026-05-14**: no Postgres in this project (see §7). Replaced by live `poe.ninja` HTTP with `diskcache`.
- **Old Prompt 002 (PoE Ninja ETL)** — proposed `scripts/poe_ninja_etl.py` writing into Postgres. **Rejected 2026-05-14**: same reason; we read on-demand and cache.
- **Old Prompt 003 (Base items ETL)** — proposed `scripts/base_items_etl.py` writing to Postgres. **Rejected 2026-05-14**. The replacement is a much simpler `scripts/extract_base_items.py` (Step 17) that just vendors `repoe-fork/base_items.json` into the repo.
- **Old Prompt 004 (Finder blank page bugfix, QA 2026-05-15)** — Build Finder went blank after "Analizza query": `TypeError: Cannot read properties of undefined (reading 'map')` in `IntentCard`, no `ErrorBoundary` so the whole page subtree unmounted. **Shipped 2026-05-15**: new `apps/shell/src/components/ErrorBoundary.tsx` wrapping IntentCard / PopulationStatsPanel / results in `FinderPage`; null-safe `??` defaults on every API-derived array access in IntentCard, PopulationStatsPanel, FinderPage. Pure frontend defensive fix, zero backend / API contract / test changes. Frontend build 567 KB / 176 KB gzip.
- **Old Prompt 005 (PoB import `explodeSource` Lua crash, QA 2026-05-15)** — pasting a stage PoB code into PoB Community v2.65.0 crashed in the DPS-calc phase with `Data/Skills/other.lua:5364: attempt to index field 'explodeSource' (a nil value)`. **Shipped 2026-05-15** (commit `c3f5e9a`): the crash's root cause was the same as the "fake items" bug — `encode_pob_code` always synthesised a `<Skills>`/`<Items>` block instead of passing through the user's pasted PoB, and the synthesised `<Skills>` block was the only synthesised XML feeding PoB's offence calc. The stage-export passthrough fix (real `<Items>`/`<Skills>` copied verbatim) removes the synthesised skills entirely, so PoB now calcs the user's own (PoB-valid) skill set. No separate fix was needed.
