/**
 * HomePage v2 — "Obsidian Pro" landing dashboard.
 *
 * A professional-tool hero (headline + two primary CTAs), a 4-card
 * tool grid (Finder / Analyze / Planner / Theorycrafter), a concrete
 * "what you can do" section aligned with each tool's real behaviour,
 * and the support card.
 */

import {
  Badge,
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
  IconFlask,
  IconHeart,
  IconListCheck,
  IconSearch,
  IconTool,
} from "@tabler/icons-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { DonationModal } from "../components/DonationModal";
import { useT } from "../i18n";

interface ToolCardProps {
  to: string;
  icon: ReactNode;
  iconColor: string;
  title: string;
  description: string;
  example?: string;
  openLabel: string;
}

function ToolCard({
  to,
  icon,
  iconColor,
  title,
  description,
  example,
  openLabel,
}: ToolCardProps) {
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
          <ThemeIcon variant="light" color={iconColor} size={44} radius="md">
            {icon}
          </ThemeIcon>
          <Title order={3} style={{ margin: 0, fontSize: "1.15rem" }}>
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
              backgroundColor: "var(--vs-ember-dim)",
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
  const navigate = useNavigate();
  const t = useT();

  return (
    <Stack gap="xl" pb="xl">
      {/* ── Hero ──────────────────────────────────────────────────── */}
      <Stack gap="md" align="center" ta="center" pt={36} pb="md">
        <Badge variant="light" color="ember" size="lg">
          v2 — Mirage League
        </Badge>
        <Title
          order={1}
          style={{
            fontSize: "clamp(2rem, 5vw, 3rem)",
            lineHeight: 1.1,
            maxWidth: 760,
          }}
        >
          {t({
            it: "Gli strumenti seri per le tue build di Path of Exile",
            en: "The serious toolkit for your Path of Exile builds",
          })}
        </Title>
        <Text c="dimmed" size="lg" maw={640}>
          {t({
            it: "Cerca build reali dalla ladder, analizzale al volo, pianifica gli upgrade con i prezzi live e genera build da zero — con numeri calcolati dal vero motore di Path of Building.",
            en: "Search real ladder builds, analyse them at a glance, plan upgrades with live prices and generate builds from scratch — with numbers computed by the real Path of Building engine.",
          })}
        </Text>
        <Group gap="sm" mt={4}>
          <Button
            size="md"
            leftSection={<IconSearch size={18} />}
            onClick={() => navigate("/finder")}
          >
            {t({ it: "Trova una build", en: "Find a build" })}
          </Button>
          <Button
            size="md"
            variant="light"
            leftSection={<IconFlask size={18} />}
            onClick={() => navigate("/theorycrafter")}
          >
            {t({ it: "Genera una build", en: "Generate a build" })}
          </Button>
        </Group>
      </Stack>

      {/* ── Tool grid ─────────────────────────────────────────────── */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
        <ToolCard
          to="/finder"
          icon={<IconSearch size={26} />}
          iconColor="ember"
          title="Build Finder"
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Scegli skill, classe e contenuto: ti restituiamo le build reali migliori dalla ladder di poe.ninja, filtrabili per vita/ES/EHP/DPS.",
            en: "Pick skill, class and content: we return the best real builds from the poe.ninja ladder, filterable by life/ES/EHP/DPS.",
          })}
          example={t({
            it: "Elemental Hit + Slayer → top 10 build reali",
            en: "Elemental Hit + Slayer → top 10 real builds",
          })}
        />
        <ToolCard
          to="/analyze"
          icon={<IconTool size={26} />}
          iconColor="violet"
          title={t({ it: "Analizza", en: "Analyze" })}
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Incolla un PoB, un link pobb.in o un URL poe.ninja: equip, gemme, statistiche chiave e albero in una dashboard leggibile.",
            en: "Paste a PoB, a pobb.in link or a poe.ninja URL: gear, gems, key stats and tree in a readable dashboard.",
          })}
          example="https://pobb.in/Sit6hlQU1uuZ"
        />
        <ToolCard
          to="/planner"
          icon={<IconListCheck size={26} />}
          iconColor="grape"
          title="Planner"
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Da un PoB al piano upgrade in 6 fasi con prezzi live, gem progression e un codice PoB importabile per ogni fase.",
            en: "From a PoB to a 6-stage upgrade plan with live prices, gem progression and an importable PoB code per stage.",
          })}
          example="Early Campaign → … → High Investment"
        />
        <ToolCard
          to="/theorycrafter"
          icon={<IconFlask size={26} />}
          iconColor="teal"
          title="Theorycrafter"
          openLabel={t({ it: "Apri", en: "Open" })}
          description={t({
            it: "Genera una build completa da zero dai dati ufficiali del gioco — albero, gemme, equip — con DPS calcolati dal vero motore di PoB.",
            en: "Generate a complete build from scratch from official game data — tree, gems, gear — with DPS computed by the real PoB engine.",
          })}
          example={t({
            it: "Witch + Occultist + Vortex → build importabile",
            en: "Witch + Occultist + Vortex → importable build",
          })}
        />
      </SimpleGrid>

      {/* ── What you can do ───────────────────────────────────────── */}
      <Card p="lg" style={{ background: "var(--vs-surface-1)" }}>
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
                it: "scegli skill, classe e contenuto, aggiungi i minimi di vita/EHP/DPS che pretendi → top 10 build reali dalla ladder, con score spiegato.",
                en: "pick skill, class and content, add the life/EHP/DPS floors you demand → top 10 real ladder builds, with an explained score.",
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
                it: "incolla un PoB / pobb.in / URL poe.ninja — o premi “Analizza” su un risultato del Finder — senza aprire Path of Building.",
                en: "paste a PoB / pobb.in / poe.ninja URL — or hit “Analyze” on a Finder result — without opening Path of Building.",
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
                it: "da un PoB (o da “Pianifica” sul Finder) ottieni 6 fasi con item, gem progression, prezzi live e un PoB importabile per fase.",
                en: "from a PoB (or “Plan” on a Finder result) you get 6 stages with items, gem progression, live prices and an importable PoB per stage.",
              })}
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                {t({
                  it: "Generare una build tua (Theorycrafter):",
                  en: "Generate your own build (Theorycrafter):",
                })}
              </Text>{" "}
              {t({
                it: "classe + ascendancy + skill → una build completa e legale nella lega, ottimizzata e validata dal vero calcolo di PoB.",
                en: "class + ascendancy + skill → a complete, league-legal build, optimised and validated by PoB's real calculation.",
              })}
            </Text>
          </SimpleGrid>
        </Stack>
      </Card>

      {/* ── Support ───────────────────────────────────────────────── */}
      <Card
        p="lg"
        style={{
          borderColor: "var(--vs-ember-border)",
          background:
            "linear-gradient(135deg, var(--vs-ember-dim) 0%, transparent 70%)",
        }}
      >
        <Group justify="space-between" wrap="wrap" gap="md">
          <Group gap="md" style={{ flex: 1, minWidth: 280 }}>
            <ThemeIcon variant="light" color="ember" size={44} radius="md">
              <IconHeart size={26} />
            </ThemeIcon>
            <Stack gap={4} style={{ flex: 1 }}>
              <Title order={4} style={{ margin: 0 }}>
                {t({ it: "Ti piace FOB?", en: "Enjoying FOB?" })}
              </Title>
              <Text size="sm" c="dimmed">
                {t({
                  it: "È un progetto personale, gratuito e senza pubblicità. Se ti è utile, considera un piccolo gesto.",
                  en: "It's a personal project — free, no ads. If you find it useful, consider a small gesture.",
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

      <DonationModal opened={donationOpen} onClose={donation.close} />
    </Stack>
  );
}
