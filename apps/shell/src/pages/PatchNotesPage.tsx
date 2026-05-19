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
