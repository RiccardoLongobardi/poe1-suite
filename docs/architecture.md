# Architecture — poe1-suite

This document captures the design decisions that underpin the mono-repo and the FOB (Frusta Oracle Builder) tool in particular. It is the single source of truth when decisions feel ambiguous during implementation.

## Scope and principles

The suite is a personal collection of tools for Path of Exile 1 — currency-making, build advising, hideout management — eventually composed into a single desktop/web/mobile application. The guiding principles are:

1. **No fake data.** Every module ships with test fixtures taken from real PoBs, real poe.ninja snapshots, real player queries. No hardcoded "demo" builds.
2. **Modular and pluggable.** Each tool is an isolated package; each external data source hides behind an interface; each feature can be replaced without rewriting the rest.
3. **End-to-end over deep polish.** V1 of each tool is shallow but complete: the user can use it in a live league from day one.

## Repo shape

- `packages/core/` — PoE 1 domain models shared across all tools (`Build`, `Item`, `League`, `PriceRange`, enums…).
- `packages/shared/` — Infrastructure shared by all tools: async HTTP client with retry and local cache, config loader (env-based), structured logging.
- `packages/<tool>/` — One Python package per tool. `packages/fob/` first, `packages/faustus/` and `packages/hideout/` later.
- `apps/server/` — FastAPI process that imports each tool's router and exposes a single HTTP surface.
- `apps/shell/` — React + Vite + Mantine SPA that consumes the API. Dark-theme, app-like layout (ispired by poeez.com, with Mantine as component library). Wraps into desktop via Tauri and mobile via Capacitor when needed.

The choice of mono-repo plus uv workspace keeps every package importable from the others without publishing, while still letting each package declare its own dependencies.

## FOB pipeline

FOB is the first real tool. Its runtime is a seven-stage pipeline:

1. **Intent Engine** (`packages/fob/intent/`). Turns a natural-language query (IT or EN) into a strongly-typed `BuildIntent`. Hybrid approach: rule-based parser with synonym dictionaries covers the high-confidence cases; an LLM fallback handles ambiguous phrasing and is forced to return valid enum values via JSON-schema enforcement.

2. **Build Source Layer** (`packages/fob/sources/`). Implementations of the `BuildSource` interface. Each source produces `Build` objects that are indistinguishable downstream. Planned sources: `PobSource` (parses a user-supplied PoB code — Step 2), `PoeNinjaBuildsSource` (ladder snapshot — Step 4), additional guide aggregators in later steps. A `SourceAggregator` fans out calls with per-source timeouts so a single failure does not break the response.

3. **Ranking Engine** (`packages/fob/ranking/`). Deterministic, explainable scoring. `hard_constraints` are applied as filters *before* scoring; remaining candidates receive a weighted sum over features (damage-profile match 30%, playstyle 25%, budget 20%, content focus 15%, defense 5%, complexity 5%). The engine emits a `ScoreBreakdown` so the output layer can say exactly why a build ranked where it did.

4. **Pricing Engine** (`packages/fob/pricing/`). Currency and unique-item prices come from poe.ninja's public JSON API, with a local disk cache (1-hour TTL). Rare crafted items are not on poe.ninja; for them we emit a `PriceRange` with a banded heuristic derived from mod tiers and item-level. Every `PriceRange` carries its `PriceSource` (observed vs heuristic) so callers can decide how much weight to give it.

5. **Planner** (`packages/fob/planner/`). Given a `Build` and a `target_goal`, produces a `BuildPlan`: three `PlanStage`s (league-start, mid, end-game) each with `core_items`, estimated costs, expected content, tree/gem changes, and explicit upgrade triggers. Works both when the starting point is a DB-sourced build ("build from scratch") and when the user pastes their own PoB ("upgrade planner").

6. **Output Composer**. Renders the pipeline output in a shape suited for humans: top-N recommended builds with reasons, the selected plan, a concrete shopping list per stage. Lives in the API layer.

7. **Shell UI**. React + Mantine frontend, mapped 1:1 to the API.

## Development roadmap

Each step produces something real and usable. No mocks, no hardcoded sample builds.

1. **Foundation** (this step). Mono-repo, `packages/core/`, `packages/shared/`, CI, pre-commit.
2. **PoB Source.** Decode and parse a PoB export code, classify the build (damage profile, playstyle, defense), emit a fully-populated `Build`. First user-visible endpoint: `POST /fob/analyze-pob`.
3. **Pricing Engine.** Wire poe.ninja; enrich the Build's `estimated_cost_div`.
4. **poe.ninja Builds Source.** Ingestion of the league ladder.
5. **Intent Engine.** Rule-based + LLM fallback.
6. **Ranking Engine** + `SourceAggregator`. End-to-end discovery endpoint: `POST /fob/recommend`.
7. **Planner.** `POST /fob/plan` — takes a Build (from source or PoB) and returns a `BuildPlan`.
8. **Output composer and Shell UI.**

## Non-goals and constraints

- No automation of inputs against the game client (ToS).
- No scraping of poeez.com (no public API, private endpoints protected).
- No storage of GGG `POESESSID` outside the local `.env`.
- League-awareness throughout: every price, every build, every plan is tied to a specific `League` object.
