# poe1-pricing

Pricing lookup for Path of Exile 1 items & currency.

Stand-alone package: consumed by FOB (to cost key items on a build plan),
planned consumer Faustus (to detect intra-Faustus arbitrage), and any
future tool in the suite that needs a `name → chaos/divine value` lookup.

## Sources (current)

- **poe.ninja** (`/poe1/api/economy/stash/{version}/{currency|item}/overview`).
  Freshness: poe.ninja snapshots approximately hourly; we cache responses
  with the suite's `HttpClient` (TTL default 1h — align with upstream).

## Public API

```python
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient
from poe1_pricing.service import PricingService

async with HttpClient(Settings()) as http:
    pricing = PricingService(http=http, league="Mirage")
    quote = await pricing.quote_by_name("Mageblood")
    # -> PriceQuote(chaos_value=..., divine_value=..., listing_count=...)
```
