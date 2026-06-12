/**
 * FaqPage — frequently asked questions, static + bilingual.
 *
 * Honest answers about what FOB is, where the data comes from, how the
 * numbers are computed (PoB-exact) and the known limitations. Reached
 * from a low-prominence nav link at the bottom of the navbar.
 */

import { Accordion, Group, Stack, Text, Title } from "@mantine/core";
import { IconHelpCircle } from "@tabler/icons-react";
import { useT, type Tr } from "../i18n";

interface FaqItem {
  q: Tr;
  a: Tr;
}

const FAQ: FaqItem[] = [
  {
    q: { it: "Cos'è FOB?", en: "What is FOB?" },
    a: {
      it: "FOB (Frusta Oracle Builder) è una suite di strumenti gratuiti per Path of Exile 1: il Build Finder cerca build reali nella ladder, Analizza PoB trasforma un codice Path of Building in una dashboard leggibile, il Planner costruisce un piano di upgrade in 6 fasi con prezzi live, e il Theorycrafter genera build da zero dai dati ufficiali del gioco. È un progetto personale, open-source.",
      en: "FOB (Frusta Oracle Builder) is a free toolkit for Path of Exile 1: the Build Finder searches real ladder builds, Analyze PoB turns a Path of Building code into a readable dashboard, the Planner builds a 6-stage upgrade plan with live prices, and the Theorycrafter generates builds from scratch from official game data. It's a personal, open-source project.",
    },
  },
  {
    q: { it: "Da dove vengono i dati?", en: "Where does the data come from?" },
    a: {
      it: "Le build reali e i prezzi vengono da poe.ninja (ladder e economia della lega corrente). L'albero delle passive, le gemme e le basi degli oggetti vengono dai dati ufficiali del gioco (gli stessi usati da Path of Building Community e RePoE). I prezzi dei rari craftati usano l'API Trade ufficiale di GGG. Niente è inventato: ogni nodo, gemma e oggetto che FOB mostra esiste davvero nel gioco.",
      en: "Real builds and prices come from poe.ninja (the current league's ladder and economy). The passive tree, gems and item bases come from official game data (the same used by Path of Building Community and RePoE). Crafted-rare prices use GGG's official Trade API. Nothing is invented: every node, gem and item FOB shows genuinely exists in the game.",
    },
  },
  {
    q: {
      it: "Come sono calcolati i DPS del Theorycrafter?",
      en: "How is Theorycrafter DPS computed?",
    },
    a: {
      it: "Le build precalcolate (badge “Ottimizzato con PoB”) sono valutate eseguendo il vero motore di calcolo di Path of Building: il numero che vedi è esattamente quello che vedresti importando la build in PoB. Le build generate al volo mostrano invece stime indicative (marcate con “~”) — importa in PoB per il numero preciso.",
      en: "Precomputed builds (the “Optimised with PoB” badge) are evaluated by running Path of Building's real calculation engine: the number you see is exactly what you'd see importing the build into PoB. Live-generated builds show indicative estimates (marked “~”) — import into PoB for the precise number.",
    },
  },
  {
    q: {
      it: "Perché le build del Theorycrafter fanno meno danni di quelle in cima alla ladder?",
      en: "Why do Theorycrafter builds deal less damage than top-ladder ones?",
    },
    a: {
      it: "Le build top della ladder usano equipaggiamento mirror-tier (oggetti da centinaia di divine, spesso irripetibili) e gemme legacy che esistono solo in Standard. FOB genera build oneste: legali nella lega corrente, equipaggiabili, lanciabili e importabili in PoB senza warning. Preferiamo un numero vero a uno gonfiato.",
      en: "Top ladder builds run mirror-tier gear (items worth hundreds of divines, often unobtainable) and legacy gems that only exist in Standard. FOB generates honest builds: legal in the current league, equippable, castable and importable into PoB with no warnings. We prefer a true number to an inflated one.",
    },
  },
  {
    q: {
      it: "Come ordina i risultati il Build Finder?",
      en: "How does the Build Finder rank results?",
    },
    a: {
      it: "Con uno score multidimensionale e spiegabile: quanto la build combacia con i criteri scelti (skill, classe, contenuto) più le sue statistiche. Espandendo una card vedi il dettaglio del punteggio. Puoi anche ordinare direttamente per DPS, Vita, EHP o livello.",
      en: "With a multi-dimensional, explainable score: how well the build matches your chosen criteria (skill, class, content) plus its stats. Expanding a card shows the score breakdown. You can also sort directly by DPS, Life, EHP or level.",
    },
  },
  {
    q: { it: "I prezzi sono aggiornati?", en: "Are prices up to date?" },
    a: {
      it: "I prezzi vengono da poe.ninja con una cache di ~15 minuti, e per i rari craftati dall'API Trade di GGG in tempo reale. Sono indicativi: il mercato si muove, controlla sempre il Trade prima di comprare (i pulsanti Trade di FOB aprono ricerche precompilate).",
      en: "Prices come from poe.ninja with a ~15-minute cache, and for crafted rares from GGG's Trade API in real time. They're indicative: the market moves, always check Trade before buying (FOB's Trade buttons open prefilled searches).",
    },
  },
  {
    q: {
      it: "Posso importare le build in Path of Building?",
      en: "Can I import builds into Path of Building?",
    },
    a: {
      it: "Sì. Il Theorycrafter e ogni fase del Planner producono un codice PoB importabile in Path of Building Community (Import → Import from code). Il Finder ti dà il codice PoB di qualsiasi personaggio della ladder con “Copia PoB”.",
      en: "Yes. The Theorycrafter and every Planner stage produce a PoB code importable into Path of Building Community (Import → Import from code). The Finder gives you any ladder character's PoB code via “Copy PoB”.",
    },
  },
  {
    q: {
      it: "Perché la prima richiesta a volte è lenta?",
      en: "Why is the first request sometimes slow?",
    },
    a: {
      it: "Il backend gira su un piano gratuito che va in pausa dopo 15 minuti di inattività: la prima richiesta dopo una pausa impiega ~30 secondi a svegliarlo (vedrai l'overlay di caricamento). Le richieste successive sono veloci.",
      en: "The backend runs on a free tier that sleeps after 15 minutes of inactivity: the first request after a pause takes ~30 seconds to wake it (you'll see the loading overlay). Subsequent requests are fast.",
    },
  },
  {
    q: { it: "FOB è gratis? Come lo supporto?", en: "Is FOB free? How do I support it?" },
    a: {
      it: "Completamente gratis, senza account né pubblicità. Se ti è utile e vuoi sostenere i costi e il tempo di mantenerlo aggiornato a ogni lega, c'è un link PayPal nel pulsante “Supporta il progetto”.",
      en: "Completely free, with no accounts and no ads. If it's useful and you want to support the costs and time of keeping it updated every league, there's a PayPal link behind the “Support the project” button.",
    },
  },
  {
    q: { it: "FOB è affiliato a GGG?", en: "Is FOB affiliated with GGG?" },
    a: {
      it: "No. FOB è un progetto indipendente della community. Path of Exile e tutti i contenuti di gioco sono proprietà di Grinding Gear Games.",
      en: "No. FOB is an independent community project. Path of Exile and all game content are property of Grinding Gear Games.",
    },
  },
];

export function FaqPage() {
  const t = useT();
  return (
    <Stack gap="md">
      <Group gap={10} align="center">
        <IconHelpCircle size={26} color="var(--vs-ember)" />
        <Title order={2}>{t({ it: "Domande frequenti", en: "FAQ" })}</Title>
      </Group>
      <Text c="dimmed" size="sm">
        {t({
          it: "Tutto quello che c'è da sapere su FOB: cosa fa, da dove vengono i dati e quali sono i suoi limiti — senza giri di parole.",
          en: "Everything you need to know about FOB: what it does, where the data comes from and what its limits are — no sugar-coating.",
        })}
      </Text>
      <Accordion variant="separated" radius="md" multiple>
        {FAQ.map((item, i) => (
          <Accordion.Item key={i} value={`q${i}`}>
            <Accordion.Control>
              <Text fw={600} size="sm">
                {t(item.q)}
              </Text>
            </Accordion.Control>
            <Accordion.Panel>
              <Text size="sm" c="dimmed">
                {t(item.a)}
              </Text>
            </Accordion.Panel>
          </Accordion.Item>
        ))}
      </Accordion>
    </Stack>
  );
}
