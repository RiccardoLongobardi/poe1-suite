/**
 * HomePage — feature dashboard at "/home".
 *
 * Three large cards walk the user through what FOB can do, each
 * navigating to its respective tool. A footer "Supporta" card opens
 * the donation modal.
 */

import {
  Badge,
  Box,
  Button,
  Card,
  Group,
  SimpleGrid,
  Stack,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconArrowRight,
  IconHeart,
  IconListCheck,
  IconSearch,
  IconTool,
} from "@tabler/icons-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { DonationModal } from "../components/DonationModal";
import { useT } from "../i18n";

interface FeatureCardProps {
  to: string;
  icon: ReactNode;
  iconColor: string;
  title: string;
  description: string;
  example?: string;
  openLabel: string;
}

function FeatureCard({
  to,
  icon,
  iconColor,
  title,
  description,
  example,
  openLabel,
}: FeatureCardProps) {
  const navigate = useNavigate();
  return (
    <Card
      className="fob-feature-card"
      p="lg"
      onClick={() => navigate(to)}
      role="link"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") navigate(to);
      }}
    >
      <Stack gap="md" h="100%">
        <Group gap={12}>
          <ThemeIcon variant="light" color={iconColor} size={48} radius="md">
            {icon}
          </ThemeIcon>
          <Title order={3} style={{ margin: 0 }}>
            {title}
          </Title>
        </Group>
        <Text size="sm" c="dimmed" style={{ flex: 1 }}>
          {description}
        </Text>
        {example && (
          <Text
            size="xs"
            c="dimmed"
            ff="monospace"
            style={{
              padding: "8px 12px",
              backgroundColor: "rgba(200, 147, 42, 0.08)",
              borderRadius: 8,
              borderLeft: "2px solid var(--vs-ember)",
            }}
          >
            {example}
          </Text>
        )}
        <Group justify="flex-end" mt="auto">
          <Text size="sm" c={iconColor} fw={500}>
            {openLabel} →
          </Text>
        </Group>
      </Stack>
    </Card>
  );
}

