# CLAUDE.md — poe1-suite

Instructions for any Claude Code session working in this repo.
Read this file top-to-bottom before doing any work.

## Who the user is

- **Riccardo** — Italian PoE 1 player, builds tools for himself (ric.longobardi@outlook.it).
- Prefers conversation in **Italian**, technical identifiers/commands in **English**.
- Values: "niente fittizio" — no fake/mocked data. Every module ships with real fixtures and is end-to-end playable before the next one starts.

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

All four must pass with zero errors. Current baseline: **466 tests green (2 skipped — integration/LLM), 90 files type-checked clean, 88 files formatted clean**.

## What's built (state as of 2026-04-25, end of Step 8 — FOB completo)

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

## What comes after (Step 11+)

- **Step 11 — UI overhaul** — tema astrale viola, welcome page animata, home page dashboard, modale donation PayPal (paypal.me/riclong). Refactor a `react-router-dom`.
- **Step 11 — UI overhaul** — tema astrale viola, welcome page animata, home page dashboard, modale donation PayPal (paypal.me/riclong). Refactor a `react-router-dom`.
- **Faustus flipper** — package `poe1-faustus` per flip di valuta basato su poe.ninja bulk trades. Strumento separato. UX: arbitraggi "X chaos → Y div → Z chaos → profit %".
- **App unica raggruppante** — navbar per tool (FOB, Faustus, …) quando arriva il secondo tool.

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
6. Commit and **push** the worktree branch: `git push origin claude/friendly-kowalevski-9d17f8`. This is mandatory after every step — don't ask, just do it.

## Environment

- `POE_LEAGUE=Mirage` (current league as of 2026-04-24).
- `ANTHROPIC_API_KEY` — only needed when Step 5A (IntentExtractor) lands.
- `POESESSID` — optional, only for authenticated GGG Trade calls.
- `.env.example` at the repo root shows the full list. Never commit `.env`.
