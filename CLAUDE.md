# CLAUDE.md — poe1-suite

Instructions for any Claude Code session working in this repo.
Read this file top-to-bottom before doing any work.

## Who the user is

- **Riccardo** — Italian PoE 1 player, builds tools for himself (ric.longobardi@outlook.it).
- Prefers conversation in **Italian**, technical identifiers/commands in **English**.
- Values: "niente fittizio" — no fake/mocked data. Every module ships with real fixtures and is end-to-end playable before the next one starts.

## What this repo is

`poe1-suite` is a uv workspace monorepo of Path of Exile 1 tools. FastAPI backend on port 8765, React/Mantine shell planned. Membership rules:

- `packages/*` → library packages (`poe1-core`, `poe1-shared`, `poe1-pricing`, `poe1-builds`, `poe1-fob`). Each exposes a FastAPI `make_router(settings)` when it has HTTP endpoints.
- `apps/*` → runnable apps. `apps/server/` mounts all routers. `apps/shell/` is the React frontend and is **excluded** from the uv workspace.

## Non-negotiable conventions

1. **Python 3.12**, Pydantic v2, FastAPI, httpx async. All Pydantic models are `frozen=True`. Use `populate_by_name=True` with `camelCase` aliases when serializing to JSON that matches external APIs.
2. **`uv` is the tool** — never `pip`, never `python -m venv`. Commands below.
3. **Test import mode is `importlib`** (configured in `pyproject.toml`). To avoid conftest namespace collisions between packages, each `packages/*/` dir has an empty `__init__.py` extending the dotted module path. Don't remove those.
4. **Ruff is strict** — `E W F I B SIM C4 UP ANN Q RUF` are enabled. Tests are exempt from `ANN`. `**/generated/**` is excluded entirely. Do **NOT** enable the `TCH` rules — they break Pydantic v2 (field annotations need to be importable at runtime).
5. **Mypy is `strict = true`** across 60+ source files. Every public function must be fully typed. `tests/*` has `disallow_untyped_defs = false` override.
6. **No fake data ever.** Tests use real fixtures captured from live poe.ninja / pobb.in. If you need new fixtures, capture them live and commit them under `packages/<pkg>/tests/fixtures/`.

## The gate (run before declaring anything done)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

All four must pass with zero errors. Current baseline: **489 tests green (2 skipped — integration/LLM), 91 files type-checked clean, 89 files formatted clean**.

## What's built (state as of 2026-04-25, end of Step 8 — FOB completo)

| Module | Package | Routes | Status |
|---|---|---|---|
| Domain models | `poe1-core` | — | done (Build, Intent, Plan, Item, League, enums) |
| HTTP/config/logging | `poe1-shared` | — | done (httpx + tenacity + diskcache, pydantic-settings, structlog) |
| PoB ingest + parser + mapper | `poe1-fob` | `POST /fob/analyze-pob` | done (raw / pobb.in / pastebin; full XML parse; Build mapping) |
| poe.ninja economy (currency, uniques, cluster, jewels, …) | `poe1-pricing` | `GET /pricing/quote`, `GET /pricing/snapshot` | done |
| poe.ninja ladder builds | `poe1-builds` | `GET /builds/list`, `GET /builds/detail` | done (protobuf columnar search + JSON hydration, 19 ascendancy fan-out, `main_skill` / `defense_type` filters) |
| IntentExtractor | `poe1-fob` | `POST /fob/extract-intent` | done (hybrid rule-based IT+EN + Anthropic Haiku tool-use fallback; 15 fixture cases; confidence threshold 0.70) |
| Ranking Engine | `poe1-fob` | `POST /fob/recommend` | done (SourceAggregator fan-out → hard-constraint filter → 6-dim weighted scorer → top-N; 49 unit tests) |
| **Planner v2** | `poe1-fob` | `POST /fob/plan`, `POST /fob/plan/stream` | done — 6-stage layout (Early/Mid/End Campaign + Early/End Mapping + High Investment), variant-aware unique pricing + Trade-API rare pricing, BuildTemplate registry (RfPohx detailed, GenericTemplate fallback), SSE streaming con progress + ETA |
| UI shell | `apps/shell` | — | done (React 18 + Vite 5 + Mantine v7 + TanStack Query; Build Finder + PoB Analyzer + Planner; `npm run dev` on :5173) |

