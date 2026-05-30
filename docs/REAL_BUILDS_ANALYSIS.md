# Perché le nostre build sono deboli — e come generarne di REALI

> Analisi richiesta da Riccardo (2026-05-30) dopo aver visto che una build
> da 179k DPS "non serve a un cazzo" rispetto alla top ladder. Giusto.
> Questo documento dice la verità sui numeri, sulla causa, e sulle opzioni.

---

## 0. Prima cosa, la più importante: **NON dobbiamo replicare il motore di PoB**

Lo stiamo **già usando**. `scripts/pob_eval.py` carica `lua51.dll` di PoB via
ctypes e gira il calc reale di PoB headless (Steps 50-52). Ogni numero che
vedi — i nostri 234k e i 13M della ladder — è uscito **dallo stesso identico
motore di PoB**. Il calcolo è esatto al 100%.

Quindi la domanda giusta non è "come replichiamo il calc di PoB" (fatto), ma:

> **perché il nostro generatore/ottimizzatore produce build deboli che PoB
> calcola correttamente come deboli?**

Il problema è la **generazione della build**, non la misura.

---

## 1. I numeri veri (entrambi via PoB-esatto, `scripts/compare_ladder.py`)

Confronto con le top build di **poe.ninja Standard** (il picco assoluto:
gear mirror, item legacy, anni di ricchezza accumulata — il soffitto più alto
possibile).

### Vortex Occultist (confronto diretto, stesso archetipo DoT)
| | Ladder (top) | Nostra | Rapporto |
|---|---|---|---|
| **DPS (DoT)** | **13.086.713** | 234.236 | **siamo al 2%** (56× sotto) |
| TotalEHP | 52.450 | 27.689 | siamo al 53% |
| Vita / ES | 1.741 / 11.703 | 3.263 / 5.382 | — |
| Link principale | Awakened Swift Affliction 5, Empower 4, Efficacy, Awakened Controlled Destruction 5, **Vortex 21/23**, Awakened Elemental Focus 5 | Vortex 20/20 + supporti regolari | — |

### Cyclone Juggernaut (NON è lo stesso archetipo!)
| | Ladder (top) | Nostra | Note |
|---|---|---|---|
| **DPS** | **109.293.778** | 135.622 | la "Cyclone" della ladder ha `FullDPS=0` |
| TotalEHP | 11.347 | 18.228 | **siamo più tanky** (161%) |

**Scoperta cruciale sul Cyclone:** la build "Cyclone" #1 della ladder ha
`FullDPS=0` e link principale `[Enhance, Mark On Hit, Assassin's Mark, More
Duration]`. **Non è un Cyclone-da-mischia: è un Cast-on-Crit** — Cyclone è solo
il *trigger* che lancia incantesimi a ogni colpo critico, e i 109M vengono
dagli spell triggerati. È un **archetipo completamente diverso** dal nostro
Cyclone-Brutality-melee. Noi costruiamo la versione "ingenua" della skill.

---

## 2. Decomposizione del divario (Vortex, 56×)

Misurato a pezzi, partendo dalla nostra build e aggiungendo una leva alla volta:

| Leva | Effetto misurato | Note |
|---|---|---|
| Gemme Awakened (Swift Affliction/Controlled Destruction/Elemental Focus 5) + Vortex 21 | **×1.5** (234k→358k) | misurato live |
| Cold DoT multiplier stacking + Wither + exposure + ailment | **~×37 residuo** | la voragine vera |
| Vita/ES grezza | — (EHP è al 53%, non è quello il dramma) | |

**La gemma-qualità è solo ×1.5. Il 97% del divario è nelle MECCANICHE DI
SCALING che non modelliamo.** Per un Vortex la ladder somma cold DoT
multiplier da: Awakened gem, gioielli cluster (notabili tipo Wicked Pall),
Watcher's Eye, **Wither** (stack che danno +% chaos/DoT taken al nemico),
**exposure** (-res cold), frostbite, Malevolence Awakened, mastery DoT,
ascendancy Occultist. Noi ne mettiamo ~+30%, loro ~+300-400%, e sul DoT è
**moltiplicativo**.

---

## 3. Cause profonde (perché l'ottimizzatore è debole)

Il nostro ottimizzatore (`scripts/optimize_build.py`) è bravo a fare quello
che fa, ma il suo **spazio di ricerca è troppo stretto** e **non modella le
meccaniche ad alto soffitto**:

1. **Niente gemme Awakened oltre 3.** Lo Step 45c blocca tutte le Awakened
   tranne Empower/Enhance/Enlighten ("3.28 le ha rimosse dai drop"). Ma sulla
   **ladder Standard ci sono** (legacy/tradeable) e valgono ×1.5. Restrizione
   troppo aggressiva per le build endgame/mirror.
2. **Niente gioielli cluster.** Large/Medium/Small cluster con notabili
   potentissimi (DoT, danno, difesa) — fonte enorme che saltiamo del tutto.
3. **Niente ottimizzazione di livello/qualità/corruzione gemme** (21/23,
   alt-quality, Vaal). Tutto fisso a 20/20.
4. **Rare a mod-singolo, non combinazioni mirror.** Step 69 ha aggiunto i
   gem-level sul corpo, ma gli altri slot hanno ~5 mod singoli al tier
   migliore, non le combo (DoT multi + %elem + vita + ES + flat + crit) che
   moltiplicano.
