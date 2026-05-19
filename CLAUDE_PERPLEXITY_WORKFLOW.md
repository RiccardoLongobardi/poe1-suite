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
- **Baseline gate**: 724 tests green / 128 mypy / ruff clean. Frontend build main 440 KB / 140 KB gzip + lazy route + `pageStore` chunks.
- **Working features (all QA-verified or post-QA fixed)**:
  - Build Finder with class/asc/stat-floor/sort filters + natural-language extraction (Step 15) + per-ascendancy population stats panel (Step 19). ✅
  - Planner with 6-stage `BuildPlan`, SSE streaming progress + ETA. ✅
  - "Importa stage in PoB": exports a stage-specific PoB code. ✅
  - PoB Analyze → full build dashboard: character header + key stats, equipment grid with per-item tooltips, flasks, tree jewels, skill-link panel. ✅
  - Cold-start Divine Orb warmup overlay. ✅
  - Trade dialog: `TradeSearchDialog` with full GGG stat DB (~9.5k stats), name/base search, per-mod toggles + strictness slider, 5L/6L filter, Instant Buyout default, integer min-roll filters, domain-aware implicit/explicit stat resolution. ✅
- **Design system**: "Void Stone & Ember" — void-black warm backgrounds, ember-gold accent, parchment text, Cinzel/Cabinet Grotesk/Geist Mono type. Light mode: "Parchment" (warm cream + ink). Both QA-verified. ✅
- **Step 33 (Visual polish batch 1) DONE 2026-05-18** — `ParticleCanvas` ember field; `.vs-rarity` hover glow on all gear items (per-rarity PoE colour); `useCountUp` on Analyze KPIs; `.vs-skeleton*` ember loaders. ✅
- **Step 34 (Visual polish batch 2) DONE 2026-05-19** — lightweight route fade (CSS), unique-item poe.ninja price badges, keyboard shortcuts overlay (`?`), toast redesign. ✅
- **Step 35 (Visual polish batch 3) DONE 2026-05-19** — 2/3 shipped: Analyze item hover+pin popover (`GearCard`) + header logo ember pulse. Finder virtual list dropped. ✅
- **Step 36 (View Transitions API) DONE 2026-05-19** — only Layer 3a (Finder skill-filter micro-transition) shipped. Layer 1 reverted same day. **Do not retry route-level View Transitions.** ✅
- **Step 37 (Theorycrafter — design phase) DONE 2026-05-19** — analysis-only. `docs/THEORYCRAFTER_DESIGN.md` written. ✅
- **Step 38 (Theorycrafter — Build Generator) → reset by Step 38r 2026-05-19** ✅ — Step 38 shipped a ladder-anchored engine (NL query → poe.ninja ladder rank → reformatted real build); that is Finder retrieval, not from-scratch generation. **Step 38r (Prompt 025) reset it: Option C — deleted the `poe1_fob.theory` subpackage + `POST /fob/theory/generate`; `/theorycrafter` is now a clean "coming soon" stub.** The correct from-scratch generator is a future step. The Finder-vs-Theorycrafter boundary is now documented permanently in `CLAUDE.md` product direction.

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

- <https://fob-ten.vercel.app> — `/finder`, `/analyze`, `/planner`, `/theorycrafter` ("coming soon" stub after the Step 38r reset).

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

*(none as of 2026-05-19 — Step 38r shipped)*

### CANDIDATE FUTURE WORK

- **Theorycrafter — PoB-driven Build Generator (true v1)** — rule-based + PoB as synthesis engine. Generates builds from scratch using vendored 3.28 data (tree, gems, item bases). No ladder retrieval. Step after the reset.
- **Theorycrafter — Item & Modifier Browser (full version)** — affix pools + numeric ranges; needs the slimmed RePoE mods vendor file. Deferred.
- **Theorycrafter — Item Filter Generator** — postponed by Riccardo.
- **Theorycrafter — Atlas Strategy Generator** + curated scarab table — postponed by Riccardo.
- **Build Generator — LLM rationale layer** — future optional enhancement (per-call cost). Only for text explanation, never for data generation.
- **Chatbot in-app** — conversational PoE assistant. Approach TBD.

### DONE

