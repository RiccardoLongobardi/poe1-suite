/**
 * PatchNotesPage — the full release history of FOB.
 *
 * A static, data-driven changelog: every release from the first
 * commit to today, newest first. Reached from a low-prominence nav
 * link at the bottom of the navbar. Bilingual (IT / EN).
 */

import { Badge, Box, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconHistory } from "@tabler/icons-react";
import { useT, type Tr } from "../i18n";

interface Release {
  /** Short label shown in the date badge. */
  date: Tr;
  /** Release headline. */
  title: Tr;
  /** Optional one-line summary under the title. */
  summary?: Tr;
  /** Detailed change bullets. */
  entries: Tr[];
}

// Newest first. Compiled from the project's step-by-step history.
//
// IMPORTANT: this array MUST be updated whenever a feature ships —
// always together with CLAUDE.md / CLAUDE_PERPLEXITY_WORKFLOW.md.
// Prepend a new entry with user-facing (not technical) bilingual copy.
const RELEASES: Release[] = [
  {
    date: { it: "29 mag 2026", en: "29 May 2026" },
    title: {
      it: "Theorycrafter — aure multiple oneste (Determination + danno + herald)",
      en: "Theorycrafter — honest multi-aura setups (Determination + damage + herald)",
    },
    summary: {
      it: "Le build ottimizzate ora portano 2-3 aure vere (più Enlighten ed efficienza di riserva), invece di una sola — un grande salto di DPS, e sempre con il mana che basta davvero.",
      en: "The optimised builds now run 2-3 real auras (plus Enlighten and reservation efficiency) instead of just one — a big DPS jump, and always with the mana to actually run them.",
    },
    entries: [
      {
        it: "Prima i build erano 'pieni' di riserva con una sola aura. Ora l'ottimizzatore mette le aure in un unico gruppo con Enlighten e, se serve, prende talenti di efficienza di riserva sull'albero — così entrano onestamente più aure. Ogni combinazione è verificata col calcolo reale di PoB: niente aure che a video non saresti in grado di tenere.",
        en: "Before, builds were 'full' on reservation with a single aura. Now the optimiser puts the auras in one group with Enlighten and, when needed, takes reservation-efficiency notables on the tree — so more auras fit honestly. Every combination is checked with PoB's real calc: no auras you couldn't actually sustain.",
      },
      {
        it: "Risultato misurato: Cyclone 128.500 → 173.300 DPS (+35%), Lacerate → 148.300 (+37%), Vortex → 241.200 (+34%), Arc → 123.600 (+50%), Ice Shot → 51.400 (+18%). Tutte con mana sufficiente e resistenze al massimo.",
        en: "Measured: Cyclone 128,500 → 173,300 DPS (+35%), Lacerate → 148,300 (+37%), Vortex → 241,200 (+34%), Arc → 123,600 (+50%), Ice Shot → 51,400 (+18%). All with enough mana and capped resistances.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — Glorious Vanity (Timeless Jewel a trasformazione)",
      en: "Theorycrafter — Glorious Vanity (transforming Timeless Jewel)",
    },
    summary: {
      it: "L'ottimizzatore ora prova anche Glorious Vanity — il jewel che trasforma i nodi dell'albero e concede keystone potenti (Corrupted Soul, Divine Flesh) — la leva più forte per le build di alto livello.",
      en: "The optimiser now also tries Glorious Vanity — the jewel that transforms tree nodes and grants powerful keystones (Corrupted Soul, Divine Flesh) — the strongest lever for high-end builds.",
    },
    entries: [
      {
        it: "A differenza degli altri Timeless Jewel (che aggiungono statistiche), Glorious Vanity sostituisce i talenti nel raggio con versioni Vaal e dà un keystone a scelta. L'ottimizzatore cerca il seed migliore e lo conferma col calcolo reale di PoB, tenendolo solo se migliora davvero.",
        en: "Unlike the other Timeless Jewels (which add stats), Glorious Vanity replaces in-radius notables with Vaal versions and grants a chosen keystone. The optimiser searches the best seed and confirms it with PoB's real calc, keeping it only if it genuinely helps.",
      },
      {
        it: "Risultato misurato: Arc +20%, Ice Shot +16%, Vortex e Lacerate +~10%, Cyclone ~+8%. Per ogni build viene scelto il tipo di jewel davvero migliore (Glorious Vanity sui melee fisici, altri tipi altrove).",
        en: "Measured: Arc +20%, Ice Shot +16%, Vortex and Lacerate +~10%, Cyclone ~+8%. Each build gets the genuinely best jewel type (Glorious Vanity on physical melee, other types elsewhere).",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — sceglie il miglior tipo di Timeless Jewel",
      en: "Theorycrafter — picks the best Timeless Jewel type",
    },
    summary: {
      it: "L'ottimizzatore ora prova tutti i tipi di Timeless Jewel (Lethal Pride, Brutal Restraint, Militant Faith…) e tiene quello che potenzia di più la build.",
      en: "The optimiser now tries every Timeless Jewel type (Lethal Pride, Brutal Restraint, Militant Faith…) and keeps the one that boosts the build most.",
    },
    entries: [
      {
        it: "Per ogni posizione del jewel cerca il seed migliore di ciascun tipo e li confronta col calcolo reale di PoB. Spesso il migliore non è Lethal Pride: su molte build vince Brutal Restraint.",
        en: "For each jewel spot it searches the best seed of every type and compares them with PoB's real calc. Often the best isn't Lethal Pride: on many builds Brutal Restraint wins.",
      },
      {
        it: "Risultato misurato: Vortex da ~158.000 a ~165.000 DPS, Ice Shot +7%, Arc +3%. Il tipo di jewel scelto è quello davvero migliore per quella build, non uno fisso.",
        en: "Measured: Vortex from ~158,000 to ~165,000 DPS, Ice Shot +7%, Arc +3%. The chosen jewel type is the one that's genuinely best for that build, not a fixed default.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — Timeless Jewel nelle build ottimizzate",
      en: "Theorycrafter — Timeless Jewels in the optimised builds",
    },
    summary: {
      it: "Le build ottimizzate ora montano un Timeless Jewel (Lethal Pride) con il seed migliore trovato cercando nei dati reali di PoB — la leva che avvicina le build endgame a quelle mirror-tier.",
      en: "Optimised builds now equip a Timeless Jewel (Lethal Pride) with the best seed found by searching PoB's real data — the lever that brings endgame builds closer to mirror-tier.",
    },
    entries: [
      {
        it: "Il generatore sceglie la posizione migliore per il jewel (il punto dell'albero il cui raggio copre più talenti utili), poi cerca tra tutti i seed quello che potenzia di più la build, e lo conferma col calcolo reale di PoB. Il jewel viene aggiunto solo se migliora davvero — non può mai peggiorare la build.",
        en: "The generator picks the best spot for the jewel (the tree socket whose radius covers the most useful notables), then searches every seed for the one that boosts the build most, and confirms it with PoB's real calc. The jewel is added only if it genuinely helps — it can never make the build worse.",
      },
      {
        it: "Risultato misurato: Cyclone da ~110.000 a ~120.000 DPS, Vortex a ~158.000, Lacerate ~99.000. Il Timeless Jewel scelto appare tra gli oggetti della build, pronto da importare in PoB.",
        en: "Measured: Cyclone from ~110,000 to ~120,000 DPS, Vortex to ~158,000, Lacerate ~99,000. The chosen Timeless Jewel appears among the build's items, ready to import into PoB.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — gear corretto per le build a danno nel tempo",
      en: "Theorycrafter — correct gear for damage-over-time builds",
    },
    summary: {
      it: "Le build a danno nel tempo (Vortex, Essence Drain, veleno) ora consigliano i moltiplicatori di danno-nel-tempo invece del danno a colpo, che per loro è inutile.",
      en: "Damage-over-time builds (Vortex, Essence Drain, poison) now recommend damage-over-time multipliers instead of flat hit damage, which is useless for them.",
    },
    entries: [
      {
        it: "Prima il gear consigliato spingeva il danno \"a colpo\" anche sulle build che fanno danno nel tempo, dove non serve a niente. Ora arma e amuleto di queste build consigliano il \"Moltiplicatore di Danno nel Tempo\", la statistica che le fa davvero scalare.",
        en: "Previously the recommended gear pushed \"on-hit\" damage even on builds that deal damage over time, where it does nothing. Now the weapon and amulet of those builds recommend \"Damage over Time Multiplier\", the stat that actually scales them.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — build ottimizzate piu resistenti (difese a strati)",
      en: "Theorycrafter — tankier optimised builds (layered defences)",
    },
    summary: {
      it: "L'ottimizzatore ora premia anche la sopravvivenza reale (EHP), non solo il danno: aggiunge layer difensivi quando convengono, sacrificando pochissimo DPS.",
      en: "The optimiser now also rewards real survivability (EHP), not just damage: it adds defensive layers when they pay off, sacrificing very little DPS.",
    },
    entries: [
      {
        it: "Prima le build venivano spinte al massimo DPS restando al minimo della sopravvivenza. Ora l'ottimizzatore preferisce, a parità di danno, le versioni più resistenti — montando scudi con block, Aegis Aurora e nodi difensivi quando alzano davvero l'EHP.",
        en: "Builds used to be pushed to max DPS while sitting at minimum survivability. Now, at equal damage, the optimiser prefers the tankier version — equipping block shields, Aegis Aurora and defensive nodes when they genuinely raise EHP.",
      },
      {
        it: "Risultato misurato col calcolo reale di PoB: Arc da ~21.000 a ~40.000 EHP (+88%) perdendo solo il 3% di danno; Vortex EHP +18%. Le build già robuste (Cyclone, Lacerate) restano invariate. Più vicine a build complete di alto livello.",
        en: "Measured with PoB's real calc: Arc from ~21,000 to ~40,000 EHP (+88%) losing only 3% damage; Vortex EHP +18%. Already-tanky builds (Cyclone, Lacerate) stay unchanged. Closer to complete high-end builds.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — gli oggetti unici nelle build ottimizzate",
      en: "Theorycrafter — unique items in the optimised builds",
    },
    summary: {
      it: "Le build ottimizzate ora montano i veri oggetti unici chiave dell'archetipo, scelti provandoli col calcolo reale di PoB. Danno ed EHP fanno un salto enorme.",
      en: "Optimised builds now equip the real chase unique items for the archetype, chosen by testing them with PoB's real calc. Damage and EHP jump massively.",
    },
    entries: [
      {
        it: "L'ottimizzatore prova gli unici piu rilevanti su ogni slot e tiene quelli che migliorano davvero le statistiche reali. Trova da solo i pezzi giusti — The Bringer of Rain, Starforge, Mark of the Shaper, Galesight — senza liste scritte a mano.",
        en: "The optimiser tries the most relevant uniques in each slot and keeps the ones that actually improve the real stats. It finds the right pieces on its own — The Bringer of Rain, Starforge, Mark of the Shaper, Galesight — with no hand-written lists.",
      },
      {
        it: "Risultato misurato col calcolo reale di PoB: Cyclone da ~22.600 a ~110.000 DPS, Vortex a ~173.000 DPS con EHP da ~6.000 a ~22.900, Lacerate ~92.000, Arc ~68.000. Un grande passo verso build complete di alto livello.",
        en: "Measured with PoB's real calc: Cyclone from ~22,600 to ~110,000 DPS, Vortex to ~173,000 DPS with EHP from ~6,000 to ~22,900, Lacerate ~92,000, Arc ~68,000. A big step toward complete high-end builds.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — niente piu keystone che rompono la build",
      en: "Theorycrafter — no more build-breaking keystones",
    },
    summary: {
      it: "Il generatore non assegna piu automaticamente i keystone: erano la causa di build con 1 sola vita o 0 scudo energetico.",
      en: "The generator no longer auto-assigns keystones: they were the cause of builds with just 1 life or 0 energy shield.",
    },
    entries: [
      {
        it: "I keystone sono scelte estreme che cambiano tutta la build (es. Chaos Inoculation porta la vita a 1, Avatar of Fire converte tutti i danni in fuoco). Venivano scelti a caso per parola chiave, rovinando build a vita o a scudo. Ora non vengono piu assegnati in automatico — le build risultano molto piu solide.",
        en: "Keystones are extreme choices that reshape the whole build (e.g. Chaos Inoculation sets life to 1, Avatar of Fire converts all damage to fire). They were being picked by keyword and wrecking life or ES builds. They're no longer auto-assigned — builds come out far sturdier.",
      },
      {
        it: "Effetto misurato: tre build prima rotte (Frost Blades, Trappola Fulmine, Scheletri) ora hanno vita/scudo corretti, e diverse build hanno anche piu danno (Cyclone e Arc quasi raddoppiati) perche non prendono piu keystone dannosi. Le build ottimizzate con PoB mantengono i keystone buoni (validati dal calcolo reale).",
        en: "Measured effect: three previously-broken builds (Frost Blades, Lightning Trap, Skeletons) now have correct life/shield, and several builds also gained damage (Cyclone and Arc nearly doubled) by no longer taking harmful keystones. PoB-optimised builds keep the good keystones (validated by the real calc).",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — build ottimizzate con numeri reali di PoB",
      en: "Theorycrafter — builds optimised with real PoB numbers",
    },
    summary: {
      it: "Per gli archetipi piu popolari il Theorycrafter ora serve una versione ottimizzata col motore di calcolo reale di Path of Building, con DPS ed EHP veri (non piu stime).",
      en: "For the most popular archetypes the Theorycrafter now serves a version optimised with Path of Building's real calc engine, with true DPS and EHP (no longer estimates).",
    },
    entries: [
      {
        it: "Dietro le quinte un ottimizzatore prova migliaia di varianti (supporti, arma, albero) misurandole col calcolo esatto di PoB e tiene la migliore che mantiene resistenze e vita/ES validi. Il risultato e una build con statistiche reali, segnalata dal badge verde \"Ottimizzato con PoB\".",
        en: "Behind the scenes an optimiser tries thousands of variants (supports, weapon, tree), scoring each with PoB's exact calc, and keeps the best one that still has capped resistances and a viable life/ES pool. The result is a build with real stats, marked by the green \"PoB-optimised\" badge.",
      },
      {
        it: "Esempi misurati: Cyclone ~22.600 DPS, Vortex ~124.700 DPS, Lacerate ~26.300, Arc ~26.800, Ice Shot ~10.800 — tutte con resistenze al cap. Gli altri archetipi continuano a essere generati al volo come prima.",
        en: "Measured examples: Cyclone ~22,600 DPS, Vortex ~124,700 DPS, Lacerate ~26,300, Arc ~26,800, Ice Shot ~10,800 — all with capped resistances. Other archetypes are still generated on the fly as before.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — build da minion con danno reale",
      en: "Theorycrafter — minion builds with real damage",
    },
    summary: {
      it: "Le build da evocazione ora ricevono i supporti e i nodi giusti per far danno davvero coi minion.",
      en: "Summoner builds now get the right supports and passives so the minions actually deal damage.",
    },
    entries: [
      {
        it: "Prima le gemme di evocazione (Summon Skeletons, Raise Spectre) prendevano supporti da incantatore (Spell Echo, Concentrated Effect) che non potenziano i minion, e l'albero non allocava nessun nodo da minion. Ora usano i supporti da minion (Minion Damage, Feeding Frenzy, ecc.) e l'albero prende i talenti dei minion: su una build di prova il danno e passato da ~500 a ~4300.",
        en: "Summon gems (Summon Skeletons, Raise Spectre) used to get caster supports (Spell Echo, Concentrated Effect) that don't buff minions, and the tree allocated no minion passives. They now use minion supports (Minion Damage, Feeding Frenzy, etc.) and the tree picks minion notables: on a test build the damage went from ~500 to ~4,300.",
      },
      {
        it: "Nota su Raise Spectre: lo spettro va scelto a mano in PoB (il generatore non puo sceglierlo per te), quindi appare un avviso che ti ricorda questo unico passaggio — fatto quello, il danno viene calcolato.",
        en: "Note on Raise Spectre: the spectre must be picked by hand in PoB (the generator can't choose it for you), so a notice now reminds you of this single step — once done, the damage is calculated.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — build a Scudo Energetico piu robuste",
      en: "Theorycrafter — sturdier Energy Shield builds",
    },
    summary: {
      it: "Le build a Scudo Energetico ora hanno un pool molto piu alto e tutte le resistenze al cap.",
      en: "Energy Shield builds now have a much higher pool and all resistances capped.",
    },
    entries: [
      {
        it: "Le build ES sceglievano basi sbagliate su cui lo scudo energetico non poteva comparire, quindi elmo, guanti e stivali restavano senza ES e il totale era basso (~3000). Ora usano basi ES pure e lo scudo compare su tutti i pezzi: il pool sale di circa il 50%.",
        en: "ES builds were picking the wrong bases — ones where energy shield can't roll — so helmet, gloves and boots had no ES and the total stayed low (~3,000). They now use pure ES bases and shield shows on every piece: the pool rises by about 50%.",
      },
      {
        it: "Le resistenze sono distribuite meglio sugli oggetti: prima la resistenza al fulmine compariva su un solo slot e restava sotto il cap; ora tutte e tre le resistenze elementali arrivano al massimo.",
        en: "Resistances are spread better across items: lightning resistance used to appear on a single slot and stayed under the cap; now all three elemental resistances reach the maximum.",
      },
    ],
  },
  {
    date: { it: "25 mag 2026", en: "25 May 2026" },
    title: {
      it: "Theorycrafter — attacchi elementali corretti",
      en: "Theorycrafter — elemental attacks fixed",
    },
    summary: {
      it: "Le build con attacchi elementali (Lightning Strike, Molten Strike, Frost Blades, Ice Shot) ora ricevono l'arma giusta e le statistiche da attacco corrette.",
      en: "Elemental attack builds (Lightning Strike, Molten Strike, Frost Blades, Ice Shot) now get the right weapon and proper attack stats.",
    },
    entries: [
      {
        it: "Prima questi attacchi venivano scambiati per incantesimi (perche infliggono danno elementale): ricevevano stat da caster e l'arma sbagliata. Ora vengono riconosciuti come attacchi e consigliano velocita d'attacco + \"Aggiunge danno <elemento>\" sull'arma.",
        en: "These attacks used to be mistaken for spells (because they deal elemental damage): they got caster stats and the wrong weapon. They're now recognised as attacks and recommend attack speed + \"Adds <element> Damage\" on the weapon.",
      },
      {
        it: "Ice Shot ora prende correttamente un Arco invece di una bacchetta; le build melee elementali tengono l'arma da mischia. Verificato col motore di calcolo reale di PoB: tutte le build con attacchi elementali ora hanno DPS reale e nessuna statistica da incantesimo fuori posto.",
        en: "Ice Shot now correctly gets a Bow instead of a wand; elemental melee builds keep their melee weapon. Verified against PoB's real calc engine: every elemental-attack build now has real DPS and no misplaced spell stats.",
      },
    ],
  },
  {
    date: { it: "24 mag 2026", en: "24 May 2026" },
    title: {
      it: "Theorycrafter — danno reale sugli oggetti (DPS molto piu alto)",
      en: "Theorycrafter — real weapon damage (much higher DPS)",
    },
    summary: {
      it: "Gli oggetti generati ora includono il danno aggiunto piatto — la fonte di DPS numero uno — quindi le build hanno un danno realistico.",
      en: "Generated items now include flat added damage — the #1 DPS source — so builds have realistic damage.",
    },
    entries: [
      {
        it: "Le armi ora consigliano \"Aggiunge X-Y danno\" (fisico per gli attacchi, elementale agli incantesimi per i caster); anelli, amuleto e guanti aggiungono danno agli attacchi. Su una build di prova il DPS e piu che raddoppiato.",
        en: "Weapons now recommend \"Adds X-Y Damage\" (physical for attacks, elemental-to-spells for casters); rings, amulet and gloves add attack damage. On a test build the DPS more than doubled.",
      },
      {
        it: "Verificato col motore di calcolo reale di PoB: i valori dei mod sono tier reali che possono davvero comparire su quello slot.",
        en: "Verified against PoB's real calc engine: the mod values are real tiers that can actually roll on that slot.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — albero ottimizzato (valore per punto)",
      en: "Theorycrafter — value-per-point tree optimisation",
    },
    summary: {
      it: "L'albero ora spende i punti dove rendono di piu, invece di riempire con nodi di poco conto.",
      en: "The tree now spends points where they pay off most, instead of filling with low-value nodes.",
    },
    entries: [
      {
        it: "Nuova allocazione \"valore per punto\": prende i notable piu utili tenendo conto di quanti punti costa raggiungerli — quindi piu notable significativi e meno nodi di passaggio inutili.",
        en: "New \"value-per-point\" allocation: it picks the most useful notables weighing how many points it costs to reach them — so more meaningful notables and fewer filler travel nodes.",
      },
      {
        it: "Le resistenze e la sopravvivenza ora contano nella scelta: preferisce un notable \"+2% a tutte le res massime\" (1 punto) invece di due nodi di resistenza singola (2 punti).",
        en: "Resistances and survivability now count in the choice: it prefers a \"+2% to all max resistances\" notable (1 point) over two single-resistance nodes (2 points).",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — maestrie e albero piu pulito",
      en: "Theorycrafter — masteries and a cleaner tree",
    },
    summary: {
      it: "L'albero ora alloca le maestrie giuste, evita nodi inutili e i pannelli mostrano numeri realistici.",
      en: "The tree now allocates the right masteries, avoids wasted nodes, and the panels show realistic numbers.",
    },
    entries: [
      {
        it: "Le maestrie (Vita, Resistenze, danno) vengono allocate con l'effetto piu adatto alla build.",
        en: "Masteries (Life, Resistances, damage) are now allocated with the effect that best fits the build.",
      },
      {
        it: "Niente piu nodi per armi che non usi (es. \"danno con le asce\" su una build con spada).",
        en: "No more nodes for weapons you don't use (e.g. \"damage with axes\" on a sword build).",
      },
      {
        it: "Le carte degli oggetti mostrano solo i modificatori che possono davvero comparire su quello slot (niente danno da incantesimo sull'elmo).",
        en: "Item cards only show modifiers that can actually appear on that slot (no spell damage on a helmet).",
      },
      {
        it: "La stima della Vita ora e realistica (~5k invece di ~13k); il DPS non viene piu mostrato con un numero fuorviante — importa in PoB per il calcolo preciso.",
        en: "The Life estimate is now realistic (~5k instead of ~13k); DPS is no longer shown as a misleading number — import into PoB for the precise math.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — modificatori reali sugli oggetti",
      en: "Theorycrafter — real item modifiers",
    },
    summary: {
      it: "Gli oggetti generati ora mostrano modificatori veri di PoE con i valori dei tier reali, non piu numeri inventati.",
      en: "Generated items now show real PoE modifiers with real tier values, no more invented numbers.",
    },
    entries: [
      {
        it: "Ogni affisso viene dal pool reale di PoE (dati RePoE): es. +189 alla Vita massima e il tier piu alto vero per quel pezzo, non un valore di fantasia.",
        en: "Every affix comes from PoE's real mod pool (RePoE data): e.g. +189 to maximum Life is the real top tier for that piece, not a made-up value.",
      },
      {
        it: "Vengono mostrati solo i modificatori che possono davvero comparire su quello slot: niente piu danno da incantesimo su un elmo o multi critico sui guanti.",
        en: "Only modifiers that can actually appear on that slot are shown: no more spell damage on a helmet or crit multiplier on gloves.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — albero passivo piu realistico",
      en: "Theorycrafter — more realistic passive tree",
    },
    summary: {
      it: "L'albero generato resta un blocco compatto vicino al punto di partenza della classe, invece di allungarsi a caso dall'altra parte dell'albero.",
      en: "The generated tree stays a compact cluster near the class start instead of sprawling across to the far side.",
    },
    entries: [
      {
        it: "La scelta dei nodi ora pesa la distanza dal punto di partenza: niente piu tentacoli verso nodi lontani (es. una build Marauder che pescava nell'area Ranger).",
        en: "Node selection now weighs distance from the class start: no more tendrils toward far-off nodes (e.g. a Marauder build reaching into the Ranger area).",
      },
      {
        it: "Nessun nodo di maestria, cluster jewel o ascendancy finisce piu per sbaglio nel percorso dell'albero principale.",
        en: "No mastery, cluster-jewel or ascendancy node ends up on the main tree path by mistake.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — gemme corrette e sensate",
      en: "Theorycrafter — correct, sensible gem links",
    },
    summary: {
      it: "I supporti generati ora sono compatibili con la skill e adatti al tipo di danno; le gemme Awakened hanno il livello giusto.",
      en: "Generated supports are now compatible with the skill and matched to its damage type; Awakened gems use the right level.",
    },
    entries: [
      {
        it: "Niente piu supporti che non funzionano (es. Advanced Traps o Ancestral Call su Cyclone): ogni supporto rispetta i requisiti reali della gemma di PoE.",
        en: "No more supports that don't work (e.g. Advanced Traps or Ancestral Call on Cyclone): every support respects PoE's real gem requirements.",
      },
      {
        it: "I supporti che bloccano il tipo di danno (Brutalita, Penetrazione Fuoco/Gelo/Fulmine, ecc.) ora compaiono solo sulle build giuste, e i link mostrano i supporti meta piu usati.",
        en: "Damage-locking supports (Brutality, Fire/Cold/Lightning Penetration, etc.) now appear only on the right builds, and links surface the most-used meta supports.",
      },
      {
        it: "Le gemme Awakened Empower/Enhance/Enlighten usano il livello massimo corretto (5, non 20).",
        en: "Awakened Empower/Enhance/Enlighten now use the correct max level (5, not 20).",
      },
      {
        it: "I notable di ascendancy non finiscono piu come punti scollegati nell'albero passivo importato.",
        en: "Ascendancy notables no longer end up as disconnected points in the imported passive tree.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Input piu diretti su Finder, Analyze e Planner",
      en: "More direct inputs on Finder, Analyze and Planner",
    },
    summary: {
      it: "Meno click: la ricerca parte subito e il testo resta sempre modificabile.",
      en: "Fewer clicks: search runs in one go and the input stays editable.",
    },
    entries: [
      {
        it: "Nel Build Finder, inviare la richiesta cerca subito le build — non serve piu un secondo click su \"Trova build\".",
        en: "In the Build Finder, submitting your query searches builds right away — no more second click on \"Find builds\".",
      },
      {
        it: "In Finder, Analyze e Planner il campo di testo resta sempre modificabile: niente piu pulsante \"modifica\" per cambiare la richiesta.",
        en: "In Finder, Analyze and Planner the text field stays editable: no more \"edit\" button to change your input.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — affissi per slot realistici",
      en: "Theorycrafter — realistic per-slot affixes",
    },
    summary: {
      it: "Ogni pezzo di equipaggiamento generato mostra ora gli affissi giusti per la build, in ordine di priorita.",
      en: "Every generated gear piece now shows the right affixes for the build, in priority order.",
    },
    entries: [
      {
        it: "Guanti e stivali ricevono velocita di lancio o di attacco a seconda della build; anelli vita/ES + mana + attributi; amuleto danno + multi critico; cintura recupero delle flask; arma con gli affissi giusti per tipo di danno.",
        en: "Gloves and boots get cast or attack speed depending on the build; rings get life/ES + mana + attributes; amulet gets damage + crit multiplier; belt gets flask recovery; the weapon gets the right affixes for its damage type.",
      },
      {
        it: "Le flask generate sono ora veri oggetti magici con un suffisso reale (es. \"di Cauterizzazione\", \"di Adrenalina\") invece di basi bianche.",
        en: "Generated flasks are now real magic items with a real suffix (e.g. \"of Staunching\", \"of Adrenaline\") instead of blank white bases.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — gemme Awakened aggiornate a 3.28",
      en: "Theorycrafter — Awakened gems matched to 3.28",
    },
    summary: {
      it: "Il generatore non propone piu gemme Awakened che in 3.28 non si possono piu ottenere.",
      en: "The generator no longer suggests Awakened gems that can no longer be obtained in 3.28.",
    },
    entries: [
      {
        it: "In 3.28 sono rimaste droppabili solo Awakened Empower, Enlighten ed Enhance: ora i link generati usano solo queste tre tra le Awakened, le altre tornano alle versioni normali.",
        en: "In 3.28 only Awakened Empower, Enlighten and Enhance still drop: generated links now use only those three among the Awakened ones, the rest fall back to their normal versions.",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — gemme piu sensate",
      en: "Theorycrafter — smarter gem links",
    },
    summary: {
      it: "I gruppi di gemme generati non ripetono piu la skill principale e usano solo supporti compatibili.",
      en: "Generated gem groups no longer repeat the main skill and only use compatible supports.",
    },
    entries: [
      {
        it: "Lo slot elmo ospita ora una seconda skill diversa (movimento o utilita) invece di duplicare la skill del corpo.",
        en: "The helmet slot now hosts a distinct secondary skill (movement or utility) instead of duplicating the body-armour skill.",
      },
      {
        it: "Ogni supporto e verificato contro la skill del suo gruppo: niente piu accoppiamenti senza senso (es. velocita di lancio su una skill da attacco).",
        en: "Every support is checked against its group's skill: no more nonsensical pairings (e.g. cast speed on an attack skill).",
      },
    ],
  },
  {
    date: { it: "22 mag 2026", en: "22 May 2026" },
    title: {
      it: "Theorycrafter — albero passivo completo",
      en: "Theorycrafter — full passive tree",
    },
    summary: {
      it: "Il generatore alloca ora un albero di dimensione realistica (~120 nodi) invece dei pochi nodi del solo percorso.",
      en: "The generator now allocates a realistic-sized tree (~120 nodes) instead of just the few path nodes.",
    },
    entries: [
      {
        it: "Dopo aver collegato i notable e i keystone piu rilevanti, l'albero si espande verso i nodi vicini piu utili (vita, difese, danno) fino a raggiungere un budget di passive credibile per una build di mappatura.",
        en: "After connecting the most relevant notables and keystones, the tree expands into the most useful nearby nodes (life, defences, damage) until it reaches a credible passive budget for a mapping build.",
      },
      {
        it: "L'allocazione resta un unico blocco connesso: ogni nodo aggiunto e adiacente a uno gia preso, quindi la build importata in PoB non ha punti orfani.",
        en: "The allocation stays a single connected block: every added node is adjacent to an already-taken one, so the build imported into PoB has no orphan points.",
      },
    ],
  },
  {
    date: { it: "20 mag 2026", en: "20 May 2026" },
    title: {
      it: "Barra laterale a comparsa",
      en: "Slide-in sidebar",
    },
    summary: {
      it: "La barra di navigazione si apre solo quando ti serve, lasciando piu spazio ai contenuti.",
      en: "The navigation rail slides in only when you need it, leaving more room for content.",
    },
    entries: [
      {
        it: "Clicca l'icona hamburger in alto a sinistra per aprire le voci di navigazione; cliccarne una porta alla pagina e richiude la barra.",
        en: "Click the hamburger icon at top-left to open the navigation; clicking an entry takes you there and closes the rail.",
      },
      {
        it: "Sezione \"Strumenti\" per le pagine principali; in fondo: Supporta il progetto + Note di rilascio.",
        en: "\"Tools\" section for the main pages; at the bottom: Support the project + Patch notes.",
      },
    ],
  },
  {
    date: { it: "20 mag 2026", en: "20 May 2026" },
    title: {
      it: "Theorycrafter — albero passivo connesso",
      en: "Theorycrafter — connected passive tree",
    },
    summary: {
      it: "Il generatore costruisce ora un percorso reale sull'albero invece di far galleggiare nodi disconnessi.",
      en: "The generator now builds a real path on the passive tree instead of floating disconnected nodes.",
    },
    entries: [
      {
        it: "I nodi dell'albero sono collegati con un BFS dal punto di partenza della classe attraverso i notable piu rilevanti — le build importate in PoB mostrano un'allocazione contigua.",
        en: "Tree nodes are connected with a BFS from the class start through the most relevant notables — builds imported into PoB now show a contiguous allocation.",
      },
      {
        it: "I nodi di passaggio (necessari solo per collegare il percorso) non occupano spazio nella lista visibile; un piccolo testo sotto riassume il totale e quanti sono i nodi di percorso.",
        en: "Path nodes (only needed to connect the route) no longer clutter the visible list; a small caption summarises the total and how many are path-only.",
      },
    ],
  },
  {
    date: { it: "20 mag 2026", en: "20 May 2026" },
    title: {
      it: "Theorycrafter — rapporto di viabilità",
      en: "Theorycrafter — viability report",
    },
    summary: {
      it: "Ogni build generata mostra ora avvisi e errori strutturali per evitare scheletri non viable.",
      en: "Every generated build now surfaces structural warnings and errors so you don't ship a non-viable skeleton.",
    },
    entries: [
      {
        it: "Controlli: resistenze (sempre via equipaggiamento), vita/ES sotto soglia per budget, almeno 2 layer difensivi, presenza di una skill di movimento, mana sustain.",
        en: "Checks: resistances (always gear-side), life/ES below the budget floor, ≥2 defence layers, a movement skill, and mana sustain.",
      },
      {
        it: "Gli errori bloccanti sono rossi, gli avvisi gialli, il via libera verde — con messaggi bilingui.",
        en: "Blocking errors show red, warnings yellow, all-clear green — with bilingual messages.",
      },
    ],
  },
  {
    date: { it: "20 mag 2026", en: "20 May 2026" },
    title: {
      it: "Theorycrafter — carte oggetto espandibili",
      en: "Theorycrafter — expandable gear cards",
    },
    summary: {
      it: "Le carte oggetto mostrano gli affissi stimati al click e aprono direttamente la ricerca su Trade.",
      en: "Gear cards now reveal their estimated affixes on click and open a Trade search directly.",
    },
    entries: [
      {
        it: "Clicca una carta di equipaggiamento per espandere l'elenco degli affissi stimati — con il simbolo ~ a indicare i valori teorici.",
        en: "Click a gear card to expand its estimated affix list — the ~ symbol marks the theoretical values.",
      },
      {
        it: "Ogni carta ha un'icona Trade che apre il dialogo di ricerca pre-compilato col base type giusto e i mod come hint.",
        en: "Every card carries a Trade icon that opens the pre-filled search dialog with the right base type and stat priorities as hints.",
      },
      {
        it: "Layout a due colonne sul desktop: gemme + albero a sinistra, equipaggiamento a destra.",
        en: "Two-column layout on desktop: gems + tree on the left, gear on the right.",
      },
    ],
  },
  {
    date: { it: "20 mag 2026", en: "20 May 2026" },
    title: {
      it: "Theorycrafter — PoB completo e funzionante",
      en: "Theorycrafter — complete, working PoB export",
    },
    summary: {
      it: "Cinque bug strutturali risolti: l'albero ora si alloca correttamente, le gemme coprono 5 slot, gli oggetti hanno affissi visibili, le fiale e i jewel sono inclusi.",
      en: "Five structural bugs fixed: the tree now allocates correctly, gems cover all 5 slots, items show real stats, flasks and jewels are included.",
    },
    entries: [
      {
        it: "L'albero passivo viene scoperto con scoring sui veri testi-mod dei nodi (prima usava solo il nome), e il nodo di partenza ora corrisponde alla classe scelta.",
        en: "Passive tree nodes are now scored on their real mod text (the name-only scorer missed most relevant notables), and the class start node finally matches the picked class.",
      },
      {
        it: "Il codice PoB include 5 gruppi gemme: 6L primario nel petto, 4L secondario nell'elmo, 4L aura+supporti nei guanti, 4L movimento negli stivali, 4L grido d'azione nell'arma.",
        en: "The PoB code now includes 5 gem groups: primary 6L in the chest, secondary 4L in the helmet, aura+supports 4L in gloves, movement 4L in boots, warcry 4L in the weapon.",
      },
      {
        it: "Gli oggetti consigliati ora portano affissi simulati realistici (vita, resistenze, danno) scalati per fascia di budget — invece di essere oggetti bianchi vuoti.",
        en: "Recommended items now ship realistic simulated affixes (life, resistances, damage) scaled by budget tier — instead of being empty white items.",
      },
      {
        it: "Cinque slot di fiale (vita o mana, mobilità, difesa, utility, resistenza) e due jewel scelti in base alla difesa e al tipo di danno.",
        en: "Five flask slots (life/mana, mobility, defence, utility, resistance) and two jewels picked by defence type and damage profile.",
      },
    ],
  },
  {
    date: { it: "20 mag 2026", en: "20 May 2026" },
    title: {
      it: "Theorycrafter v2 — form e PoB importabile",
      en: "Theorycrafter v2 — form-driven with PoB export",
    },
    summary: {
      it: "Generatore di build completamente riprogettato: form a cascata, PoB code completo e link Trade per ogni slot.",
      en: "Completely redesigned build generator: cascading form, full PoB code, Trade links per slot.",
    },
    entries: [
      {
        it: "Niente piu testo libero: scegli Classe -> Ascendancy -> Skill -> Danno -> Difesa -> Budget -> Focus. Le opzioni a valle si filtrano automaticamente.",
        en: "No more free text: pick Class -> Ascendancy -> Skill -> Damage -> Defence -> Budget -> Focus. Downstream options filter automatically.",
      },
      {
        it: "Ogni build generata ora include un codice PoB completo: copialo e incollalo nel pulsante \"Import\" di Path of Building.",
        en: "Every generated build now ships a complete PoB code: copy it and paste into Path of Building's \"Import\" button.",
      },
      {
        it: "Ogni slot di equipaggiamento ha un'icona Trade che apre la ricerca su pathofexile.com con il base type giusto.",
        en: "Every gear slot has a Trade icon that opens a pathofexile.com search with the correct base type.",
      },
      {
        it: "Albero passivo: vengono indicati i veri node id dei keystone e degli ascendancy notable, presi dai dati ufficiali 3.28.",
        en: "Passive tree: real keystone and ascendancy-notable node IDs are surfaced, sourced from the official 3.28 data.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: {
      it: "Theorycrafter — Genera build",
      en: "Theorycrafter — Build Generator",
    },
    entries: [
      {
        it: "Descrivi in italiano la build che vuoi giocare e ricevi uno scheletro completo con skill setup, pietre passive e slot oggetti.",
        en: "Describe your build idea in natural language and get a complete skeleton with skill setup, passive milestones, and gear slots.",
      },
      {
        it: "Lo scheletro e generato da zero con i dati ufficiali di PoE 3.28 (albero, gemme, basi oggetto) — non e copiato dalla classifica dei giocatori.",
        en: "The skeleton is generated from scratch with official PoE 3.28 data (tree, gems, item bases) — not copied from the player ladder.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: {
      it: "Theorycrafter ridefinito",
      en: "Theorycrafter redefined",
    },
    entries: [
      {
        it: "Theorycrafter costruirà build da zero usando i dati ufficiali di PoE 3.28 (albero, gemme, basi oggetto), senza attingere dalla classifica dei giocatori — trovare build reali resta il compito del Build Finder. La prima versione confondeva i due ruoli ed è stata rimossa; il vero generatore arriverà in un prossimo aggiornamento.",
        en: "Theorycrafter will build from scratch using official PoE 3.28 data (tree, gems, item bases), not the player ladder — finding real builds stays the Build Finder's job. The first version blurred the two roles and was removed; the real generator is coming in a future update.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: {
      it: "Theorycrafter in arrivo",
      en: "Theorycrafter on the way",
    },
    summary: {
      it: "Un nuovo strumento per progettare build da zero — analisi e progettazione completate.",
      en: "A new tool to design builds from scratch — analysis and design complete.",
    },
    entries: [
      {
        it: "Theorycrafter sarà una nuova sezione per costruire una build da zero: generatore di build, esploratore di oggetti e modificatori, strategia atlas e generatore di loot filter.",
        en: "Theorycrafter will be a new section to build a character from scratch: build generator, item & modifier browser, atlas strategy, and a loot-filter generator.",
      },
      {
        it: "Questa release completa la fase di analisi e progettazione; lo sviluppo arriverà nei prossimi aggiornamenti.",
        en: "This release completes the analysis and design phase; development lands in upcoming updates.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: {
      it: "Filtro skill del Finder più fluido",
      en: "Smoother Finder skill filter",
    },
    entries: [
      {
        it: "Nel Build Finder, filtrando i risultati per skill la lista ora si aggiorna con una breve dissolvenza invece di scattare.",
        en: "In the Build Finder, filtering results by skill now updates the list with a short cross-fade instead of jumping.",
      },
      {
        it: "L'animazione rispetta l'impostazione \"riduci movimento\" del sistema.",
        en: "The animation respects the system's \"reduce motion\" setting.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: { it: "Dettagli oggetto al passaggio + logo animato", en: "Hover item details + animated logo" },
    entries: [
      {
        it: "Nella pagina Analizza, passa il mouse su un pezzo di equipaggiamento per vederne i dettagli; cliccalo per fissare il riquadro e tenerlo aperto.",
        en: "On the Analyse page, hover a gear piece to see its details; click it to pin the panel so it stays open.",
      },
      {
        it: "Il logo FOB nell'header ora pulsa con un bagliore ember.",
        en: "The FOB logo in the header now pulses with an ember glow.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: {
      it: "Fix Trade: mod impliciti corrotti",
      en: "Trade fix: corrupted implicit mods",
    },
    entries: [
      {
        it: "I modificatori impliciti (inclusi quelli da corruzione) ora vengono cercati correttamente su Trade — prima venivano trattati come modificatori normali e la ricerca falliva.",
        en: "Implicit mods (including corrupted ones) are now searched correctly on Trade — they were treated as normal mods before and the search failed.",
      },
      {
        it: "Le transizioni tra le pagine sono ora più fluide (dissolvenza leggera).",
        en: "Page transitions are now smoother (a light fade).",
      },
      {
        it: "I valori minimi dei filtri Trade sono ora arrotondati a numeri interi.",
        en: "Trade filter minimum values are now rounded to whole numbers.",
      },
    ],
  },
  {
    date: { it: "19 mag 2026", en: "19 May 2026" },
    title: { it: "Navigazione fluida", en: "Fluid navigation" },
    summary: {
      it: "Transizioni animate tra le pagine, prezzi sugli oggetti, scorciatoie da tastiera e notifiche ridisegnate.",
      en: "Animated page transitions, prices on items, keyboard shortcuts and redesigned notifications.",
    },
    entries: [
      {
        it: "Le pagine ora si dissolvono dolcemente l'una nell'altra invece di scattare.",
        en: "Pages now cross-fade smoothly into each other instead of cutting.",
      },
      {
        it: "Badge prezzo poe.ninja direttamente sugli oggetti unici, in Analizza e nel Planner.",
        en: "poe.ninja price badge directly on unique items, in Analyse and the Planner.",
      },
      {
        it: "Scorciatoie da tastiera: premi ? per vederle (G+F/A/P/N per navigare, T tema, L lingua).",
        en: "Keyboard shortcuts: press ? to see them (G+F/A/P/N to navigate, T theme, L language).",
      },
      {
        it: "Notifiche ridisegnate nel tema Void Stone & Ember.",
        en: "Notifications restyled in the Void Stone & Ember theme.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Fix ricerca Trade per gli unique",
      en: "Trade search fix for uniques",
    },
    entries: [
      {
        it: "La ricerca per nome degli oggetti unique ora funziona: nome e tipo base vengono inviati insieme a pathofexile.com/trade.",
        en: "Searching uniques by name now works: the name and base type are sent together to pathofexile.com/trade.",
      },
      {
        it: "Le ricerche Trade si aprono di default con il filtro \"Instant Buyout\".",
        en: 'Trade searches now open with the "Instant Buyout" filter by default.',
      },
      {
        it: "Più mod sono ricercabili: i modificatori con un numero (come quello principale della Mageblood) ora vengono riconosciuti.",
        en: "More mods are searchable: count modifiers (like Mageblood's signature mod) are now recognised.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: { it: "Interfaccia viva", en: "Living interface" },
    summary: {
      it: "Il sito ora respira: particelle, shimmer, numeri animati e caricamenti raffinati.",
      en: "The site now breathes: particles, shimmer, animated numbers and refined loaders.",
    },
    entries: [
      {
        it: "Sfondo animato con particelle ember che reagiscono al movimento del mouse.",
        en: "Animated ember particle background that reacts to mouse movement.",
      },
      {
        it: "Gli oggetti si illuminano al passaggio del mouse con un bagliore nel colore della loro rarità (blu magico, giallo raro, arancio unique).",
        en: "Items light up on hover with a glow in their rarity colour (magic blue, rare yellow, unique orange).",
      },
      {
        it: "Le statistiche chiave (Vita, DPS, EHP…) si animano contando da zero all'apertura.",
        en: "Key stats (Life, DPS, EHP…) count up from zero on load.",
      },
      {
        it: "Skeleton loader in stile ember durante il caricamento dei risultati.",
        en: "Ember-style skeleton loaders while results are loading.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Pannello Trade: tutte le mod dell'oggetto",
      en: "Trade panel: all of the item's mods",
    },
    entries: [
      {
        it: "Il pannello di ricerca Trade ora è più grande e mostra tutte le mod dell'oggetto, non solo quelle più comuni.",
        en: "The Trade search panel is now bigger and shows every mod of the item, not just the common ones.",
      },
      {
        it: "Ogni mod riconosciuta è attivabile come filtro: il riconoscimento usa l'intero database delle stat di pathofexile.com (~9500 voci).",
        en: "Every recognised mod can be toggled as a filter: recognition uses the full pathofexile.com stat database (~9,500 entries).",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Pannello ricerca Trade stile poe.ninja",
      en: "poe.ninja-style Trade search panel",
    },
    summary: {
      it: "Cliccando l'icona Trade ora si apre un pannello configurabile.",
      en: "Clicking the Trade icon now opens a configurable panel.",
    },
    entries: [
      {
        it: "Scegli se cercare per nome (unique) o tipo base, e imposta il filtro link (5L / 6L).",
        en: "Choose to search by unique name or base type, and set the link filter (5L / 6L).",
      },
      {
        it: "Ogni mod dell'item ha un interruttore e uno slider di tolleranza (50-100%): decidi quali mod includere e quanto stretti.",
        en: "Each item mod has a toggle and a strictness slider (50-100%): pick which mods to include and how tight.",
      },
      {
        it: "\"Cerca su Trade\" apre pathofexile.com/trade con la ricerca esatta già pronta.",
        en: '"Search on Trade" opens pathofexile.com/trade with the exact search ready.',
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Ricerca Trade pre-compilata (funzionante)",
      en: "Prefilled Trade search (working)",
    },
    entries: [
      {
        it: "L'icona Trade ora apre davvero pathofexile.com/trade con la ricerca già pronta per l'item — si apre subito una scheda e dopo un istante mostra i risultati filtrati.",
        en: "The Trade icon now really opens pathofexile.com/trade with the search ready for the item — a tab opens immediately and shows the filtered results a moment later.",
      },
      {
        it: "Risolto un problema per cui, dopo \"Genera piano\", il riquadro del codice nel Planner diventava enorme: ora resta su una riga compatta.",
        en: 'Fixed an issue where, after "Generate plan", the code box in the Planner ballooned: it now stays on one compact line.',
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Ricerca Trade pre-compilata",
      en: "Prefilled Trade search",
    },
    summary: {
      it: "Il pulsante Trade apre direttamente la ricerca giusta.",
      en: "The Trade button opens the right search directly.",
    },
    entries: [
      {
        it: "Cliccando l'icona Trade su un item del Planner o di Analizza si apre ora pathofexile.com/trade con la ricerca già compilata: nome per gli unique, tipo base per i rari.",
        en: "Clicking the Trade icon on a Planner or Analyse item now opens pathofexile.com/trade with the search already filled in: name for uniques, base type for rares.",
      },
      {
        it: "Niente più copia-incolla manuale: il risultato è a un solo click.",
        en: "No more manual copy-paste: the result is a single click away.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Correzioni QA + stato persistente",
      en: "QA fixes + persistent state",
    },
    summary: {
      it: "Cinque migliorie su Finder, Analizza e Planner.",
      en: "Five improvements across Finder, Analyse and Planner.",
    },
    entries: [
      {
        it: 'Il pulsante "Copia PoB" nel Finder ora copia il codice PoB della build (importabile in Path of Building), non il link al profilo.',
        en: 'The Finder "Copy PoB" button now copies the build\'s PoB code (importable into Path of Building), not the profile link.',
      },
      {
        it: "La pagina Analizza e il Planner accettano anche l'URL di un personaggio poe.ninja, oltre al codice PoB e ai link pobb.in.",
        en: "The Analyse page and the Planner now also accept a poe.ninja character URL, on top of PoB codes and pobb.in links.",
      },
      {
        it: "Corretti i colori di Analizza e Planner nel tema chiaro: niente più riquadri scuri sullo sfondo crema.",
        en: "Fixed the Analyse and Planner colours in light mode: no more dark patches on the cream background.",
      },
      {
        it: "Il campo di input del Planner è ora compatto, coerente con quello di Analizza.",
        en: "The Planner input field is now compact, consistent with the Analyse one.",
      },
      {
        it: "Finder, Analizza e Planner conservano ricerca e risultati quando navighi tra le pagine — niente più dati persi.",
        en: "Finder, Analyse and Planner keep your search and results when you navigate between pages — no more lost work.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Rifinitura risultati Finder",
      en: "Finder result-list polish",
    },
    summary: {
      it: "Più contesto su ogni build trovata.",
      en: "More context on every build found.",
    },
    entries: [
      {
        it: "Quando ordini per DPS, vita, EHP o livello, un'etichetta nell'intestazione dei risultati lo segnala chiaramente.",
        en: "When you sort by DPS, life, EHP or level, a label in the results header makes it clear.",
      },
      {
        it: 'Ogni build mostra "X% del meta": quanto è popolare la sua skill nella ladder attuale.',
        en: 'Each build shows "X% of meta": how popular its skill is in the current ladder.',
      },
      {
        it: "Clicca il nome della skill su una card per filtrare al volo i risultati su quella skill.",
        en: "Click a skill name on a card to instantly filter the results to that skill.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Ricerca su Trade da gear e Analyze",
      en: "Trade search from gear and Analyze",
    },
    summary: {
      it: "Apri pathofexile.com/trade con un click da più punti.",
      en: "Open pathofexile.com/trade in one click from more places.",
    },
    entries: [
      {
        it: "Il pulsante per cercare un item su Trade è ora disponibile anche nella scheda Gear del Planner e su ogni pezzo di equipaggiamento della pagina Analyze.",
        en: "The button to search an item on Trade is now also on the Planner Gear tab and on every equipment piece in the Analyze page.",
      },
      {
        it: "Per gli unique viene copiato il nome, per i rari il tipo base — il termine giusto da incollare nella ricerca.",
        en: "For uniques the name is copied, for rares the base type — the right term to paste into the search.",
      },
    ],
  },
  {
    date: { it: "18 mag 2026", en: "18 May 2026" },
    title: {
      it: "Caricamento più veloce",
      en: "Faster loading",
    },
    entries: [
      {
        it: "Il sito ora carica solo il codice della pagina che apri: il pacchetto iniziale è quasi un terzo più leggero e l'avvio è più rapido.",
        en: "The site now loads only the code of the page you open: the initial bundle is almost a third lighter and startup is faster.",
      },
    ],
  },
  {
    date: { it: "17 mag 2026", en: "17 May 2026" },
    title: {
      it: "Fix: card del Finder in light mode",
      en: "Fix: Finder cards in light mode",
    },
    entries: [
      {
        it: "Le card dei risultati del Build Finder apparivano di un grigio sporco sullo sfondo crema del tema chiaro. Ora hanno la corretta tinta pergamena.",
        en: "The Build Finder result cards showed a muddy grey on the light theme's cream background. They now have the correct parchment tint.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: {
      it: "Supporto inglese + font uniforme",
      en: "English support + uniform font",
    },
    summary: {
      it: "L'intera interfaccia è ora bilingue.",
      en: "The whole interface is now bilingual.",
    },
    entries: [
      {
        it: "Aggiunto il supporto completo all'inglese con un toggle IT/EN nell'header, accanto al tema chiaro/scuro. La lingua scelta viene ricordata.",
        en: "Added full English support with an IT/EN toggle in the header, next to the light/dark theme switch. The chosen language is remembered.",
      },
      {
        it: "Font dei campi di testo uniformato su tutte le pagine (Geist Mono), coerente con i riquadri di codice di Home e Analyze.",
        en: "Input-field font unified across all pages (Geist Mono), consistent with the code boxes on Home and Analyze.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: {
      it: "Pagina Note di rilascio",
      en: "Patch Notes page",
    },
    entries: [
      {
        it: "Nuova pagina con tutto lo storico degli aggiornamenti del tool, dalle origini a oggi. Raggiungibile dal link in fondo alla barra di navigazione.",
        en: "New page with the tool's full update history, from the origins to today. Reached from the link at the bottom of the navbar.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: { it: 'Light mode "Parchment"', en: 'Light mode "Parchment"' },
    summary: {
      it: "La controparte diurna del tema scuro: pergamena calda invece di pietra del vuoto.",
      en: "The daytime counterpart of the dark theme: warm parchment instead of void stone.",
    },
    entries: [
      {
        it: 'Nuova modalità chiara "Parchment": sfondi crema caldi, testo inchiostro walnut, oro ember scurito per superare il contrasto WCAG su crema.',
        en: 'New "Parchment" light mode: warm cream backgrounds, dark-walnut ink text, ember gold darkened to clear WCAG contrast on cream.',
      },
      {
        it: "Il toggle sole/luna nell'header alterna in modo pulito tra Void Stone (scuro) e Parchment (chiaro) — niente più aree bianco-su-bianco.",
        en: "The sun/moon toggle in the header switches cleanly between Void Stone (dark) and Parchment (light) — no more white-on-white areas.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: { it: "Icona del sito", en: "Site favicon" },
    entries: [
      {
        it: 'Aggiunta una favicon "FOB" in neon viola su tile scura, leggibile nella tab del browser.',
        en: 'Added a neon-violet "FOB" favicon on a dark tile, readable in the browser tab.',
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: {
      it: 'Redesign frontend "Void Stone & Ember"',
      en: 'Frontend redesign "Void Stone & Ember"',
    },
    summary: {
      it: "Rifacimento completo dell'interfaccia con un'identità visiva ispirata a Path of Exile.",
      en: "Complete UI overhaul with a visual identity inspired by Path of Exile.",
    },
    entries: [
      {
        it: 'Nuovo design system: palette nero-vuoto + oro ember + testo pergamena, texture di rumore sottile, font Cinzel / Cabinet Grotesk / Geist Mono. Sostituito il vecchio tema viola "Atlas".',
        en: 'New design system: void-black + ember-gold + parchment-text palette, subtle noise texture, Cinzel / Cabinet Grotesk / Geist Mono fonts. Replaced the old "Atlas" violet theme.',
      },
      {
        it: 'Build Finder ridisegnato: ricerca hero centrale "Consulta l\'oracolo" che collassa dopo l\'analisi, riga di filtri compatta, layout a due colonne con sidebar statistiche, card risultato con stat chip a colori di rarità e animazione di comparsa scaglionata.',
        en: 'Build Finder redesigned: a centred "Consult the oracle" hero search that collapses after analysis, a compact filter row, a two-column layout with a stats sidebar, result cards with rarity-coloured stat chips and a staggered reveal animation.',
      },
      {
        it: "Planner: i 6 stage diventano una timeline orizzontale a numeri romani (I–VI); un click su uno stage ne espande la scheda dettagliata.",
        en: "Planner: the 6 stages become a horizontal Roman-numeral timeline (I–VI); clicking a stage expands its detailed card.",
      },
      {
        it: "Analyze: header personaggio sticky, valori numerici in monospace, comparsa progressiva delle sezioni.",
        en: "Analyze: sticky character header, monospace numeric values, progressive section reveal.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: {
      it: 'Overlay di cold-start "Divine Orb"',
      en: 'Cold-start "Divine Orb" overlay',
    },
    summary: {
      it: "Feedback visivo durante il risveglio del backend gratuito.",
      en: "Visual feedback while the free-tier backend wakes up.",
    },
    entries: [
      {
        it: "Il backend su Render free tier si spegne dopo 15 minuti di inattività; la prima richiesta impiega ~30s.",
        en: "The Render free-tier backend spins down after 15 minutes idle; the first request then takes ~30s.",
      },
      {
        it: "Aggiunto un overlay a tutto schermo con una Divine Orb animata (SVG disegnata a mano) mostrato mentre il server si risveglia.",
        en: "Added a full-screen overlay with an animated Divine Orb (hand-drawn SVG) shown while the server wakes up.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: {
      it: "Redesign pagina Analyze",
      en: "Analyze page redesign",
    },
    summary: {
      it: "Da quattro badge a una dashboard completa stile Path of Building.",
      en: "From four badges to a full Path of Building-style dashboard.",
    },
    entries: [
      {
        it: "La pagina Analyze mostra ora header personaggio + statistiche chiave (Vita, ES, EHP, DPS, armatura, evasione).",
        en: "The Analyze page now shows a character header + key stats (Life, ES, EHP, DPS, armour, evasion).",
      },
      {
        it: "Griglia equipaggiamento con tooltip per item (impliciti/espliciti, socket, item level), riga flasche e gioielli sull'albero.",
        en: "Equipment grid with per-item tooltips (implicits/explicits, sockets, item level), a flask row and tree jewels.",
      },
      {
        it: "Pannello completo dei collegamenti gemme, con gruppo principale evidenziato.",
        en: "A full skill-link panel, with the main group highlighted.",
      },
    ],
  },
  {
    date: { it: "15 mag 2026", en: "15 May 2026" },
    title: {
      it: "Statistiche di popolazione nel Finder",
      en: "Population stats in the Finder",
    },
    summary: {
      it: 'Contesto sul "meta" prima di scegliere una build.',
      en: 'Meta context before picking a build.',
    },
    entries: [
      {
        it: "Nuovo pannello che mostra le skill più giocate e le distribuzioni percentili (vita / ES / EHP / DPS / livello) per ascendancy, aggregate dalla ladder di poe.ninja.",
        en: "New panel showing the most-played skills and percentile distributions (life / ES / EHP / DPS / level) per ascendancy, aggregated from the poe.ninja ladder.",
      },
    ],
  },
  {
    date: { it: "14–15 mag 2026", en: "14–15 May 2026" },
    title: {
      it: "Pivot dinamico: sintesi al posto della curatela",
      en: "Dynamic pivot: synthesis over curation",
    },
    summary: {
      it: "La progressione della build viene derivata algoritmicamente dal PoB incollato.",
      en: "Build progression is derived algorithmically from the pasted PoB.",
    },
    entries: [
      {
        it: "Tree progression: l'albero passivo dei 6 stage viene derivato con una BFS sul PoB dell'utente, partendo dal nodo iniziale della classe.",
        en: "Tree progression: the 6-stage passive tree is derived with a BFS over the user's PoB, starting from the class start node.",
      },
      {
        it: "Gear progression: gli item vengono classificati per fascia di prezzo e sostituiti con equivalenti più economici per gli stage iniziali.",
        en: "Gear progression: items are classified by price tier and substituted with cheaper equivalents for the early stages.",
      },
      {
        it: "Gem progression: livello e qualità delle gemme proiettati lungo la curva campagna→endgame, con gestione di gemme Awakened/Vaal/trigger.",
        en: "Gem progression: gem level and quality projected along the campaign→endgame curve, handling Awakened/Vaal/trigger gems.",
      },
    ],
  },
  {
    date: { it: "14 mag 2026", en: "14 May 2026" },
    title: {
      it: "Build stage-by-stage stile Pohx",
      en: "Pohx-style stage-by-stage build",
    },
    summary: {
      it: "Per ogni stage: albero, gear, gemme e un codice PoB importabile.",
      en: "For each stage: tree, gear, gems and an importable PoB code.",
    },
    entries: [
      {
        it: "Progressione di albero passivo, equipaggiamento e collegamenti gemme per ognuno dei 6 stage.",
        en: "Passive tree, equipment and gem-link progression for each of the 6 stages.",
      },
      {
        it: 'Encoder XML di Path of Building: genera un codice importabile direttamente in PoB Community, con il pulsante "Importa stage in PoB".',
        en: 'Path of Building XML encoder: produces a code importable straight into PoB Community, via the "Import stage into PoB" button.',
      },
    ],
  },
  {
    date: { it: "14 mag 2026", en: "14 May 2026" },
    title: {
      it: "Filtri di ricerca Finder",
      en: "Finder search filters",
    },
    entries: [
      {
        it: "Filtro per classe o ascendancy, soglie minime di Vita/ES/EHP/DPS, range di livello, ordinamento.",
        en: "Filter by class or ascendancy, minimum Life/ES/EHP/DPS thresholds, level range, sorting.",
      },
      {
        it: 'L\'estrattore di intent capisce frasi come "almeno 1m dps e 8000 ehp, ordina per ehp".',
        en: 'The intent extractor understands phrases like "at least 1m dps and 8000 ehp, sort by ehp".',
      },
    ],
  },
  {
    date: { it: "14 mag 2026", en: "14 May 2026" },
    title: {
      it: "Migrazione backend Fly.io → Render",
      en: "Backend migration Fly.io → Render",
    },
    entries: [
      {
        it: "Il backend è stato migrato su Render, che offre un free tier permanente. Trade-off: spin-down dopo 15 min di inattività.",
        en: "The backend was migrated to Render, which offers a permanent free tier. Trade-off: spin-down after 15 min idle.",
      },
    ],
  },
  {
    date: { it: "7 mag 2026", en: "7 May 2026" },
    title: {
      it: "FOB live in produzione",
      en: "FOB live in production",
    },
    summary: {
      it: "Il tool diventa pubblico, a costo zero.",
      en: "The tool goes public, at zero cost.",
    },
    entries: [
      {
        it: "Hardening per uso multi-utente: CORS, limiti di concorrenza, health check arricchito.",
        en: "Hardening for multi-user use: CORS, concurrency limits, an enriched health check.",
      },
      {
        it: "Containerizzazione con Dockerfile multi-stage. Deploy: frontend su Vercel, backend su hosting cloud. Costo: 0 €/mese.",
        en: "Containerisation with a multi-stage Dockerfile. Deploy: frontend on Vercel, backend on cloud hosting. Cost: €0/month.",
      },
    ],
  },
  {
    date: { it: "1–2 mag 2026", en: "1–2 May 2026" },
    title: {
      it: "49 template + motore reverse-progression",
      en: "49 templates + reverse-progression engine",
    },
    summary: {
      it: "Copertura completa delle build e upgrade ladder personalizzate.",
      en: "Full build coverage and personalised upgrade ladders.",
    },
    entries: [
      {
        it: "49 BuildTemplate: 7 per ognuna delle 7 classi di Path of Exile 1.",
        en: "49 BuildTemplates: 7 for each of Path of Exile 1's 7 classes.",
      },
      {
        it: "Motore reverse-progression: ogni item endgame genera una upgrade ladder di predecessori via via più economici, con la motivazione di ogni gradino.",
        en: "Reverse-progression engine: each endgame item generates an upgrade ladder of progressively cheaper predecessors, with a rationale for every rung.",
      },
    ],
  },
  {
    date: { it: "30 apr 2026", en: "30 Apr 2026" },
    title: {
      it: "Template aggiuntivi + BuildCard",
      en: "Extra templates + BuildCard",
    },
    entries: [
      {
        it: "16 nuovi template di build (caster, attack, minion, totem).",
        en: "16 new build templates (caster, attack, minion, totem).",
      },
      {
        it: 'BuildCard potenziata: EHP visibile, pulsante "Copia link" al profilo poe.ninja, gemme principali caricate su richiesta.',
        en: 'Improved BuildCard: visible EHP, a "Copy link" button to the poe.ninja profile, main gems loaded on demand.',
      },
    ],
  },
  {
    date: { it: "26 apr 2026", en: "26 Apr 2026" },
    title: {
      it: "Planner v2 + interfaccia",
      en: "Planner v2 + interface",
    },
    summary: {
      it: "Il planner prende la sua forma a 6 fasi e l'app prende un'identità.",
      en: "The planner takes its 6-stage shape and the app gets an identity.",
    },
    entries: [
      {
        it: "Planner v2: 6 fasi, ognuna con range di divine, motivazione e trigger per avanzare.",
        en: "Planner v2: 6 stages, each with a divine range, a rationale and a trigger to advance.",
      },
      {
        it: "Pricing in streaming via Server-Sent Events con barra di avanzamento ed ETA dinamico.",
        en: "Streaming pricing via Server-Sent Events with a progress bar and a dynamic ETA.",
      },
      {
        it: "Overhaul UI: tema, routing, pagine Welcome e Home.",
        en: "UI overhaul: theme, routing, Welcome and Home pages.",
      },
    ],
  },
  {
    date: { it: "25–26 apr 2026", en: "25–26 Apr 2026" },
    title: { it: "Pricing v2", en: "Pricing v2" },
    summary: {
      it: "Prezzi affidabili anche per uniques con varianti e rari custom.",
      en: "Reliable prices even for variant uniques and custom rares.",
    },
    entries: [
      {
        it: "Pricing variant-aware per uniques (Forbidden Shako/Flame/Flesh, Impossible Escape...).",
        en: "Variant-aware pricing for uniques (Forbidden Shako/Flame/Flesh, Impossible Escape...).",
      },
      {
        it: "Nuova sorgente: GGG Trade API, con rispetto del rate-limit, per i rari custom-craftati.",
        en: "New source: the GGG Trade API, rate-limit aware, for custom-crafted rares.",
      },
    ],
  },
  {
    date: { it: "24–25 apr 2026", en: "24–25 Apr 2026" },
    title: { it: "Le fondamenta", en: "The foundations" },
    summary: {
      it: "Dalla prima riga di codice al primo planner funzionante.",
      en: "From the first line of code to the first working planner.",
    },
    entries: [
      {
        it: "Modelli di dominio core, ingest e parser dei codici Path of Building.",
        en: "Core domain models, ingest and parser for Path of Building codes.",
      },
      {
        it: "Integrazione economia poe.ninja e ladder builds con ricerca su tutte le ascendancy.",
        en: "poe.ninja economy integration and a builds ladder searched across every ascendancy.",
      },
      {
        it: "IntentExtractor (capisce richieste in italiano e inglese) e Ranking Engine con score multi-dimensionale.",
        en: "An IntentExtractor (understands Italian and English requests) and a Ranking Engine with a multi-dimensional score.",
      },
      {
        it: "Primo Planner e shell React + Vite + Mantine.",
        en: "The first Planner and the React + Vite + Mantine shell.",
      },
    ],
  },
];

function ReleaseCard({ release }: { release: Release }) {
  const t = useT();
  return (
    <Card
      withBorder
      radius="md"
      p="md"
      style={{ borderLeft: "3px solid var(--vs-ember)" }}
    >
      <Stack gap={8}>
        <Group justify="space-between" align="center" wrap="nowrap">
          <Title order={4}>{t(release.title)}</Title>
          <Badge color="ember" variant="light" size="sm" style={{ flexShrink: 0 }}>
            {t(release.date)}
          </Badge>
        </Group>
        {release.summary && (
          <Text size="sm" c="dimmed" fs="italic">
            {t(release.summary)}
          </Text>
        )}
        <Stack gap={4} mt={2}>
          {release.entries.map((e, i) => (
            <Group key={i} gap={8} wrap="nowrap" align="flex-start">
              <Box
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: "50%",
                  background: "var(--vs-ember)",
                  marginTop: 7,
                  flexShrink: 0,
                }}
              />
              <Text size="sm">{t(e)}</Text>
            </Group>
          ))}
        </Stack>
      </Stack>
    </Card>
  );
}

export function PatchNotesPage() {
  const t = useT();
  return (
    <Stack gap="md">
      <Group gap={10} align="center">
        <IconHistory size={26} color="var(--vs-ember)" />
        <Title order={2}>
          {t({ it: "Note di rilascio", en: "Patch notes" })}
        </Title>
      </Group>
      <Text c="dimmed" size="sm">
        {t({
          it: "Tutta la storia di FOB, dalle origini a oggi — dalla prima riga di codice (24 aprile 2026) all'ultimo aggiornamento. Dal più recente.",
          en: "The whole history of FOB, from the origins to today — from the first line of code (24 April 2026) to the latest update. Newest first.",
        })}
      </Text>

      <Stack gap="sm">
        {RELEASES.map((r, i) => (
          <ReleaseCard key={i} release={r} />
        ))}
      </Stack>

      <Text size="xs" c="dimmed" ta="center" mt="md">
        {t({
          it: "FOB · Frusta Oracle Builder — progetto personale, open-source su GitHub.",
          en: "FOB · Frusta Oracle Builder — a personal project, open-source on GitHub.",
        })}
      </Text>
    </Stack>
  );
}
