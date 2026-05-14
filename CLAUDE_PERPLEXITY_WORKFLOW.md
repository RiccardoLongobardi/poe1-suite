# CLAUDE_PERPLEXITY_WORKFLOW

Coordinated workflow between **Perplexity (research)** and **Claude Code (Opus 4.7)** for the `poe1-suite` mono-repo.

This file is the single source of truth for:
- What Perplexity is responsible for (research, design, prompts).
- What Claude Code is responsible for (implementation inside this repo).
- The current backlog and decisions.

## 1. Project context

`poe1-suite` is a mono-repo of Path of Exile 1 tools, with Python packages under `packages/`, a FastAPI backend under `apps/server/`, and a React shell under `apps/shell/`.[cite:62]

The current focus is building:
- **FOB** — Frusta Oracle Builder (build advisor) under `packages/fob/`.
- A shared **PoE 1 data layer** (data warehouse-ish) to power multiple tools (FOB, Faustus, future apps).

We use:
- **Perplexity** to design schemas, choose external data sources (PoEDB, PoE Ninja, trade API, etc.), and write high-quality prompts.
- **Claude Code (Opus 4.7)** to implement code and infrastructure directly in this repo.

## 2. Roles and boundaries

### 2.1 Perplexity (research & design)

Perplexity is used for:
- Deep research on PoE APIs and data sources (PoEDB, PoE Ninja, GGG developer docs, community tools).
- Designing data models, table schemas, ETL flows, and integration patterns.
- Writing **ready-to-paste prompts** for Claude Code.
- Updating this `CLAUDE_PERPLEXITY_WORKFLOW.md` file (and high-level docs) with:
  - New prompts.
  - Backlog items.
  - Decision log entries.

Perplexity **does not**:
- Modify application code files directly (`.py`, `.ts`, `.sql` inside the repo).
- Change the FOB implementation or server code.

### 2.2 Claude Code (implementation)

Claude Code (Opus 4.7) is used for:
- Creating and editing code in:
  - `packages/` (core models, shared infra, FOB, etc.).
  - `apps/server/` (FastAPI routes, composition logic).
  - `apps/shell/` (when needed for frontend).
  - `scripts/` (utility/ops scripts).
- Implementing DB schemas and migrations (SQL files, Alembic if introduced).
- Implementing ETL pipelines (Python modules under `packages` or `scripts` as appropriate).

Claude Code **may** update this file **only** in the section `5. Backlog & status` (checklist) when explicitly instructed via a prompt.
Claude Code should **not** modify prompts or the decision log.

## 3. Collaboration rules

1. **Single orchestration file**
   - This file is the coordination hub; do not create duplicate orchestration docs elsewhere.

2. **Perplexity writes prompts, Claude executes them**
   - New prompts are added here by Perplexity under section `4. Prompt library`.
   - You copy specific prompts into Claude Code when you want to generate or refactor code.

3. **No silent overwrites**
   - When Claude Code changes repo structure or introduces new modules, it should be instructed to:
     - Reflect the change in `docs/architecture.md` if architecture-level.[cite:63]
     - Update `5. Backlog & status` in this file to mark tasks as done or in progress.

4. **Source of truth for PoE data layer**
   - All design decisions about the PoE data layer (schemas, ETL strategy, data sources) are recorded in `6. Decision log`.

## 4. Prompt library for Claude Code

This section contains prompts that can be copy-pasted into Claude Code. Each prompt assumes it is run inside the `poe1-suite` repo with access to existing files.

### Prompt 001 – Core DB schema (PoE data layer)

```prompt
You are working inside the `poe1-suite` mono-repo. The README describes it as a mono-repo of Path of Exile 1 tools (Python packages under `packages/`, FastAPI backend under `apps/server/`, React shell under `apps/shell/`).[cite:62]

Goal: introduce a **core relational schema** for a PoE data layer focusing on leagues, currencies, base items, and economy snapshots (prices).

Target DB: PostgreSQL.

Create a SQL file at `docs/sql/001_core_tables.sql` with the following tables and constraints:

1. `dim_league`
   - `league_id` SERIAL PRIMARY KEY
   - `league_name` TEXT UNIQUE NOT NULL
   - `game` TEXT NOT NULL CHECK (game IN ('PoE1','PoE2'))
   - `start_date` DATE NULL
   - `end_date` DATE NULL
   - `is_hardcore` BOOLEAN NOT NULL DEFAULT FALSE
   - `is_ssf` BOOLEAN NOT NULL DEFAULT FALSE
   - `raw_source` JSONB NULL  -- original payload from league API

2. `dim_currency`
   - Primary source: PoE Ninja `currencyoverview` / `itemoverview` API (fields like `name`, `detailsId`, `icon`, `chaosEquivalent`).[cite:19]
   - Columns:
     - `currency_id` SERIAL PRIMARY KEY
     - `details_id` TEXT UNIQUE NOT NULL        -- maps PoE Ninja `detailsId`
     - `display_name` TEXT NOT NULL             -- `currencyTypeName` or `name`
     - `icon_url` TEXT NULL
     - `category` TEXT NOT NULL                 -- Currency, Fragment, Oil, Fossil, Essence, etc.
     - `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

