# poe1-suite

A mono-repo of Path of Exile 1 tools. Each tool is a Python package under `packages/`, composed at runtime by `apps/server/` (FastAPI) and a shared frontend `apps/shell/` (React + Vite + Mantine).

> Path of Exile is a trademark of Grinding Gear Games. This project is an independent fan-made utility.

## Tools in this repo

| Tool | Package | Status |
| --- | --- | --- |
| **FOB** — Frusta Oracle Builder (build advisor) | `packages/fob/` | foundations in place, Step 2 next |
| **Faustus** flipper | `packages/faustus/` | planned |
| **Hideout** manager | `packages/hideout/` | planned |

## Repo layout

```
poe1-suite/
├── packages/
│   ├── core/        # shared PoE 1 domain models (Build, Item, League, ...)
│   ├── shared/      # shared infrastructure (http client, config, logging)
│   ├── fob/         # Frusta Oracle Builder
│   └── (future tools…)
├── apps/
│   ├── server/      # FastAPI entrypoint composing all tool routers
│   └── shell/       # React + Vite + Mantine UI (planned)
├── docs/
└── .github/workflows/
```

## Getting started (dev)

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+ (only when working on `apps/shell/`).

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all workspace dependencies
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Run all tests
uv run pytest

# Lint & type-check
uv run ruff check .
uv run ruff format --check .
uv run mypy packages apps
```

## Configuration

All runtime configuration is loaded from environment variables (or a local `.env` file — see `.env.example`). Never commit real API keys.

Key variables:

- `POE_LEAGUE` — current league slug (e.g. `Settlers`, `Necropolis`)
- `POE_NINJA_BASE_URL` — defaults to `https://poe.ninja/api/data`
- `ANTHROPIC_API_KEY` — used by FOB Intent Engine LLM fallback
- `POESESSID` — optional; only needed for authenticated GGG API calls

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full design: module pipeline, data model, build sources strategy, development roadmap.

## License

[MIT](LICENSE).