5. **Zero modellazione delle meccaniche moltiplicative ad alto soffitto:**
   - **Trigger** (Cast-on-Crit, Cast-when-Channelling, Mjolner) → i 109M del Cyclone.
   - **Wither / exposure / ailment stacking** → il 37× del Vortex.
   - **Totem/mine/ballista, Mageblood (4 flask permanenti), shock/scorch/brittle.**
6. **Costruiamo la versione "ingenua" di ogni skill**, non la versione meta.
   Cyclone per noi = mischia; sulla ladder = trigger CoC.

**Nota sull'EHP:** non è "bassissimo" in assoluto — siamo al 53% sui caster e
al **161%** sul Cyclone (più tanky della ladder, che è glass-cannon a 11k EHP).
Il dramma vero è il **DPS**, non l'EHP. Ma anche l'EHP si chiude con le stesse
leve (cluster difensivi, mod crafted, Aegis/CI scaling).

---

## 4. Il bivio strategico (decisione che spetta a te, Riccardo)

Per generare build **REALI e viable a livello ladder** ci sono tre strade, e
una tocca una **regola architetturale dura** del progetto.

### Path A — Approfondire l'ottimizzatore "da zero" (la visione "pura")
Restando nella regola "Theorycrafter genera da zero", aggiungere allo spazio
di ricerca: gemme Awakened complete, gioielli cluster, livello/qualità/Vaal
gemme, composer rare multi-mod, e **modellare le meccaniche** (Wither,
exposure, ailment, trigger/CoC, totem/mine, flask-stacking).
- **Pro:** rispetta la regola; build inventate davvero.
- **Contro:** è un lavoro **enorme, multi-mese**, e anche così potremmo non
  raggiungere la ladder (il meta usa interazioni profonde). Ogni meccanica è
  un progetto a sé. Realistico arrivare forse al 10-30% della ladder, non al 100%.

### Path B — Seed dalla struttura della ladder (richiede di rilassare la regola)
Usare una top build della ladder per quell'archetipo come **scheletro di
partenza** (i suoi gem link, gli unici chiave, la forma dell'albero, le
meccaniche), e poi far girare **il NOSTRO ottimizzatore PoB** per
rifinire/personalizzare/validare (budget, varianti, gear).
- **Pro:** raggiunge il **livello ladder SUBITO** perché parte da una build
  provata da 13M. È il modo in cui un giocatore reale fa: prende una guida e
  la adatta.
- **Contro:** **viola la regola dura** in `CLAUDE.md` ("Theorycrafter non deve
  MAI usare la ladder come fonte della build; al massimo come segnale di
  popolarità — altrimenti è il Finder"). Diventa "personalizza una build meta"
  invece di "inventa da zero". **Serve una tua decisione esplicita** per
  cambiare cosa È il Theorycrafter.

### Path C — Ibrido (il compromesso onesto)
Da zero per l'**identità** (classe/skill/scheletro), ma usare la ladder come
**template di meccaniche**: rilevare che "il Vortex meta usa Wither + exposure
+ Awakened + questi cluster" e **replicare il PATTERN** (le meccaniche, le
categorie di mod), non la build specifica. Il segnale ladder resta
"popolarità/struttura", non "la build".
- **Pro:** build forti senza copiare una build specifica; resta difendibile
  come "Theorycrafter".
- **Contro:** comunque grande; serve estrarre i pattern meccanici dalla ladder.

---

## 5. Raccomandazione onesta

1. **A breve, indipendentemente dal path**, ci sono win incrementali misurati
   e sicuri (tutti fitness-gated, non regrediscono nulla):
   - Sbloccare le gemme Awakened per l'endgame (**×1.5 misurato** sul Vortex).
   - Aggiungere i gioielli cluster all'ottimizzatore.
   - Ottimizzare livello/qualità/corruzione gemme (21/23, Vaal, alt-quality).
   - Modellare il **Wither + exposure** per le build DoT (la leva più grossa
     sui caster DoT, da sola probabilmente ×3-10).
   - Composer rare multi-mod sugli slot non-unici.
   Questi da soli possono portarci da 2% a forse 15-30% della ladder.

2. **Per il salto vero a livello ladder serve la tua decisione sul bivio.**
   La verità scomoda: una build *inventata da zero* che pareggi una build
   ladder min-maxata da un umano esperto è una frontiera (mesi, forse mai al
   100%). Il modo pragmatico e onesto per dare a te build REALI **oggi** è il
   **Path B** (seed dalla ladder) — ma cambia cosa è il Theorycrafter e va
   contro una regola che tu stesso hai voluto. Solo tu puoi rilassarla.

3. **Chiarimento sull'EHP:** non è il problema principale (siamo 53-161% della
   ladder). Concentriamo gli sforzi sul DPS / sulle meccaniche di scaling.

---

## 6. Prossimo passo concreto (se vuoi che parta subito, senza decidere il bivio)

Posso implementare **subito** i win incrementali del Path A che sono sicuri e
misurati, in quest'ordine di impatto:

1. **Wither + exposure modeling per le build DoT** (probabile la leva singola
   più grossa sui caster — il 37× del Vortex è qui dentro).
2. **Sbloccare Awakened gems endgame** (×1.5 già misurato).
3. **Cluster jewels nell'ottimizzatore.**
4. **Gem corruption/level (21/23, Vaal).**
5. **Composer rare multi-mod.**

Ognuno è un re-run offline del precompute + validazione, fitness-gated.
Mi dici tu se parto da #1 o se prima vuoi decidere il bivio (A/B/C).
