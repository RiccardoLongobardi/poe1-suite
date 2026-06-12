/**
 * PrivacyPage — privacy & legal notes, static + bilingual.
 *
 * FOB collects nothing: no accounts, no tracking, preferences in
 * localStorage only. This page states that plainly, lists the
 * third-party APIs contacted to answer requests, and carries the
 * GGG-content disclaimer.
 */

import { Card, Group, Stack, Text, Title } from "@mantine/core";
import { IconShieldLock } from "@tabler/icons-react";
import { useT, type Tr } from "../i18n";

interface Section {
  title: Tr;
  body: Tr;
}

const SECTIONS: Section[] = [
  {
    title: { it: "Nessun dato personale", en: "No personal data" },
    body: {
      it: "FOB non ha account, registrazione o login. Non raccogliamo nome, email, indirizzo IP a fini di profilazione, né alcun altro dato personale. Non ci sono cookie di tracciamento, analytics di terze parti o pubblicità.",
      en: "FOB has no accounts, registration or login. We don't collect your name, email, IP address for profiling, or any other personal data. There are no tracking cookies, third-party analytics or ads.",
    },
  },
  {
    title: {
      it: "Preferenze salvate solo nel tuo browser",
      en: "Preferences stored in your browser only",
    },
    body: {
      it: "Lingua, tema e lo stato delle pagine (ultima ricerca, filtri) vivono nel localStorage/sessionStorage del tuo browser e non lasciano mai il tuo dispositivo. Cancellare i dati di navigazione li rimuove.",
      en: "Language, theme and page state (last search, filters) live in your browser's localStorage/sessionStorage and never leave your device. Clearing your browsing data removes them.",
    },
  },
  {
    title: {
      it: "Cosa succede quando fai una ricerca",
      en: "What happens when you run a search",
    },
    body: {
      it: "Le tue richieste (criteri di ricerca, codici PoB incollati) vengono inviate al backend di FOB solo per produrre la risposta e non vengono memorizzate in modo permanente. Per rispondere, il backend interroga API pubbliche di terze parti: poe.ninja (ladder e prezzi) e pathofexile.com (API Trade ufficiale di GGG). A queste API non viene inoltrato alcun tuo dato personale.",
      en: "Your requests (search criteria, pasted PoB codes) are sent to FOB's backend only to produce the answer and are not permanently stored. To answer, the backend queries public third-party APIs: poe.ninja (ladder and prices) and pathofexile.com (GGG's official Trade API). No personal data of yours is forwarded to those APIs.",
    },
  },
  {
    title: { it: "Donazioni", en: "Donations" },
    body: {
      it: "Il pulsante di supporto apre PayPal in una nuova scheda. L'eventuale donazione avviene interamente su PayPal ed è soggetta ai suoi termini e alla sua privacy policy — FOB non riceve né conserva alcun dato del pagamento.",
      en: "The support button opens PayPal in a new tab. Any donation happens entirely on PayPal and is subject to its terms and privacy policy — FOB receives and stores no payment data.",
    },
  },
  {
    title: { it: "Contenuti di gioco e marchi", en: "Game content and trademarks" },
    body: {
      it: "Path of Exile è un marchio di Grinding Gear Games. Tutti i contenuti di gioco citati (skill, oggetti, albero delle passive) sono proprietà di Grinding Gear Games. FOB è un progetto indipendente della community, non affiliato né approvato da GGG.",
      en: "Path of Exile is a trademark of Grinding Gear Games. All referenced game content (skills, items, the passive tree) is property of Grinding Gear Games. FOB is an independent community project, neither affiliated with nor endorsed by GGG.",
    },
  },
  {
    title: { it: "Open source", en: "Open source" },
    body: {
      it: "Il codice di FOB è open-source: puoi verificarne il funzionamento, segnalare problemi o contribuire su GitHub. Questa pagina descrive lo stato attuale del progetto e verrà aggiornata se qualcosa cambia.",
      en: "FOB's code is open-source: you can inspect how it works, report issues or contribute on GitHub. This page describes the project's current state and will be updated if anything changes.",
    },
  },
];

export function PrivacyPage() {
  const t = useT();
  return (
    <Stack gap="md">
      <Group gap={10} align="center">
        <IconShieldLock size={26} color="var(--vs-ember)" />
        <Title order={2}>{t({ it: "Privacy e note legali", en: "Privacy & legal" })}</Title>
      </Group>
      <Text c="dimmed" size="sm">
        {t({
          it: "In breve: FOB non raccoglie nulla. Qui sotto i dettagli, in linguaggio semplice.",
          en: "In short: FOB collects nothing. The details below, in plain language.",
        })}
      </Text>
      {SECTIONS.map((s, i) => (
        <Card key={i} withBorder radius="md" p="md">
          <Stack gap={6}>
            <Title order={4}>{t(s.title)}</Title>
            <Text size="sm" c="dimmed">
              {t(s.body)}
            </Text>
          </Stack>
        </Card>
      ))}
    </Stack>
  );
}
