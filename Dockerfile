# syntax=docker/dockerfile:1.7
# =============================================================================
# poe1-suite backend (FastAPI + uv workspace) — production image
# =============================================================================
# Two-stage build:
#   1. ``builder`` — install uv, sync the workspace, compile bytecode.
#   2. ``runtime`` — slim Python image with only the venv + sources.
#
# The frontend (apps/shell) is intentionally NOT in this image; it
# ships separately to Vercel as a static SPA. The dockerignore makes
# sure node_modules / dist never sneak in.
#
# Build:
#   docker build -t poe1-server:latest .
# Run:
#   docker run --rm -p 8080:8080 -e PORT=8080 -e HOST=0.0.0.0 \
#     -e ENVIRONMENT=production -e POE_LEAGUE=Mirage \
#     -e CORS_ALLOWED_ORIGINS=https://fob.vercel.app \
#     poe1-server:latest

# -----------------------------------------------------------------------------
# Stage 1: builder — sync the workspace with uv into a virtualenv
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS builder

# uv via the official prebuilt static binary. Pin to a tested version
# so build is reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Copy everything the workspace needs in one shot. We deliberately
# keep this simple (no two-step pyproject-only copy) because each
# sub-package has its own README that hatchling reads at install
# time. .dockerignore keeps the context clean.
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY packages ./packages
COPY apps/server ./apps/server

# Sync the workspace. `--no-dev` skips pytest/ruff/mypy. `--locked`
# refuses to update the lockfile inside the build (reproducibility).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# -----------------------------------------------------------------------------
# Stage 2: runtime — slim image with just the venv + sources
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime

# Non-root user for the running process.
RUN groupadd --gid 1000 app \
 && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    ENVIRONMENT=production \
    LOG_FORMAT=json \
    CACHE_DIR=/data/.cache_http

# Copy the prebuilt venv and the application sources from the builder.
# The venv contains ALL site-packages (including the workspace
# packages installed in editable mode by `uv sync`).
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/packages /app/packages
COPY --from=builder --chown=app:app /app/apps/server /app/apps/server

# Cache directory mount point. Fly.io can mount a persistent volume
# here if you want the on-disk diskcache to survive restarts; if not,
# the cache lives ephemerally in the container fs.
RUN mkdir -p /data/.cache_http && chown -R app:app /data

USER app

EXPOSE 8080

# Healthcheck: hit /health via stdlib so we don't need curl/wget.
# Fly.io has its own probe but a Docker-native check is useful for
# `docker run` smoke tests too.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8080\")}/health', timeout=3).read()" || exit 1

# The console script registered by apps/server/pyproject.toml. Reads
# HOST/PORT from the env (set above) and starts uvicorn.
CMD ["poe1-server"]