Server: `uv run poe1-server` → <http://127.0.0.1:8765>. `/health`, `/version`, plus all the routes above.
Shell dev: `cd apps/shell && npm run dev` → <http://127.0.0.1:5173> (proxies API to :8765).

## What's next (Step 9 — Pricing v2)

In progress: pricing affidabile con confidence ≥60-75 % anche per uniques con varianti e rari custom-craftati.

- **9.1 — variant-aware uniques** ✅ done (2026-04-25). HelmetEnchant + Oil categorie nuove; `PriceSnapshot.by_name_and_variant`/`variants_of`; `PricingService.quote_unique_variant`/`quote_variants`; modulo `poe1_pricing.variants` con resolver protocol + registry + resolver per Forbidden Shako, Forbidden Flame, Forbidden Flesh, Impossible Escape (35 nuovi test).
- **9.2 — GGG Trade API source** ✅ done (2026-04-25). Nuovo `TradeSource` async in `poe1_pricing.sources.trade`: search → fetch → trimmed-median pricing in chaos. `RateLimitState` parser sui header `X-Rate-Limit-Ip`, sleep proattivo a 80% di headroom + `Retry-After` honoring sui 429. `TradeQuery` + `StatFilter` per query stat-aware. `HttpClient` esteso con `post_json` e `request_json` (no-cache) generici. 32 nuovi test con `httpx.MockTransport`.
- **9.3 — PoB mod extraction** ✅ done (2026-04-25). Due nuovi moduli in `poe1_fob.pob`: `uniques.unique_variant()` (item → registry → variant string) e `rares.{clean_mods, valuable_stat_filters}` (filtra metadata PoB tipo `Item Level:`, `Sockets:`, influence tags + estrae StatFilter dai mod chiave). `MOD_PATTERNS` con ~30 stat-id GGG per Life/ES/Mana, resistenze, suppression, level of socketed gems, attributi, crit, cast/attack speed. 35 nuovi test (variant resolution, metadata filtering, pattern matching, full pipeline su PoB reale).
- **9.4a — integrazione planner + SSE + UI loader** ✅ done (2026-04-25). `PricingPort` esteso con `quote_unique_variant`. `PlannerService` riscritto con `plan_with_progress()` async generator che emette `PricingProgress` (start/item_started/item_done/done) con ETA dinamico (heuristic upfront → average osservato dopo il primo item). Variant resolver via `Item.mods` text. `plan()` rimane wrapper sync. Endpoint `POST /fob/plan/stream` con SSE (`text/event-stream`, `data:` frames). Frontend `planBuildStream()` async generator + `<PricingProgressBar>` con Mantine `<Progress>`, ETA countdown live (~10 Hz). `HttpClient.post_json`/`request_json` generici. 12 nuovi test (lifecycle eventi, ETA, variant integration). Baseline 457 verdi, 89 mypy, 87 format.
- **9.4b — rare-via-Trade** ✅ done (2026-04-25). Mapper PoB esteso per promuovere rari high-value a `KeyItem` (≥2 stat filter riconosciuti tra `MOD_PATTERNS`). Nuovo `TradePort` Protocol nel planner (opzionale). `PlannerService` dispatch: UNIQUE→ninja con variant, RARE→Trade con `TradeQuery(type=base_type, stats=...)` percentile pricing. Helper `quote_trade_range()` stampa `PriceSource.TRADE_API`. ETA upfront contabilizza `n_trade × 6s`. Router wire `TradeSource(http, league)` accanto a `PricingService`. `valuable_stat_filters_from_mods()` accetta `Iterable[str]` direttamente. 4 nuovi test (Trade dispatch, skip senza port, skip < 2 mod, ETA mix). Baseline 461 / 89 / 87.

## Step 9 completo

