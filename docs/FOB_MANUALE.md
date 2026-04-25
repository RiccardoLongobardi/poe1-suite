# FOB — Frusta Oracle Builder
## Manuale utente

---

## Indice

1. [Cos'è FOB](#1-cosè-fob)
2. [Avvio rapido](#2-avvio-rapido)
3. [Build Finder](#3-build-finder)
4. [Analizza PoB](#4-analizza-pob)
5. [Planner](#5-planner)
6. [API — riferimento curl](#6-api--riferimento-curl)
7. [Interpretare i risultati](#7-interpretare-i-risultati)
8. [Limitazioni note e consigli pratici](#8-limitazioni-note-e-consigli-pratici)

---

## 1. Cos'è FOB

FOB è un advisor per Path of Exile 1 che fa tre cose:

| Funzione | Cosa fa |
|---|---|
| **Build Finder** | Scrivi una frase in italiano o inglese → restituisce le build reali dal ladder di poe.ninja ordinate per affinità con la tua richiesta |
| **Analizza PoB** | Incolla un codice PoB o un link pobb.in/pastebin → ti mostra un riassunto della build normalizzato (classe, skill, difesa, item chiave) |
| **Planner** | Partendo dallo stesso PoB, genera un piano di upgrade a 3 step con i prezzi live da poe.ninja |

Il backend gira su Python/FastAPI alla porta **8765**.
La shell React gira alla porta **5173** (o, in produzione, stessa porta del backend).

---

## 2. Avvio rapido

### Prerequisiti

- `uv` installato (https://docs.astral.sh/uv)
- Variabile d'ambiente `POE_LEAGUE=Mirage` nel file `.env`
- Opzionale: `ANTHROPIC_API_KEY` per il fallback LLM nell'estrazione intent

### Avviare il backend

```bash
# dalla root del repo
uv run poe1-server
```

Il server risponde su `http://127.0.0.1:8765`.
Controlla lo stato: `curl http://127.0.0.1:8765/health`

### Avviare la shell (UI)

```bash
cd apps/shell
npm run dev
```

Apri `http://127.0.0.1:5173` nel browser.
La UI proxia automaticamente tutte le chiamate API al backend su :8765.

---

## 3. Build Finder

**Pagina**: clicca **Build Finder** nella navbar a sinistra.

### Come funziona

Scrivi una descrizione della build che cerchi — in italiano o in inglese — e clicca **Cerca**. Il sistema:

1. Estrae l'intent dalla tua frase (danno, playstyle, difesa, budget, hard constraint)
2. Interroga il ladder di poe.ninja per tutte le 19 ascendancies in parallelo
3. Filtra le build che violano i tuoi vincoli "hard" (es. "no trap", "voglio CI")
4. Punteggia ogni candidata su 6 dimensioni e restituisce le migliori

### Esempi di query

```
voglio una cold dot build comfy per mapping, budget massimo 20 div
looking for a cheap RF jugg, no totems
build tanky con CI per bossing
flicker strike occultist, buon dps
minion build per levelling veloce
```

### Leggere i risultati

Ogni card mostra:

| Campo | Significato |
|---|---|
| **Score totale** | Punteggio 0-1 (più alto = più affine alla tua richiesta) |
| **Classe / Ascendancy** | Es. "Witch / Occultist" |
| **Skill principale** | La skill attiva dominante nella build |
| **DPS** | Danno effettivo riportato da PoB (in milioni) |
| **Life / ES** | Pool difensivo principale |
| **Rank ladder** | Posizione nel ladder ufficiale poe.ninja |

### Filtri hard constraint

Se scrivi termini come quelli sotto, il sistema **esclude** build incompatibili:

| Cosa scrivi | Esclude |
|---|---|
| `no trap`, `senza trappole` | build con trap/mine come skill principale |
| `no totem`, `senza totem` | build totem/ballista |
| `no melee` | cyclone, strike, slam ecc. |
| `no minion`, `senza summoner` | skeleton, zombie, spectre ecc. |
| `CI`, `chaos inoculation` | build NON-CI (life builder) |
| `RF`, `righteous fire` | build che non usano RF |

---

## 4. Analizza PoB

**Pagina**: clicca **Analizza PoB** nella navbar.

### Input accettati

Incolla uno dei seguenti nel campo di testo:

- **Codice PoB raw** — la stringa base64 che Path of Building copia negli appunti (`eNqtW...`)
- **Link pobb.in** — es. `https://pobb.in/abc123`
- **Link pastebin.com** — es. `https://pastebin.com/xYz789`

Clicca **Analizza**.

### Output

Il sistema mostra un riepilogo della build:

- Classe e ascendancy
- Skill principale + i primi 3 support gem
- Profilo danno (Fire/Cold/Lightning/Chaos/Physical + DoT se applicabile)
- Playstyle (self-cast, totem, trap, mine, summoner, trigger)
- Difesa principale (Life, ES, Armour, Evasion)
- Content focus previsto (mapping, bossing, Uber)
- Lista degli **item chiave** (unique e rari rilevanti estratti dal PoB)

### Usi pratici

- Controlla che il parser abbia capito correttamente la tua build prima di passare al Planner
- Condividi il link pobb.in e usa FOB per spiegare la build a qualcuno che non usa PoB
- Verifica quali item chiave vengono estratti (quelli con `importance ≥ 3` finiscono nel piano)

---

## 5. Planner

**Pagina**: clicca **Planner** nella navbar.

### Come si usa

1. Incolla lo stesso input che useresti per **Analizza PoB** (codice, pobb.in, pastebin)
2. Scegli il **Target Goal**:
   - **Solo mapping** — ottimizza per T16 farm, meno attenzione agli Uber
   - **Mapping + boss** *(default)* — bilanciamento mapping/pinnacle boss
   - **Uber capable** — il piano include step verso Uber content
3. Clicca **Genera piano**

### I tre stage del piano

Il planner divide il percorso di upgrade in tre fasi basate sul costo degli item chiave:

| Stage | Budget | Cosa include |
|---|---|---|
| **League start** | 0 - 1 div | Gem dalle quest, rari economici, unique sotto 1 divine. Obiettivo: cap res + farm T1-T8 |
| **Mid-game** | 1 - 25 div | Unique core della build, body 5L/6L, primi jewel. Obiettivo: farm T16 affidabile |
| **End-game** | 25 - 100 div | Chase unique, awakened gem, rari top-tier, min-max finale |

Ogni stage mostra:

- **Budget stimato** (range min-max in divines, prezzi live da poe.ninja)
- **Item da comprare** (ordinati per priorità: 1 = compra subito)
- **Gem da aggiornare** (consigli specifici per la tua skill principale)
- **Content aspettato** (cosa riesci a fare confortevolmente in questo stage)
- **Trigger per passare al prossimo stage** (indicatore concreto di quando avanzare)

### Come leggere i prezzi

| Badge | Significato |
|---|---|
| `HIGH` (verde) | poe.ninja ha 50+ listing → prezzo affidabile |
| `MEDIUM` (giallo) | 10-50 listing → prezzo indicativo |
| `LOW` (rosso) | < 10 listing o item non trovato → prezzo stimato o assente |
| Nessun prezzo | Item non trovato su poe.ninja → va nella fase End-game per sicurezza |

I prezzi sono aggiornati in tempo reale ad ogni richiesta (con cache locale di 5 minuti).

### Esempio pratico: Vortex Occultist

Supponendo questa build (esempio puramente illustrativo):

```
Item chiave:                    Costo approx.
  Tabula Rasa (6L levelling)      30 chaos  (0.15 div)  -> League start
  Inpulsa's Broken Heart          1500 chaos (7.5 div)  -> Mid-game
  Mageblood                       60000 chaos (300 div) -> End-game
```

Il Planner produrrà:

```
League start  [0.0 – 1.0 div]
  #1  Tabula Rasa  (body armour)   ~25-35 chaos  [HIGH]
  Gem: Setup base: Vortex + Bonechill, Hypothermia.
  Trigger: "quando hai ~1 div liquido e res a 75%..."

Mid-game  [7.5 – 25.0 div]
  #1  Inpulsa's Broken Heart  (body armour)  ~6.4-8.6 div  [HIGH]
  Gem: porta tutti i support gem a 20/20...
  Trigger: "quando hai ~25 div e ti senti comodo in T16..."

End-game  [300 – 345 div]
  #1  Mageblood  (belt)  ~255-345 div  [HIGH]
  Gem: Sostituisci con awakened support gem...
```

### Nota sul costo totale

Il costo totale mostrato in testa alla pagina è la **somma dei midpoint** dei tre stage. In presenza di item molto costosi (come un Mageblood da 300 div), il totale sarà dominato dall'End-game — è normale e intenzionale.

---

## 6. API — riferimento curl

Tutti gli endpoint accettano e restituiscono JSON. Base URL: `http://127.0.0.1:8765`.

### 6.1 `POST /fob/extract-intent`

Converte una frase libera in un intent strutturato.

```bash
curl -s -X POST http://127.0.0.1:8765/fob/extract-intent \
  -H "Content-Type: application/json" \
  -d '{"query": "voglio una cold dot occultist per mapping, budget 30 div"}' \
  | python -m json.tool
```

Risposta (selezione campi chiave):

```json
{
  "damage_profile": "cold_dot",
  "playstyle": "self_cast",
  "character_class": "witch",
  "content_tags": ["mapping"],
  "budget_div_max": 30.0,
  "confidence": 0.92,
  "parser_origin": "rules"
}
```

### 6.2 `POST /fob/recommend`

Data una BuildIntent, restituisce le build dal ladder ordinate per score.

```bash
curl -s -X POST http://127.0.0.1:8765/fob/recommend \
  -H "Content-Type: application/json" \
  -d '{
    "intent": {
      "damage_profile": "cold_dot",
      "playstyle": "self_cast",
      "content_tags": ["mapping"]
    },
    "top_n": 5
  }' | python -m json.tool
```

Risposta:

```json
{
  "ranked": [
    {
      "source_id": "ninja::occultist::12345",
      "character_class": "witch",
      "ascendancy": "occultist",
      "main_skill": "Vortex",
      "score": {
        "total": 0.847,
        "damage": 0.9,
        "defense": 0.7,
        "budget": 0.8,
        "playstyle": 1.0,
        "content": 0.8,
        "popularity": 0.6
      }
    }
  ],
  "total_candidates": 438,
  "intent": { "..." : "..." }
}
```

### 6.3 `POST /fob/analyze-pob`

Analizza un codice PoB o URL.

```bash
curl -s -X POST http://127.0.0.1:8765/fob/analyze-pob \
  -H "Content-Type: application/json" \
  -d '{"input": "https://pobb.in/abc123"}' \
  | python -m json.tool
```

Risposta:

```json
{
  "build": {
    "sourceId": "pob::a3f8c12d9e01",
    "characterClass": "witch",
    "ascendancy": "occultist",
    "mainSkill": "Vortex",
    "supportGems": ["Bonechill", "Hypothermia", "Swift Affliction"],
    "damageProfile": "cold_dot",
    "playstyle": "self_cast",
    "contentTags": ["mapping", "bossing"],
    "defenseProfile": "energy_shield",
    "keyItems": [
      {
        "slot": "body_armour",
        "item": { "name": "Shavronne's Wrappings", "rarity": "unique" },
        "importance": 5
      }
    ]
  },
  "snapshot": { "...": "XML completo parsato" }
}
```

### 6.4 `POST /fob/plan`

Il workflow completo: PoB → Build → piano prezzato.

```bash
curl -s -X POST http://127.0.0.1:8765/fob/plan \
  -H "Content-Type: application/json" \
  -d '{
    "input": "https://pobb.in/abc123",
    "target_goal": "mapping_and_boss"
  }' | python -m json.tool
```

`target_goal` accetta: `"mapping_only"` | `"mapping_and_boss"` | `"uber_capable"`

Risposta (struttura):

```json
{
  "build": { "...": "come /analyze-pob" },
  "plan": {
    "buildSourceId": "pob::a3f8c12d9e01",
    "targetGoal": "mapping_and_boss",
    "stages": [
      {
        "label": "League start",
        "budgetRange": {
          "min": { "amount": 0.0, "currency": "divine" },
          "max": { "amount": 1.0, "currency": "divine" },
          "source": "poe_ninja",
          "confidence": "medium"
        },
        "expectedContent": ["league_start", "mapping"],
        "coreItems": [
          {
            "name": "Tabula Rasa",
            "slot": "body_armour",
            "rarity": "unique",
            "buyPriority": 1,
            "priceEstimate": {
              "min": { "amount": 25.5, "currency": "chaos" },
              "max": { "amount": 34.5, "currency": "chaos" },
              "confidence": "high"
            }
          }
        ],
        "gemChanges": ["Setup base: Vortex + Bonechill, Hypothermia."],
        "upgradeRationale": "Setup base con i gem dalle quest...",
        "nextStepTrigger": "Quando hai accumulato ~1 div liquido..."
      }
    ],
    "totalEstimatedCost": {
      "min": { "amount": 8.5, "currency": "divine" },
      "max": { "amount": 26.0, "currency": "divine" }
    }
  }
}
```

### 6.5 Endpoint di sistema

```bash
# health check
curl http://127.0.0.1:8765/health

# versione
curl http://127.0.0.1:8765/version

# documentazione interattiva (Swagger UI)
open http://127.0.0.1:8765/docs

# schema OpenAPI grezzo
curl http://127.0.0.1:8765/openapi.json
```

---

## 7. Interpretare i risultati

### Score del Build Finder

Lo score totale va da 0 a 1. La composizione:

| Dimensione | Peso | Cosa misura |
|---|---|---|
| `damage` | ~25% | DPS relativo al pool di candidati (percentile) |
| `defense` | ~20% | Life/ES relativo al pool |
| `budget` | ~20% | Quanto il costo stimato si avvicina al budget indicato |
| `playstyle` | ~15% | Match esatto con il playstyle richiesto |
| `content` | ~10% | Match con i content tag (mapping/bossing/uber) |
| `popularity` | ~10% | Rank nel ladder (più alto = più testato dalla community) |

Punteggi sopra 0.75 indicano un ottimo match. Sotto 0.50 è segnale che il pool non ha molti candidati per quella query.

### Confidenza dei prezzi nel Planner

- **HIGH** → usa il prezzo con fiducia
- **MEDIUM** → controlla manualmente su poe.trade prima di comprare
- **LOW** → item raro o niche, confronta con poe.trade e chatta in trade
- **Nessun prezzo** → item non listato su poe.ninja nell'ultima snapshot; cerca manualmente

### Budget heuristico vs. data-driven

Se uno stage non ha item prezzati, il budget mostrato è **HEURISTIC** (sfumato in grigio nell'UI). Questo succede quando:
- Nessun key item della build ricade in quello stage
- Tutti gli item di quello stage non sono stati trovati su poe.ninja

Il range HEURISTIC corrisponde ai limiti standard dello stage (es. [1, 25] div per Mid-game) e va usato come riferimento generale, non come preventivo preciso.

---

## 8. Limitazioni note e consigli pratici

### Cosa FOB non fa (ancora)

- **Rari e craft**: il planner gestisce solo unique. Armature rare, armi, gioielli non-unique non appaiono nel piano.
- **Cluster jewel**: non ancora estratti dal parser PoB.
- **Levelling item temporanei**: il planner non distingue tra un item che usi solo durante il levelling e uno che tieni a lungo termine.
- **Vendor recipe**: nessuna valutazione di recipe (Chaos orb, Regal, ecc.).

### Tips

1. **Prima analizza, poi pianifica.** Usa `Analizza PoB` per verificare che il parser abbia capito la build, poi vai sul Planner. Se un item chiave non compare nell'analisi, non comparirà neanche nel piano.

2. **Build Finder + Analizza PoB insieme.** Trova una build con il Finder, incolla il link pobb.in del primo risultato nell'Analizzatore per capire come è strutturata prima di seguirla.

3. **Target Goal fa differenza per i gem.** Con `uber_capable` il planner elenca gem awakened come step dell'End-game. Con `mapping_only` si ferma prima.

4. **I prezzi scadono.** poe.ninja aggiorna i prezzi ogni 5-10 minuti; FOB usa una cache locale di 5 minuti. Per un preventivo preciso, genera il piano a mercato fresco e non fidarti di un PDF di 3 giorni fa.

5. **Build con link pobb.in pubblici.** Se il link è di qualcun altro e il codice non è stato aggiornato da lui, stai analizzando un vecchio snapshot. Usa sempre il codice esportato direttamente dal tuo PoB per il Planner.

6. **Query in italiano.** Il parser di intent è addestrato principalmente su frasi italiane e inglesi PoE-standard. Evita abbreviazioni molto gergali o nomi di skill storpiati — es. scrivi "Righteous Fire" non "RF" se vuoi un match sicuro.

---

*Generato il 2026-04-25 — FOB v1.0 (Step 8 completo)*
