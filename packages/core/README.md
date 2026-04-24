# poe1-core

Shared PoE 1 domain models used by every tool in the suite.

The package is intentionally dependency-light: only `pydantic` for validation. Anything that needs IO, HTTP, or external services belongs in `poe1-shared` or in a tool package — never here.

## What lives here

- `poe1_core.models.enums` — canonical enumerations (`DamageProfile`, `Playstyle`, `ContentFocus`, `Ascendancy`, …). These are the vocabulary every other module speaks.
- `poe1_core.models.league` — `League` metadata.
- `poe1_core.models.item` — `Item`, `ItemMod`.
- `poe1_core.models.pricing` — `PriceValue`, `PriceRange`, `PriceSource`.
- `poe1_core.models.build` — `Build`, `BuildMetrics`, `KeyItem`.
- `poe1_core.models.build_intent` — `BuildIntent`, the normalised representation of a player's query.
- `poe1_core.models.plan` — `PlanStage`, `BuildPlan`, `CoreItem`.

## Principles

1. **Pydantic v2 everywhere.** Validation is the contract.
2. **Enum values are stable strings** (snake_case, lowercased). Never use the raw label outside this package.
3. **JSON round-trip is tested.** Every model must survive `Model.model_validate_json(model.model_dump_json())`.
4. **No business logic.** Methods are validators, factories, or trivial projections only.