Step 9 (Pricing v2) chiuso. Cosa abbiamo:
- Variant-aware unique pricing per Forbidden Shako/Flame/Flesh, Impossible Escape (4 resolver registrati)
- GGG Trade API rate-limit aware client per rari custom-craft
- PoB mod extraction con 30+ pattern → stat-id GGG
- Streaming planner (SSE `/fob/plan/stream`) con progress + ETA dinamico
- UI con barra di caricamento + countdown ETA in tempo reale

## Step 10 completo

Step 10 (Planner v2) chiuso. Cosa abbiamo:
- **6 fasi**: Early/Mid/End Campaign + Early/End Mapping + High Investment, ognuna con range di divines, rationale di default, content focus, trigger to advance. Bucketing items per divine midpoint con clamp che preserva l'invariante monotone-midpoint del `BuildPlan`.
- **`BuildTemplate` system** in `poe1_fob.planner.templates`: protocol + registry-based dispatch (`pick_template(build)`). `GenericTemplate` come fallback (deriva content da main_skill + support_gems), `RfPohxTemplate` come reference fully-detailed (Holy Flame Totem early → Unflinching switch → Kaom's Heart → Mageblood). 5 nuovi test sui template.
- `PlannerService.template_override` kwarg per i test.
- Aggiornati i test esistenti per il nuovo layout 6-stage (40 verdi nel modulo planner).

Templates futuri da aggiungere: Vortex, Spectre, Spark, Bone Spear, Cyclone (struttura già pronta, serve solo riempire i 6 metodi `for_stage` per ognuno).

## Step 11 completo

Step 11 (UI overhaul) chiuso. Cosa abbiamo:
- **Tema astrale viola** (`apps/shell/src/theme.ts`): palette `astral` + `gold` come custom Mantine colors, `primaryColor=astral`, primaryShade 5/6 dark/light. Headings su Cinzel/Marcellus serif, body su Inter.
- **`index.css`**: background astrale (3 radial gradients viola), animation primitives `astral-pulse` / `astral-fade-in` / `astral-twinkle` / `astral-rotate-slow`, classi `.fob-feature-card` con hover-grow + glow.
- **Welcome page** (`/`): logo orb pulsing, tagline "FOB · Frusta Oracle Builder", CTA "Inizia" con stagger animation. Star-field di 24 punti twinkling. Setta `localStorage.fob_seen_welcome` al click → visite future skippano direttamente a `/home`. State helper in `state/welcome.ts`.
- **Home page** (`/home`): hero + 3 feature card (Build Finder, Analizza PoB, Planner) con icona, descrizione, esempio in monospace, hover-glow. Card "Cosa puoi fare" con 4 esempi pratici. Card "Supporta" gold-bordered con CTA → modale donation.
- **DonationModal**: copy in italiano, 2 sezioni icon+testo (cosa cambia / quanto donare), CTA gold "Apri PayPal — paypal.me/riclong" con `target=_blank rel=noopener`.
- **Routing react-router-dom**: BrowserRouter wraps la app, Routes per `/` `/home` `/finder` `/analyze` `/planner` + 404→/home redirect. AppShell solo sulle route non-welcome. Navbar usa `useLocation` per attive states; lift-to-planner ora via `navigate('/planner')` invece che state-based. "Supporta" button anche nella navbar.

## Step 12 completo

Step 12 (Templates aggiuntivi + UI BuildCard upgrade) chiuso. Cosa abbiamo:
- **17 template totali** in `poe1_fob.planner.templates`. RfPohx + 16 nuovi:
  - Caster: Vortex Occultist, Spark Inquisitor, Bone Spear Necro, Hexblast Mines, Detonate Dead Necro, Bane Occultist
  - Attack: Cyclone Slayer/Berserker, Lightning Strike Raider, Tornado Shot Deadeye, Frost Blades Raider, Toxic Rain Pathfinder
  - Minion: Raise Spectre Necro, Skeleton Mages, Animate Weapon
  - Totem: Holy Flame Totem Hierophant (non-RF), Shrapnel/Lancing Ballista Deadeye
  - Ognuno ha advice mirato per Early Campaign / Mid Campaign / Early Mapping / End Mapping (gli stage non sovrascritti cadono su `GenericTemplate.for_stage`)
- `_matches_skill(*needles)` helper per matcher case-insensitive substring.
- `pyproject.toml`: per-file-ignore E501 per `templates.py` (testo italiano descrittivo).
- 4 nuovi test (registry coverage, Vortex/Cyclone/Spectre signature advice).
- **BuildCard upgrade**: EHP visibile accanto a Life/ES e DPS, pulsante "Copia link" che mette in clipboard l'URL pubblico poe.ninja del personaggio (con feedback "Copiato"), main gems lazy-fetched dal `/builds/detail` quando l'utente espande la card. Nuova API `getDetailFull(account, name)` espone anche `skills: SkillGroup[]`.

## Step 13.A1+A2 completo

Step 13.A — poe.ninja-style item Trade search integration (parte 1, MVP).

**Backend** (`/fob/trade-search`):
- Nuovo endpoint POST con `TradeSearchRequest` (item_name + item_type + tuple di `TradeSearchModFilter` con stat_id+min+max + online_only + min_links 1-6) → `TradeSearchResponse` (league + search_id + url + total_listings).
- Internamente costruisce un `TradeQuery` (riusando la stessa abstraction di Step 9.2), chiama `TradeSource.search()`, riformatta come `https://www.pathofexile.com/trade/search/<league>/<search_id>` da aprire in nuova tab.
- Validation 422 quando il payload non ha né nome né tipo né mod (no-empty-query rule).
- 6L / 5L socket constraint passato via `extra_filters.socket_filters` di GGG. 10 nuovi test sui validators Pydantic.

**Frontend**:
- Nuovo client `tradeSearch(req)` in `api/fob.ts` + tipi `TradeSearchModFilter` / `TradeSearchRequest` / `TradeSearchResponse` in `types.ts`.
- Nuovo componente `TradeSearchDialog` (Mantine `<Modal>`):
  - Header con item name/base in badge.
  - Lista mod toggleable (Switch) con strictness slider 50-100% (default 80%, marker visivo a 80 e 100).
  - Computed live: per ogni mod attivo mostra il `min` calcolato (`rolled_value × strictness/100`).
  - Optional 5L/6L socket constraint quando il caller passa `allowLinks=true`.
  - "Apri su Trade" → POST → `window.open(url, '_blank', 'noopener,noreferrer')`.
- `StageCard` integrato: ogni `ItemRow` ha un `<ActionIcon>` "Cerca su Trade" con `<IconSearch>` che apre il dialog. Per uniques passa `itemName=name`; allowLinks=true per body armour.

**Note sui limiti dell'MVP**: oggi `CoreItem` non porta `mods`/`base_type`, quindi per i rari del Plan il dialog ha la lista mod vuota (la ricerca sarà solo per slot/base se aggiunto). Step 13.A3 estenderà `CoreItem` con questi campi e popolerà il dialog con i mod estratti.

Baseline: 480 test verdi / 90 mypy / 88 format. Build frontend 508 KB / 159 KB gzip.

## Step 13.A3 completo

Step 13.A3 — popolamento dialog Trade-search dalla mod text del PoB.

**Modello core**:
- `CoreItem` esteso con `base_type: str | None = None` e `mods: tuple[str, ...] = ()`. Defaults vuoti per backward-compat con plan serializzati pre-A3.
- `_key_item_to_core_item()` nel planner service popola entrambi i nuovi campi dal `KeyItem.item.base_type` + `KeyItem.item.mods` (tuple di mod text).

**Backend** (`POST /fob/extract-trade-mods`):
- Nuovo endpoint stateless: prende `{mods: list[str]}` e ritorna `{mods: list[ExtractedTradeMod]}` con `(line, stat_id, value, label)` per ogni mod riconosciuto da `MOD_PATTERNS`.
- Internamente: `clean_mod_lines()` (nuovo helper pubblico in `pob/rares.py` che espone `_clean()` per stringhe) → `extract_mods()` → dedupe by `stat_id`.
- Zero HTTP esterni — serve solo per il pattern matching client-friendly.
- 5 nuovi test sui modelli Pydantic.

**Frontend**:
- Tipi `ExtractedTradeMod`, `TradeModExtractRequest`, `TradeModExtractResponse` in `types.ts`. `CoreItem` esteso con `base_type` e `mods` opzionali.
- Client `extractTradeMods(mods)` in `api/fob.ts`.
- `TradeSearchDialog` ora accetta sia `mods` (rows pre-extracted) sia `rawMods` (text); su `opened=true` con `rawMods` non vuoto fa `useEffect` fetch all'endpoint preview e popola la lista. Loader Mantine durante l'estrazione, fallback "non riconosciuti" se il match table non trova nulla.
- `StageCard` passa `tradeItem.base_type` come `itemType` e `tradeItem.mods` come `rawMods` — il dialog ora ha la lista mod popolata automaticamente per qualsiasi item del Plan, **non solo per gli unique**.

Baseline: 485 test verdi / 91 mypy / 89 format. Frontend build 508 KB / 159 KB gzip.

## Step 13.B completo

Step 13.B — Watcher's Eye combo pricing via Trade.

- **`MOD_PATTERNS` esteso con 26 pattern Watcher's Eye** in `pob/rares.py`: Hatred (cold conv / inc cold / adds cold), Anger (fire), Wrath (lightning), Discipline (ES recharge / onslaught / ES from body), Precision (crit chance / multi), Malevolence (DoT / avoid cold), Determination (armour / phys reduction), Grace (dodge / max ES), Vitality (life leech), Haste (cooldown / atk-cast speed), Pride (phys taken aura), Zealotry (spell crit / faster ailments). Stat ID GGG verificati contro `awakened-poe-trade/data/trade-stats.json`.
- **`_TRADE_PRICED_UNIQUES`** (`{"Watcher's Eye"}`) frozenset in `planner/service.py`. Quando un unique in questo set è in build E TradePort è disponibile, si entra nel path `_price_combo_unique`: `valuable_stat_filters_from_mods` + `TradeQuery(name=name, type="Prismatic Jewel", stats=...)` + percentile median. Risultato stampato `PriceSource.TRADE_API`.
- **Fallback graceful**: se Trade ritorna None (zero listing, currencies sconosciute), il planner cade su poe.ninja `quote_unique_range` per cheapest-variant.
- **4 nuovi test** (Trade dispatch, fallback su Trade None, skip senza TradePort, skip se nessun mod riconosciuto). Anche un Watcher's Eye con mod fittizia non rompe il piano.
- `pyproject.toml` per-file-ignore E501 esteso a `pob/rares.py` (regex Watcher's Eye lunghi).

Baseline: 489 test verdi / 91 mypy / 89 format.

## Step 13.D in corso (target 7 template per classe = 49 totali)

Step 13.D in progress — copertura per classe via BuildTemplate. Target rivisto: **7 template per ogni classe** PoE1 (Marauder / Duelist / Ranger / Witch / Templar / Shadow / Scion) = **49 totali nel registry**. Currently 17 → da aggiungere ~32 template.

Mappa coverage attuale (post-Turno 1):

| Classe | Count | Template registrati |
|---|---|---|
| Marauder | 7/7 ✅ | RF Jugg, Boneshatter, Earthshatter Jugg, Tectonic Slam Chieftain, Molten Strike Chieftain, Ground Slam Jugg, Volcanic Fissure Jugg |
| Duelist | 7/7 ✅ | Cyclone Slayer, Reave Slayer, Lacerate Gladiator, Splitting Steel Gladiator, Sunder Champion, Static Strike Gladiator, Spectral Throw Champion |
| Ranger | 7/7 ✅ | LS Raider, TS Deadeye, FB Raider, TR Pathfinder, Ballista Deadeye, Ice Shot Deadeye, Poisonous Concoction Pathfinder |
| Witch | 7/7 ✅ | Vortex Occ, Bone Spear Necro, DD Necro, Bane Occ, Spectre Necro, Skel Mages, Animate Weapon (1 da swap → Elementalist) |
| Templar | 7/7 ✅ | Spark Inq, HFT Hiero, Penance Brand Inq, Crackling Lance Inq, Arc Hierophant, Smite Guardian, Aurabot Guardian |
| Shadow | 4/7 | Hexblast Mines, Poison BV Assassin, Cobra Lash Assassin, Pyroclast Mines Saboteur |
| Scion | 0/7 | — |

**Turno 1 (Marauder)** ✅ done (2026-05-01). 3 nuovi template + matchers + test signature:
- `BoneshatterTemplate` (matcher "boneshatter") — Jugg/Berserker, trauma stack mechanic, Sunder/Ground Slam levelling → switch a level 28, Heatshiver cold-conv variant.
- `EarthshatterJuggTemplate` (matcher "earthshatter") — slam phys + spike detonation, Tukohama's Coffer, +2 to Slam Skills crafting.
- `TectonicSlamChieftainTemplate` (matcher "tectonic slam") — fire slam consumando EC, Tukohama War's Herald + Ngamahu True Flame, Magnate belt + Kaom's Way ring.

Baseline 492 test verdi / 91 mypy / 89 format.

**Turno 2 (Marauder)** ✅ done (2026-05-01). Marauder coverage 4/7 → 7/7 (chiusa). 3 nuovi template:
- `MoltenStrikeChieftainTemplate` (matcher "molten strike") — phys-to-fire melee strike + projectile, Tukohama War's Herald lab1, Avatar of Fire keystone, Hrimsorrow + Ngamahu's Flame transition.
- `GroundSlamJuggTemplate` (matcher "ground slam") — slam phys signature day-1 Marauder, Resolute Technique, Marohi Erqi 2H → +2 to Slam Skills craft, Ground Slam of Earthshaking transfigured variant.
- `VolcanicFissureJuggTemplate` (matcher "volcanic fissure") — slam fire travelling fissure, Avatar of Fire opzionale, Combustion + Awakened Fire Pen endgame.

NOTA: in Turno 2 swappato il pianificato "Ngamahu Cyclone Chieftain" con `VolcanicFissureJuggTemplate` perché il matcher su `main_skill` non distingue Ngamahu Cyclone (item-keyed) dal generico Cyclone Slayer (skill-keyed) — sarebbe servito un refactor del matcher per guardare anche `key_items`.

Baseline 495 test verdi / 91 mypy / 89 format.

**Turno 3 (Duelist)** ✅ done (2026-05-01). Duelist coverage 1/7 → 4/7. 3 nuovi template:
- `ReaveSlayerTemplate` (matcher "reave") — sword phantom blade stacks AoE, Headsman lab1, Paradoxica/Foil endgame, Vaal Reave per single-target burst.
- `LacerateGladiatorTemplate` (matcher "lacerate") — sword 2H/DW slash + bleed, Painforged + Gratuitous Violence corpse explode, Crimson Dance keystone (DW variant), Lacerate of Haemorrhage transfigured opzionale.
- `SplittingSteelGladiatorTemplate` (matcher "splitting steel") — phys ranged-melee con secondary projectiles, Steel Skills cluster, Painforged (Glad) o Worthy Foe + Inspirational (Champion).

Baseline 498 test verdi / 91 mypy / 89 format.

**Turno 4 (Duelist)** ✅ done (2026-05-01). Duelist coverage 4/7 → 7/7 (chiusa). 3 nuovi template:
- `SunderChampionTemplate` (matcher "sunder") — slam phys signature day-1, Worthy Foe + Inspirational lab1, Marohi Erqi → +2 to Slam Skills 2H mace endgame, Sunder of Earthbreaking transfigured.
- `StaticStrikeGladiatorTemplate` (matcher "static strike") — lightning melee + chained beams, Versatile Combatant (Glad block) o Inspirational (Champion), Saviour shield + Paradoxica/Foil crit weapon.
- `SpectralThrowChampionTemplate` (matcher "spectral throw") — boomerang projectile day-1 Duelist, Worthy Foe + Inspirational, Awakened GMP + Slower Projectiles bossing, Vaal ST burst.

Baseline 501 test verdi / 91 mypy / 89 format.

**Turno 5 (Ranger)** ✅ done (2026-05-01). Ranger coverage 5/7 → 7/7 (chiusa). 2 nuovi template:
- `IceShotDeadeyeTemplate` (matcher "ice shot") — bow phys→cold conversion + cone secondary AoE, Endless Munitions lab1, Lioneye's Glare transition → +1/+2 socketed bow craft o +3 bow + Voltaxic Rift endgame.
- `PoisonousConcoctionPathfinderTemplate` (matcher "poisonous concoction") — flask-thrown chaos hit + poison massiccio, Master Surgeon (sustain) + Nature's Reprisal (poison multi), Mageblood endgame.

Baseline 503 test verdi / 91 mypy / 89 format.

**Turno 6 (Templar)** ✅ done (2026-05-01). Templar coverage 2/7 → 5/7. 3 nuovi template:
- `PenanceBrandInquisitorTemplate` (matcher "penance brand") — brand caster phys/lightning, Inevitable Judgment + Pious Path, Awakened Brand Recall + Awakened Lightning Pen endgame.
- `CracklingLanceInquisitorTemplate` (matcher "crackling lance") — lightning beam multistage, Inevitable Judgment + Augury of Penitence, Replica Conqueror's Efficiency + +1 power charge body.
- `ArcHierophantTemplate` (matcher "arc") — chain lightning day-1 Templar, Conviction of Power + Sanctuary of Thought, Mind Over Matter + Arcane Cloak, Awakened Chain endgame.

NOTA: matcher "arc" è una substring potenzialmente collisiva (matcherebbe "Arctic Breath", "Arctic Armour" se mai apparissero come main_skill). Tollerabile in pratica perché Arctic Armour è una buff aura (mai main_skill DPS) e Arctic Breath è skill morta. Se in futuro serve distinguere, mettere matcher più specifico prima di "arc".

Baseline 506 test verdi / 91 mypy / 89 format.

**Turno 7 (Templar)** ✅ done (2026-05-01). Templar coverage 5/7 → 7/7 (chiusa). 2 nuovi template + nuova sliding-rule matcher:
- `SmiteGuardianTemplate` (matcher "smite") — lightning melee + party aura buff radius, Radiant Crusade lab1, Aegis Aurora shield + Sublime Vision amulet, Time of Need ascendancy.
- `AurabotGuardianTemplate` (matcher CUSTOM `_matches_aurabot`) — support build aura stacking party, Radiant Crusade + Time of Need + Unwavering Crusade, Crown of the Tyrant + Sublime Vision + Awakened Generosity ovunque, Skin of the Lords + Aegis Aurora.
- Nuovo helper `_matches_aurabot(build)` che conta gli aura nei `support_gems` (≥5 → aurabot). Frozenset `_AURA_GEMS` con 19 nomi base. Registrato PRIMA dei matcher skill, perché un Aurabot con throwaway Smite/Spark va comunque a AurabotGuardian.

Pattern di matcher esteso: oltre allo skill-keyed `_matches_skill(*needles)`, ora supportiamo predicate-keyed (es. count auras). Utile per future match item-keyed (CoC Cospri, Mjolner) tramite `key_items` lookup.

Baseline 509 test verdi / 91 mypy / 89 format.

**Turno 8 (Shadow)** ✅ done (2026-05-01). Shadow coverage 1/7 → 4/7. 3 nuovi template:
- `PoisonBladeVortexAssassinTemplate` (matcher "blade vortex") — chaos blade orbit + poison stack, Mistwalker + Noxious Strike + Toxic Delivery, Cospri's Will body + Cold Iron Point dagger.
- `CobraLashAssassinTemplate` (matcher "cobra lash") — chaos projectile chain + poison, Toxic Delivery, Awakened Chain + Awakened Vile Toxins endgame, Vaal Cobra Lash boss.
- `PyroclastMinesSaboteurTemplate` (matcher "pyroclast") — fire AoE mines bossing, Pyromaniac + Bombardier + Demolitions Specialist, Bottled Faith consacrated ground.

NOTA matcher ordering: `_matches_skill("blade vortex")` deve venire **prima** di `_matches_skill("vortex")` perché "vortex" è substring di "blade vortex". Sezione registry "Casters" riordinata di conseguenza.

Baseline 512 test verdi / 91 mypy / 89 format.

Turni successivi pianificati:
- T8-T9 Shadow: Poison BV Assassin, Cobra Lash Assassin, Pyroclast Mines Sab, Cold DoT Trickster, Blade Blast Trickster, Soulrend Trickster *(richiede split del matcher BoneSpearNecro)* (6)
- T10-T12 Scion: CoC Cospri, Power Siphon, Storm Brand, Mjolner, Spectral Helix, Reap, Forbidden Rite (7)
- T13 Witch swap: rimpiazzo di 1 template Necro (probabilmente Animate Weapon) con Ball Lightning Elementalist o equivalente.

## What comes after (Step 13+)
- **Step 13.C — Reverse-progression engine** (final endgame del progetto): derivare custom upgrade ladder dal PoB endgame anziché dai template hardcoded.
- **Faustus flipper** — package `poe1-faustus` per flip di valuta basato su poe.ninja bulk trades. Strumento separato. UX: arbitraggi "X chaos → Y div → Z chaos → profit %".
- **App unica raggruppante** — navbar per tool (FOB, Faustus, …) quando arriva il secondo tool.

## Project-specific gotchas (learned the hard way)

- **poe.ninja post-PoE2 endpoints:** `/poe1/api/economy/stash/{version}/...` for prices, `/poe1/api/builds/{version}/search` (protobuf) for ladder. `league=` param wants the **display name** ("Mirage"), not the URL slug. The old `/api/data/currencyoverview` scheme is dead.
- **pytest conftest collision:** Always `--import-mode=importlib`. The `packages/__init__.py` + `packages/<pkg>/__init__.py` empty files exist specifically to make conftests resolve as `packages.builds.tests.conftest` etc.
- **uv workspace `packages/*` glob** will pick up `packages/__pycache__` once Python compiles the namespace package. `pyproject.toml` excludes it explicitly — don't remove that exclude.
- **Aliased Pydantic fields in JSON responses**: FastAPI serializes by alias by default (`response_model_by_alias=True`). So `path_of_building_export` surfaces as `pathOfBuildingExport` in JSON; `class_name` surfaces as `class`; `defensive_stats` as `defensiveStats`. Tests that assert on the response dict must use the aliased keys.
- **diskcache has no `py.typed`** → mypy override `ignore_missing_imports = true`.
- **Protobuf generated file** at `packages/builds/src/poe1_builds/generated/ninja_builds_pb2.py` is ignored by ruff and mypy. Regenerate with `grpcio-tools` if the upstream schema changes; keep the raw `.proto` source under that dir too.

## How to pick up a new Step

1. Read the latest `docs/architecture.md` if it exists.
2. Run `uv run pytest -q` — if anything's red, fix that first.
3. Create a new `packages/<name>/` following the pricing/builds template: `src/poe1_<name>/{__init__.py, models.py, service.py, sources/*.py, router.py}`, `tests/{conftest.py, fixtures/, test_*.py}`, `pyproject.toml` declaring the package and its deps.
4. Capture real fixtures first, then write models to match them, then write the source adapter, then the service facade, then the router.
5. Close the step by running the full gate and updating this file's "What's built" table.
6. Commit and **push** the worktree branch: `git push origin claude/friendly-kowalevski-9d17f8`. This is mandatory after every step — don't ask, just do it.

## Environment

- `POE_LEAGUE=Mirage` (current league as of 2026-04-24).
- `ANTHROPIC_API_KEY` — only needed when Step 5A (IntentExtractor) lands.
- `POESESSID` — optional, only for authenticated GGG Trade calls.
- `.env.example` at the repo root shows the full list. Never commit `.env`.
