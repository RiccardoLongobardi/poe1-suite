# poe1-builds

Ladder build ingestion for Path of Exile 1.

Stand-alone package consumed by FOB (build advisor): exposes a
`BuildSource` abstraction, a concrete `NinjaBuildsSource` adapter that
reverse-engineers the poe.ninja protobuf search API, and a
`BuildsService` facade with server-side filters.

## Data shape (poe.ninja, reverse-engineered 2026-04-24)

poe.ninja's builds API post-PoE2 split is:

- `GET /poe1/api/data/index-state` (JSON) — snapshot versions + league
  list. Same endpoint as the pricing package; we reuse its version resolution.
- `GET /poe1/api/builds/{version}/search?overview={slug}[&class=X&skills=Y&...]`
  — returns **protobuf** (`application/x-protobuf`) in a columnar format
  containing **all** characters matching the filters, with per-dimension
  facet counts. A single unfiltered Mirage snapshot is ~50 KB;
  per-class filtered slices are ~35-40 KB.
- `GET /poe1/api/builds/{version}/character?account=X&name=Y&overview=slug&type=Exp&timeMachine=`
  — returns **JSON** (~150 KB per char), including `pathOfBuildingExport`
  and fully-hydrated items, skills, passives, masteries, flasks, jewels,
  cluster jewels, ascendancies, pantheon, bandit. The PoB export feeds
  directly into the existing `poe1-fob.pob` pipeline.

## Public API (planned)

```python
from poe1_shared.config import Settings
from poe1_shared.http import HttpClient
from poe1_builds import BuildsService

async with HttpClient(Settings()) as http:
    builds = BuildsService(http=http, league="Mirage")
    snapshot = await builds.list_builds(class_="Slayer", level_range=(95, 100))
    for ref in snapshot.refs[:5]:
        full = await builds.get_detail(ref)
        # -> FullBuild with pob_export ready for poe1_fob.pob
```
