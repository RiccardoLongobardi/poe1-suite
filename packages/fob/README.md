# poe1-fob — Frusta Oracle Builder

Path of Exile 1 build advisor. Takes a natural-language query (IT or EN) or a PoB export, returns ranked build recommendations with a 3-stage progression plan and cost estimates.

## Status

Foundations are in place (`poe1-core` models, `poe1-shared` infrastructure). Implementation happens in steps:

1. ✅ Foundation (this commit).
2. ⏭️ **Next — PoB Source.** Decode + parse PoB export codes, produce a fully-populated `Build`. First user-visible endpoint: `POST /fob/analyze-pob`.
3. Pricing Engine (poe.ninja client).
4. poe.ninja Builds Source (ladder ingestion).
5. Intent Engine (rule-based + LLM fallback).
6. Ranking Engine + SourceAggregator.
7. Planner.
8. Output composer + UI.

See [`docs/architecture.md`](../../docs/architecture.md) for the full design.

## Package layout (target)

```
src/poe1_fob/
├── intent/
├── sources/
│   ├── pob/        # Step 2
│   └── poe_ninja/  # Step 4
├── ranking/
├── pricing/
├── planner/
└── api/            # FastAPI router, mounted by apps/server
```

Currently only an empty `src/poe1_fob/__init__.py` is provided — the subpackages are added step by step as the features ship.