export function HomePage() {
  const [donationOpen, donation] = useDisclosure(false);
  const t = useT();

  return (
    <Stack gap="xl" pb="xl">
      {/* Hero */}
      <Stack gap="xs" align="center" ta="center" pt="md" pb="md">
        <Badge variant="light" color="ember" size="lg">
          <Group gap={4} wrap="nowrap">
            <Text size="xs" fw={500}>
              v1 — Mirage League
            </Text>
          </Group>
        </Badge>
        <Title
          order={1}
          style={{
            fontSize: "2.4rem",
            textShadow: "0 0 20px rgba(200, 147, 42, 0.3)",
          }}
        >
          {t({
            it: "Cosa stiamo costruendo oggi?",
            en: "What are we building today?",
          })}
        </Title>
        <Text c="dimmed" size="md" maw={620}>
          {t({
            it: "FOB ti aiuta a scegliere una build, capire cosa fa, e pianificare l'upgrade dal day-0 al day-100 con i prezzi live di poe.ninja e GGG Trade.",
            en: "FOB helps you pick a build, understand what it does, and plan the upgrade path from day-0 to day-100 with live prices from poe.ninja and GGG Trade.",
          })}
        </Text>
      </Stack>

      {/* Three feature cards */}
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg">
        <FeatureCard
          to="/finder"
          icon={<IconSearch size={28} />}
          iconColor="ember"
          title="Build Finder"
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Scegli skill, classe/ascendancy e contenuto: FOB interroga la ladder di poe.ninja e ti restituisce le build reali migliori, ordinate con uno score multidimensionale e filtrabili per vita/ES/EHP/DPS.",
            en: "Pick skill, class/ascendancy and content: FOB queries the poe.ninja ladder and returns the best real builds, ranked with a multi-dimensional score and filterable by life/ES/EHP/DPS.",
          })}
          example={t({
            it: "Elemental Hit + Slayer + Mapping → top 10 build reali",
            en: "Elemental Hit + Slayer + Mapping → top 10 real builds",
          })}
        />
        <FeatureCard
          to="/analyze"
          icon={<IconTool size={28} />}
          iconColor="violet"
          title={t({ it: "Analizza PoB", en: "Analyse PoB" })}
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Incolla un codice PoB o un link pobb.in / pastebin. FOB estrae classe, ascendancy, skill principale, item chiave, profilo difensivo e damage profile.",
            en: "Paste a PoB code or a pobb.in / pastebin link. FOB extracts class, ascendancy, main skill, key items, defensive profile and damage profile.",
          })}
          example="https://pobb.in/Sit6hlQU1uuZ"
        />
        <FeatureCard
          to="/planner"
          icon={<IconListCheck size={28} />}
          iconColor="grape"
          title="Planner"
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Dal PoB al piano upgrade in 6 fasi (Early/Mid/End Campaign + Early/End Mapping + High Investment) con prezzi live, gem progression e trigger per avanzare.",
            en: "From PoB to a 6-stage upgrade plan (Early/Mid/End Campaign + Early/End Mapping + High Investment) with live prices, gem progression and triggers to advance.",
          })}
          example="Early Campaign → Mid Campaign → ... → High Investment"
        />
      </SimpleGrid>

      {/* What you can do — quick examples */}
      <Card p="lg" bg="rgba(200, 147, 42, 0.06)">
        <Stack gap="sm">
          <Title order={4}>
            {t({ it: "Cosa ci puoi fare in pratica", en: "What you can do with it" })}
          </Title>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                {t({
                  it: "Trovare una build per la tua lega (Finder):",
                  en: "Find a build for your league (Finder):",
                })}
              </Text>{" "}
              {t({
                it: "scegli skill, classe e contenuto (es. Elemental Hit + Slayer + Mapping), aggiungi i minimi di vita/EHP/DPS che pretendi → top 10 build reali dalla ladder, con score spiegato.",
                en: "pick skill, class and content (e.g. Elemental Hit + Slayer + Mapping), add the life/EHP/DPS floors you demand → top 10 real ladder builds, with an explained score.",
              })}
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                {t({
                  it: "Capire una build al volo (Analizza):",
                  en: "Understand a build at a glance (Analyze):",
                })}
              </Text>{" "}
              {t({
                it: "incolla un PoB / pobb.in / URL poe.ninja — o premi “Analizza” su un risultato del Finder — e vedi equip, gemme, statistiche chiave e albero senza aprire Path of Building.",
                en: "paste a PoB / pobb.in / poe.ninja URL — or hit “Analyze” on a Finder result — and see gear, gems, key stats and tree without opening Path of Building.",
              })}
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                {t({
                  it: "Pianificare il day-0 al day-100 (Planner):",
                  en: "Plan day-0 to day-100 (Planner):",
                })}
              </Text>{" "}
              {t({
                it: "da un PoB (o da “Pianifica” sul Finder) ottieni 6 fasi con gli item da indossare, gem progression, prezzi live e un codice PoB importabile per ogni fase.",
                en: "from a PoB (or “Plan” on a Finder result) you get 6 stages with the items to wear, gem progression, live prices and an importable PoB code per stage.",
              })}
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                {t({
                  it: "Capire se una build è alla tua portata:",
                  en: "See whether a build is within reach:",
                })}
              </Text>{" "}
              {t({
                it: 'nel Planner il costo totale stimato è la somma dei budget per fase. Se il "High Investment" è 800 div, sai cosa ti aspetta prima di iniziare.',
                en: 'in the Planner the total estimated cost is the sum of the per-stage budgets. If "High Investment" is 800 div, you know what to expect before you start.',
              })}
            </Text>
          </SimpleGrid>
        </Stack>
      </Card>

      {/* Support card */}
      <Card
        p="lg"
        style={{
          borderColor: "rgba(232, 168, 50, 0.4)",
          background:
            "linear-gradient(135deg, rgba(200, 147, 42, 0.08) 0%, rgba(232, 168, 50, 0.06) 100%)",
        }}
      >
        <Group justify="space-between" wrap="wrap" gap="md">
          <Group gap="md" style={{ flex: 1, minWidth: 280 }}>
            <ThemeIcon variant="light" color="ember" size={48} radius="md">
              <IconHeart size={28} />
            </ThemeIcon>
            <Stack gap={4} style={{ flex: 1 }}>
              <Title order={4} style={{ margin: 0 }}>
                {t({ it: "Ti piace FOB?", en: "Enjoying FOB?" })}
              </Title>
              <Text size="sm" c="dimmed">
                {t({
                  it: "È un progetto personale. Mantenerlo aggiornato ogni lega richiede tempo: se ti è utile, considera un piccolo gesto.",
                  en: "It's a personal project. Keeping it updated every league takes time — if you find it useful, consider a small gesture.",
                })}
              </Text>
            </Stack>
          </Group>
          <Button
            color="ember"
            size="md"
            rightSection={<IconArrowRight size={16} />}
            onClick={donation.open}
          >
            {t({ it: "Supporta", en: "Support" })}
          </Button>
        </Group>
      </Card>

      <Box ta="center" pt="md">
        <Text size="xs" c="dimmed">
          {t({
            it: "FOB v1 · Mirage League · open-source su GitHub",
            en: "FOB v1 · Mirage League · open-source on GitHub",
          })}
        </Text>
      </Box>

      <DonationModal opened={donationOpen} onClose={donation.close} />
    </Stack>
  );
}
