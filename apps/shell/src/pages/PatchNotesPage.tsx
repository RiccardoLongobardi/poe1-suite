/**
 * PatchNotesPage — the full release history of FOB.
 *
 * A static, data-driven changelog: every release from the first
 * commit to today, newest first. Reached from a low-prominence nav
 * link at the bottom of the navbar.
 */

import { Badge, Box, Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconHistory } from "@tabler/icons-react";

interface Release {
  /** Short label shown in the date badge. */
  date: string;
  /** Release headline. */
  title: string;
  /** Optional one-line summary under the title. */
  summary?: string;
  /** Detailed change bullets. */
  entries: string[];
}

// Newest first. Compiled from the project's step-by-step history.
const RELEASES: Release[] = [
  {
    date: "15 mag 2026",
    title: "Step 23 — Light mode \"Parchment\"",
    summary:
      "La controparte diurna del tema scuro: pergamena calda invece di pietra del vuoto.",
    entries: [
      "Nuova modalità chiara \"Parchment\": sfondi crema caldi, testo inchiostro walnut, oro ember scurito per superare il contrasto WCAG su crema.",
      "Il toggle sole/luna nell'header ora alterna in modo pulito tra Void Stone (scuro) e Parchment (chiaro) — niente più aree bianco-su-bianco.",
      "Fix collaterali che migliorano anche il tema scuro: campi input e testo secondario allineati ai token di design.",
    ],
  },
  {
    date: "15 mag 2026",
    title: "Icona del sito",
    summary: "Favicon dedicata al posto dell'icona vuota di default.",
    entries: [
      "Aggiunta una favicon \"FOB\" in neon viola su tile scura, leggibile nella tab del browser.",
    ],
  },
  {
    date: "15 mag 2026",
    title: "Step 22 — Redesign frontend \"Void Stone & Ember\"",
    summary:
      "Rifacimento completo dell'interfaccia con un'identità visiva ispirata a Path of Exile.",
    entries: [
      "Nuovo design system: palette nero-vuoto + oro ember + testo pergamena, texture di rumore sottile, font Cinzel / Cabinet Grotesk / Geist Mono. Sostituito il vecchio tema viola \"Atlas\".",
      "Build Finder ridisegnato: ricerca hero centrale \"Consulta l'oracolo\" che collassa dopo l'analisi, riga di filtri compatta, layout a due colonne con sidebar statistiche, card risultato con stat chip a colori di rarità e animazione di comparsa scaglionata.",
      "Planner: i 6 stage diventano una timeline orizzontale a numeri romani (I–VI); un click su uno stage ne espande la scheda dettagliata.",
      "Analyze: header personaggio sticky, valori numerici in monospace, comparsa progressiva delle sezioni.",
      "Fix QA: la riga filtri del Finder si adatta agli schermi larghi; le statistiche Vita/ES/EHP della pagina Analyze non vengono più nascoste dall'header.",
    ],
  },
  {
    date: "15 mag 2026",
    title: "Step 21 — Overlay di cold-start \"Divine Orb\"",
    summary:
      "Feedback visivo durante il risveglio del backend gratuito.",
    entries: [
      "Il backend su Render free tier si spegne dopo 15 minuti di inattività; la prima richiesta impiega ~30s.",
      "Aggiunto un overlay a tutto schermo con una Divine Orb animata (SVG disegnata a mano) mostrato mentre il server si risveglia, così l'utente non pensa che il sito sia rotto.",
    ],
  },
  {
    date: "15 mag 2026",
    title: "Step 20 — Redesign pagina Analyze",
    summary: "Da quattro badge a una dashboard completa stile Path of Building.",
    entries: [
      "La pagina Analyze mostra ora: header personaggio + statistiche chiave (Vita, ES, EHP, DPS, armatura, evasione).",
      "Griglia equipaggiamento con tooltip per item (impliciti/espliciti, socket, item level), riga flasche e gioielli sull'albero.",
      "Pannello completo dei collegamenti gemme, con gruppo principale evidenziato.",
    ],
  },
  {
    date: "15 mag 2026",
    title: "Step 19 — Statistiche di popolazione nel Finder",
    summary: "Contesto sul \"meta\" prima di scegliere una build.",
    entries: [
      "Nuovo pannello che mostra le skill più giocate e le distribuzioni percentili (vita / ES / EHP / DPS / livello) per ascendancy, aggregate dalla ladder di poe.ninja.",
      "Si aggiorna in tempo reale al cambio del filtro classe/ascendancy.",
    ],
  },
  {
    date: "14–15 mag 2026",
    title: "Step 16–18 — Pivot dinamico: sintesi al posto della curatela",
    summary:
      "La progressione della build viene derivata algoritmicamente dal PoB incollato, non più hand-curated.",
    entries: [
      "Step 16 — Dynamic Tree Progression: l'albero passivo dei 6 stage viene derivato con una BFS sul PoB dell'utente, partendo dal nodo iniziale della classe.",
      "Step 17 — Dynamic Gear Progression: gli item vengono classificati per fascia di prezzo e sostituiti con equivalenti più economici per gli stage iniziali.",
      "Step 18 — Dynamic Gem Progression: livello e qualità delle gemme proiettati lungo la curva campagna→endgame, con gestione di gemme Awakened/Vaal/trigger.",
      "I 49 template hand-written restano solo come testo descrittivo e fallback per chi non incolla un PoB.",
    ],
  },
  {
    date: "14 mag 2026",
    title: "Step 14 — Build stage-by-stage stile Pohx",
    summary:
      "Per ogni stage: albero, gear, gemme e un codice PoB importabile.",
    entries: [
      "Progressione di albero passivo, equipaggiamento e collegamenti gemme per ognuno dei 6 stage.",
      "Encoder XML di Path of Building: genera un codice importabile direttamente in PoB Community.",
      "Pulsante \"Importa stage in PoB\" nella scheda di ogni stage.",
      "Debug a fondo del formato PoB (header URL dell'albero, mastery, cluster jewel) per garantire un import pulito.",
    ],
  },
  {
    date: "14 mag 2026",
    title: "Step 15 — Filtri di ricerca Finder",
    summary: "Ricerca più precisa con filtri ed estrazione da linguaggio naturale.",
    entries: [
      "Filtro per classe o ascendancy, soglie minime di Vita/ES/EHP/DPS, range di livello, ordinamento.",
      "L'estrattore di intent capisce frasi come \"almeno 1m dps e 8000 ehp, ordina per ehp\".",
    ],
  },
  {
    date: "14 mag 2026",
    title: "Migrazione backend Fly.io → Render",
    summary: "Cambio di hosting per restare sul piano gratuito permanente.",
    entries: [
      "Il trial di Fly.io richiedeva una carta di credito; il backend è stato migrato su Render, free tier permanente.",
      "Trade-off accettato: spin-down dopo 15 min di inattività (gestito poi dall'overlay di cold-start).",
    ],
  },
  {
    date: "7 mag 2026",
    title: "FOB live in produzione",
    summary: "Il tool diventa pubblico, a costo zero.",
    entries: [
      "Hardening per uso multi-utente: CORS, limiti di concorrenza, health check arricchito.",
      "Containerizzazione con Dockerfile multi-stage.",
      "Deploy: frontend su Vercel, backend su hosting cloud. Costo: 0 €/mese.",
      "Round di bug-fix post-lancio: hard skill filter, fix rate-limit, gestione 429 della Trade API.",
    ],
  },
  {
    date: "1–2 mag 2026",
    title: "Step 13 — 49 template + motore reverse-progression",
    summary: "Copertura completa delle build e upgrade ladder personalizzate.",
    entries: [
      "49 BuildTemplate: 7 per ognuna delle 7 classi di Path of Exile 1.",
      "Pricing della combo Watcher's Eye tramite la GGG Trade API.",
      "Motore reverse-progression: ogni item endgame genera una \"upgrade ladder\" di predecessori via via più economici, con la motivazione di ogni gradino.",
      "Integrazione Trade-search nello stile poe.ninja per gli item del piano.",
    ],
  },
  {
    date: "30 apr 2026",
    title: "Step 12 — Template aggiuntivi + BuildCard",
    entries: [
      "16 nuovi template di build (caster, attack, minion, totem).",
      "BuildCard potenziata: EHP visibile, pulsante \"Copia link\" al profilo poe.ninja, gemme principali caricate su richiesta.",
    ],
  },
  {
    date: "26 apr 2026",
    title: "Step 10–11 — Planner v2 + interfaccia",
    summary: "Il planner prende la sua forma a 6 fasi e l'app prende un'identità.",
    entries: [
      "Planner v2: 6 fasi (Early/Mid/End Campaign + Early/End Mapping + High Investment), ognuna con range di divine, motivazione e trigger per avanzare.",
      "Sistema BuildTemplate per descrivere ogni build.",
      "Pricing in streaming via Server-Sent Events con barra di avanzamento ed ETA dinamico.",
      "Overhaul UI: tema astrale, routing, pagine Welcome e Home.",
    ],
  },
  {
    date: "25–26 apr 2026",
    title: "Step 9 — Pricing v2",
    summary: "Prezzi affidabili anche per uniques con varianti e rari custom.",
    entries: [
      "Pricing variant-aware per uniques (Forbidden Shako/Flame/Flesh, Impossible Escape...).",
      "Nuova sorgente: GGG Trade API, con rispetto del rate-limit, per i rari custom-craftati.",
      "Estrazione dei modificatori dal PoB per query di prezzo stat-aware.",
    ],
  },
  {
    date: "24–25 apr 2026",
    title: "Step 1–8 — Le fondamenta",
    summary: "Dalla prima riga di codice al primo planner funzionante.",
    entries: [
      "Modelli di dominio core (Build, Intent, Plan, Item, enum di gioco).",
      "Ingest e parser dei codici Path of Building (raw, pobb.in, pastebin).",
      "Integrazione economia poe.ninja (currency, uniques, cluster jewel...).",
      "Ladder builds di poe.ninja con ricerca su tutte le 19 ascendancy.",
      "IntentExtractor: capisce richieste in italiano e inglese.",
      "Ranking Engine: punteggio multi-dimensionale per consigliare le build.",
      "Primo Planner e shell React + Vite + Mantine.",
    ],
  },
];