3. `dim_base_item`
   - For now only the structure, to be populated later from PoEDB / PyPoE exports.
   - Columns:
     - `base_item_id` SERIAL PRIMARY KEY
     - `base_item_name` TEXT NOT NULL
     - `item_class` TEXT NOT NULL
     - `icon_url` TEXT NULL
     - `level_req` INT NULL
     - `tags` TEXT[] NULL
     - `is_unique_only` BOOLEAN NOT NULL DEFAULT FALSE
     - `valid_from_patch` TEXT NULL
     - `valid_to_patch` TEXT NULL

4. `fact_economy_snapshot`
   - Grain: (league_id, currency_id OR base_item_id, snapshot_ts).
   - Columns:
     - `snapshot_id` BIGSERIAL PRIMARY KEY
     - `league_id` INT NOT NULL REFERENCES dim_league(league_id)
     - `currency_id` INT NULL REFERENCES dim_currency(currency_id)
     - `base_item_id` INT NULL REFERENCES dim_base_item(base_item_id)
     - `snapshot_ts` TIMESTAMPTZ NOT NULL
     - `price_chaos` NUMERIC(18,4) NOT NULL
     - `price_divine` NUMERIC(18,4) NULL
     - `source` TEXT NOT NULL DEFAULT 'poe.ninja'
     - `raw_source` JSONB NULL
   - Add a CHECK constraint so that at least one of `currency_id` or `base_item_id` is NOT NULL.
   - Add indexes for:
     - `(league_id, snapshot_ts)`
     - `(currency_id, snapshot_ts)`
     - `(base_item_id, snapshot_ts)`

General requirements:
- Use `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.
- Add concise `COMMENT ON TABLE` and `COMMENT ON COLUMN` statements explaining the purpose of each table/column.
- Keep SQL formatted cleanly and organized.

After generating the SQL file, briefly summarize the tables and their relationships in a comment block at the top of the file.
```

### Prompt 002 – ETL for PoE Ninja (currencies + price snapshots)

```prompt
You are in the `poe1-suite` repo. A new SQL schema for `dim_league`, `dim_currency`, `dim_base_item`, and `fact_economy_snapshot` exists under `docs/sql/001_core_tables.sql`.

Goal: create an ETL script to ingest **PoE Ninja** economy data into Postgres.

Tasks:

1. Create a Python module at `scripts/poe_ninja_etl.py` that:
   - Uses `asyncio` or synchronous code (your choice, default to sync for simplicity) with `requests` or `httpx`.
   - Reads configuration from environment variables (you can use `pydantic-settings` or simple `os.environ`):
     - `DB_DSN` (Postgres connection string)
     - `POE_LEAGUE` (current league name, e.g. `Necropolis`)
     - `POE_NINJA_BASE_URL` (defaults to `https://poe.ninja/api/data`).[cite:19]

2. Implement a function `fetch_poe_ninja(endpoint: str, league: str, type_: str) -> dict` that:
   - Builds URLs like:
     - `https://poe.ninja/api/data/currencyoverview?league=LEAGUE&type=Currency`
     - `https://poe.ninja/api/data/itemoverview?league=LEAGUE&type=BaseType`
   - Handles basic retries with exponential backoff.
   - Raises a clear exception on non-200 responses.

3. Implement `ensure_league(conn, league_name: str) -> int` that:
   - Ensures a row exists in `dim_league` for `league_name` (game='PoE1' by default).
   - Returns `league_id`.

