# Step 14 — Pohx-style stage-by-stage build

## Goal

Trasformare il planner attuale (6 stage con gem advice + KeyItem
pricing) in un sistema **stage-by-stage completo Pohx-style**: per
ogni stage, l'utente vede una build COMPLETA — items su ogni slot,
skill tree allocato, gem links, note, e il risultato è un **PoB
code importabile** (uno per stage).

Esempio target: <https://www.pohx.net> — 7 progressioni da day-0 a
mirror-tier, ognuna con tree allocato, gear suite completa, gem
setup esatto.

## Cosa abbiamo oggi

| Componente | Stato |
|---|---|
| 6 stage (Early Campaign → High Investment) | ✅ |
| 49 BuildTemplate skill-keyed con gem advice per stage | ✅ |
| Reverse-progression engine con upgrade ladder per item | ✅ |
| KeyItem pricing live (poe.ninja + Trade) | ✅ |
| target_goal modulazione stage layout | ✅ (Step 14 prep) |

## Cosa manca per Pohx-style

### 1. Tree progression per stage

Ogni stage deve avere uno **skill tree URL** o **node list** valida.
Esempio per RF Jugg:
- Early Campaign: Marauder start → Iron Reflexes → Resolute Technique
- Mid Campaign: + Heart of Flame, Diamond Skin, life clusters baseline
- ...
- High Investment: + Forbidden notable allocations, +cluster jewel
  notables specifici

**Implementazione**: nuovo modulo `poe1_fob/tree/` con:
- `TreeProgression` dataclass: per ogni stage_key un `set[int]` di node ids
- Tabella per template (estendere `BuildTemplate` con `for_stage_tree`)
- Tree URL generator (encoding `0x...` Path of Building format)

### 2. Gear suite per stage (tutti gli slot)

Ogni stage = lista di items per ogni slot (helmet/body/gloves/boots/
belt/amulet/ring1/ring2/weapon/offhand/flask×5/jewel×N).

Oggi il planner mostra solo i `KeyItem` (4-7 unique). Manca tutto
il rare gear plug. Pohx fa questo a mano per ogni stage; noi
possiamo:
- **Manuale**: estendere i template con `for_stage_gear()`
- **Generato**: derivare slot-by-slot da `Build.equipment` del PoB
  endgame, downgrade per stage tramite `InfluenceItemDegrader`

**Implementazione**: `BuildTemplate.for_stage` ritorna anche un
`StageGearSet` (tuple di `Item` per ogni slot, plus rare-craft hints).

### 3. Gem setup completo per stage

Oggi: `gem_changes` come stringhe testuali. Serve invece:
- `links: tuple[GemLink, ...]` per ogni stage (6L body, 4L gloves,
  4L helmet, 3L boots/weapon)
- Ogni `GemLink`: skill_gem + supports + level/quality target
- Trasferimento al PoB: ogni gem nel suo socket con level/quality
  giusti

### 4. Notes per stage

Esempio Pohx:
> "RF damage is unsustainable until you have Springleaf. Drop RF
> if you take heavy hits and re-light it after."

**Implementazione**: `StagePlanContent.notes: tuple[str, ...]`
extension. Già presente come `rationale`/`gem_changes` ma
formato libero, da strutturare meglio.

### 5. PoB code generator per stage

Il colpo di grazia: il PoB che importi nell'app desktop. Format:
- XML (PoB schema documentato in `https://github.com/PathOfBuildingCommunity/PathOfBuilding/wiki/Build-share-XML`)
- zlib compress
- url-safe base64 encode

`packages/fob/src/poe1_fob/pob/encode.py` (nuovo) — l'inverso di
`pob/decode.py`. Input: `Build` + `StageGearSet` + `TreeProgression` +
gem links → XML → compressed code.

### 6. UI: stage cards interattive

`StageCard.tsx` espande così:
- Tab/sub-block: Tree (link al webtree o inline render)
- Tab: Gear (grid 6+5 slot con item)
- Tab: Gems (link visualization)
- Tab: Notes
- Bottone: **"Importa in PoB"** (copia il code in clipboard)

## Effort estimate

Step 14 è grosso. Stima rough:

| Task | Stima |
|---|---|
| Tree progression model + 5 template iconici | 2-3 ore |
| Gear suite model + 5 template iconici | 3-4 ore |
| Gem links structured + 5 template | 2 ore |
| PoB encoder | 4-6 ore (XML schema, encoding edge cases) |
| UI overhaul StageCard tabs | 3-4 ore |
| Tests + integration | 2 ore |
| **Totale** | **~16-20 ore** |

Da spalmare su più sessioni. Suggerimento: T1 = solo tree progression
per RF Jugg (proof-of-concept), poi expand.

## Roadmap turni

- **T1**: Tree model + RfPohxTemplate.for_stage_tree (5 stage tree URL)
- **T2**: Gear set model + RfPohxTemplate.for_stage_gear (5 stage gear)
- **T3**: Gem links structured + RfPohx
- **T4**: PoB encoder + smoke test (importable RF stage 1)
- **T5**: UI tabs in StageCard
- **T6**: Estendi a 2-3 altri template signature (Vortex Occ, TS Deadeye)
- **T7+**: Coverage incrementale dei restanti template