function ReleaseCard({ release }: { release: Release }) {
  return (
    <Card
      withBorder
      radius="md"
      p="md"
      style={{ borderLeft: "3px solid var(--vs-ember)" }}
    >
      <Stack gap={8}>
        <Group justify="space-between" align="center" wrap="nowrap">
          <Title order={4}>{release.title}</Title>
          <Badge color="ember" variant="light" size="sm" style={{ flexShrink: 0 }}>
            {release.date}
          </Badge>
        </Group>
        {release.summary && (
          <Text size="sm" c="dimmed" fs="italic">
            {release.summary}
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
              <Text size="sm">{e}</Text>
            </Group>
          ))}
        </Stack>
      </Stack>
    </Card>
  );
}

export function PatchNotesPage() {
  return (
    <Stack gap="md">
      <Group gap={10} align="center">
        <IconHistory size={26} color="var(--vs-ember)" />
        <Title order={2}>Note di rilascio</Title>
      </Group>
      <Text c="dimmed" size="sm">
        Tutta la storia di FOB, dalle origini a oggi — dalla prima riga di
        codice (24 aprile 2026) all'ultimo aggiornamento. Dal più recente.
      </Text>

      <Stack gap="sm">
        {RELEASES.map((r, i) => (
          <ReleaseCard key={i} release={r} />
        ))}
      </Stack>

      <Text size="xs" c="dimmed" ta="center" mt="md">
        FOB · Frusta Oracle Builder — progetto personale, open-source su GitHub.
      </Text>
    </Stack>
  );
}
