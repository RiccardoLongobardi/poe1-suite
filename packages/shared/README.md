# poe1-shared

Shared infrastructure used by every tool in the suite.

## Modules

- `poe1_shared.config` — settings loaded from environment (and optional `.env`). `Settings` is the single entry point.
- `poe1_shared.http` — async HTTP client with retry (tenacity) and on-disk cache (diskcache). Wraps `httpx.AsyncClient`.
- `poe1_shared.logging` — structured logging setup via `structlog`. Call `configure_logging(settings)` once at process startup.

## Usage

```python
from poe1_shared.config import Settings
from poe1_shared.logging import configure_logging, get_logger
from poe1_shared.http import HttpClient

settings = Settings()
configure_logging(settings)
log = get_logger(__name__)

async with HttpClient(settings) as client:
    data = await client.get_json("https://poe.ninja/api/data/currencyoverview?league=Standard&type=Currency")
    log.info("fetched_currency", entries=len(data.get("lines", [])))
```
