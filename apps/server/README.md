# poe1-server

FastAPI process that exposes every tool's HTTP surface.

Each tool package provides a `make_router(settings)` factory that returns a `fastapi.APIRouter`. This application imports each factory, mounts the router under the tool's prefix (`/fob`, `/faustus`, `/hideout`, …), and starts uvicorn.

## Run (dev)

```bash
uv run poe1-server
# or
uv run uvicorn poe1_server.main:create_app --factory --reload
```

By default the server listens on `http://127.0.0.1:8765`. Configure via the standard `POE_*` / `LOG_*` / `HTTP_*` environment variables loaded by `poe1_shared.config.Settings`.

## Current endpoints

- `GET /health` — liveness probe.
- `GET /version` — suite version info.

Tool routers are added as each tool's feature set lands.