- [x] **Step 38r — Theorycrafter architectural reset** (2026-05-19, Prompt 025) — Option C: deleted the ladder-anchored `poe1_fob.theory` subpackage + `POST /fob/theory/generate` + tests + frontend wiring. `/theorycrafter` kept as a clean "coming soon" stub. Finder-vs-Theorycrafter boundary documented permanently in `CLAUDE.md`. 714 tests / 124 mypy.
- [x] **Step 38 — Theorycrafter: Build Generator** (2026-05-19) ⚠️ ARCHITECTURAL DRIFT — shipped but wrong (ladder-anchored retrieval). Reset by Step 38r above.
- [x] **Step 37 — Theorycrafter design & architecture analysis** (2026-05-19, Prompt 024) — analysis-only. `docs/THEORYCRAFTER_DESIGN.md`. ✅
- [x] **Step 36 — View Transitions API** (2026-05-19, Prompt 023) — Layer 3a only. Layer 1 reverted. ✅
- [x] **Step 35 — Visual polish batch 3** (2026-05-19, Prompt 022) — GearCard hover+pin, ember pulse. ✅
- [x] **Bugfix — Trade dialog: decimal stat-filter min** (2026-05-19). ✅
- [x] **Bugfix — Trade dialog: implicit mods + route transition stutter** (2026-05-19). ✅
- [x] **Step 34 — Visual polish batch 2** (2026-05-19, Prompt 021). ✅
- [x] **Bugfix — Trade dialog: unique name search + Instant Buyout + count mods** (2026-05-18). ✅
- [x] **Step 33 — Visual polish batch 1** (2026-05-18, Prompt 020). ✅
- [x] **Step 32 — Trade dialog: full GGG stat DB + all mods** (2026-05-18). ✅
- [x] **Step 31 — poe.ninja-style Trade-search dialog** (2026-05-18). ✅
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

- **2026-05-19** — *Step 38r reset executed (Prompt 025) — Option C chosen.* Claude evaluated the three options and chose **C (delete + stub)**: the `poe1_fob.theory` ladder-anchored engine was deleted, `/theorycrafter` left as a clean "coming soon" stub. Reasoning: Option B (rebuild the correct engine now) needs a substantial rule-based synthesis pipeline + a gem-data vendor file that doesn't exist yet — the workflow itself scopes the correct generator as a separate future step; B would have shipped a half-built engine. Option A keeps semi-wrong code for marginal value. C leaves the repo honest. The Finder-vs-Theorycrafter boundary is now a permanent rule in `CLAUDE.md` product direction.
- **2026-05-19** — *Step 38 architectural drift identified. Theorycrafter ≠ Finder.* Product intent clarified by Riccardo: **Theorycrafter must generate builds from scratch** using official 3.28 data (vendored tree, gems, item bases). It must NOT search or reformat builds from the poe.ninja ladder — that is exactly what Finder already does. Step 38's engine ("NL query → ladder rank → reformatted real build") is wrong by definition. The correct engine is **rule-based deterministic planner + Path of Building as the synthesis/validation motor**. LLM is explicitly excluded from build data generation; it may only be used optionally for NL intent parsing and textual rationale (with per-call cost). Step 38 must be diagnosed and corrected via Prompt 025 before any new Theorycrafter work. The three options Claude must evaluate: (A) Rename Step 38 as a Finder extension and rebuild Theorycrafter from scratch; (B) Heavy refactor keeping only UI shell; (C) Delete and rebuild. Claude must choose one — no "it depends".
- **2026-05-19** — *Theorycrafter rollout narrowed (Riccardo's answers to the §5 open questions).* Build Generator rule-based; Item Filter Generator postponed; Atlas Strategy postponed; Item & Modifier Browser deferred (full version when built); LLM rationale layer future enhancement; route `/theorycrafter` confirmed.
- **2026-05-19** — *Theorycrafter scoped as next major feature.* Four backlog items consolidated into Theorycrafter.
- **2026-05-19** — *Chatbot in-app added as candidate backlog.*
- **2026-05-19** — *View Transitions API: route-level use rejected for good (Step 36 revert).* Route changes permanently use the keyed `.vs-route` CSS fade. Do not retry route-level View Transitions.
- **2026-05-19** — *Step 35 virtualization dropped.* Finder list ≤50 items with variable-height cards.
- **2026-05-18** — *Visual polish roadmap: three batches (Steps 33, 34, 35).*
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

*(no open prompts as of 2026-05-19 — Prompt 025 shipped, see §9)*

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
- **Old Prompt 025 (Step 38r — Theorycrafter architectural reset)** — Shipped 2026-05-19. ✅ Option C: deleted the ladder-anchored `poe1_fob.theory` engine; `/theorycrafter` left as a "coming soon" stub. Finder-vs-Theorycrafter boundary documented permanently in `CLAUDE.md`.