4. Implement `sync_currencies(conn, league_id: int, league_name: str)` that:
   - Calls PoE Ninja `currencyoverview` for relevant `type` values (Currency, Fragment, etc.), following community docs for available `type` strings.[cite:19]
   - For each entry, upserts into `dim_currency` based on `detailsId`.
   - Inserts a row into `fact_economy_snapshot` for each entry with:
     - `league_id`
     - `currency_id`
     - `base_item_id = NULL`
     - `snapshot_ts = now()`
     - `price_chaos = chaosEquivalent`
     - `price_divine = NULL` (for now)
     - `source = 'poe.ninja'`
     - `raw_source` as JSONB payload of the line.

5. Structure and quality:
   - Use `psycopg2` or `asyncpg` or `sqlalchemy` (choose one and structure it cleanly in a way that fits this repo).
   - Add type hints to all functions.
   - Add a `main()` function and guard (`if __name__ == "__main__":`) that:
     - Reads config.
     - Connects to the DB.
     - Ensures league.
     - Calls `sync_currencies`.

6. Logging & errors:
   - Use the `logging` module with INFO-level logging for high-level steps and DEBUG for details.
   - Fail fast on misconfiguration (missing `DB_DSN` or `POE_LEAGUE`).

Keep the script self-contained and focused: no framework, just a clean ETL utility we can later schedule via cron or CI.
```

### Prompt 003 – ETL scaffold for base items from PoEDB exports

```prompt
You are in the `poe1-suite` repo and there is a Postgres schema with `dim_base_item` already defined.

Goal: scaffold an ETL module that can load base item metadata from a JSON export produced from PoEDB or similar sources.[cite:21]

Create a Python module at `scripts/base_items_etl.py` with the following characteristics:

1. Define a dataclass `BaseItemRecord` with fields:
   - `base_item_name: str`
   - `item_class: str`
   - `icon_url: str | None`
   - `level_req: int | None`
   - `tags: list[str]`
   - `is_unique_only: bool`
   - `valid_from_patch: str | None`
   - `valid_to_patch: str | None`

2. Define a protocol-like base class or simple abstract class `BaseItemSource` with a method:
   - `iter_base_items(self) -> Iterable[BaseItemRecord]`

3. Implement a concrete class `PoEDBJsonBaseItemSource` that:
   - Takes a path to a JSON file in its constructor (e.g. `data/poedb_base_items.json`).
   - Expects the JSON to be a list of objects with at least `name`, `item_class`, and optionally other fields.
   - Maps JSON objects to `BaseItemRecord` instances.

4. Implement a function `load_base_items_to_db(conn, source: BaseItemSource)` that:
   - Iterates over `source.iter_base_items()`.
   - Upserts into `dim_base_item` using `(base_item_name, item_class)` as a natural key.
   - Updates `icon_url`, `level_req`, `tags`, `is_unique_only`, `valid_from_patch`, `valid_to_patch` if the record already exists.

5. Provide a `main()` function that:
   - Reads `DB_DSN` and `BASE_ITEMS_JSON_PATH` from environment variables.
   - Connects to the DB.
   - Instantiates a `PoEDBJsonBaseItemSource` with the JSON path.
   - Calls `load_base_items_to_db`.

Do not implement any scraping or HTTP fetching here. Assume the JSON file has already been downloaded by some other process. Focus on clean structure and upsert logic, with type hints and minimal but clear logging.
```

## 5. Backlog & status

### TODO

- [ ] Create core PoE data schema SQL (`docs/sql/001_core_tables.sql`).
- [ ] Implement PoE Ninja ETL (`scripts/poe_ninja_etl.py`).
- [ ] Implement base items ETL scaffold (`scripts/base_items_etl.py`).
- [ ] Decide where to physically host the Postgres instance (local Docker vs managed) and document it.
- [ ] Connect FOB to the new PoE data layer for price lookup.

### IN PROGRESS

- [ ] FOB foundations in `packages/fob/` (per ARCHITECTURE + FOB_MANUALE docs).[cite:63]

### DONE

- [x] Mono-repo layout and basic tooling (uv, FastAPI app, docs/architecture.md, docs/DEPLOY.md).[cite:62][cite:63]

## 6. Decision log

- 2026-05-14 – We will coordinate Perplexity and Claude Code via a dedicated orchestration file `CLAUDE_PERPLEXITY_WORKFLOW.md` in the repo root.
- 2026-05-14 – Target DB for the PoE data layer is PostgreSQL; initial schema will cover leagues, currencies, base items, and economy snapshots.
- 2026-05-14 – PoE Ninja is the primary external source for economy/pricing data; PoEDB/PyPoE will be used for static game data exports.
