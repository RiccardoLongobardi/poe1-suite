# PoB test fixtures

These files are real Path of Building exports used as deterministic inputs
for the `PobSource` parser. Do **not** hand-edit them — the parser must
handle exactly what PoB produces in the wild.

| File | Source | Build |
|---|---|---|
| `pob_YNQeadFwNBmX.txt` | <https://pobb.in/YNQeadFwNBmX/raw> | Marauder / Chieftain, Raise Spectre, level 100 |

If a fixture needs refreshing (e.g. after a PoB format change), replace
the file rather than patching it.
