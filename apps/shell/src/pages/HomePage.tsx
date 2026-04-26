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

interface FeatureCardProps {
  to: string;
  icon: ReactNode;
  iconColor: string;
  title: string;
  description: string;
  example?: string;
}

function FeatureCard({
  to,
  icon,
  iconColor,
  title,
  description,
  example,
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
              backgroundColor: "rgba(110, 38, 255, 0.08)",
              borderRadius: 8,
              borderLeft: "2px solid var(--astral-glow)",
            }}
          >
            {example}
          </Text>
        )}
        <Group justify="flex-end" mt="auto">
          <Text size="sm" c={iconColor} fw={500}>
            Apri →
          </Text>
        </Group>
      </Stack>
    </Card>
  );
}

export function HomePage() {
  const [donationOpen, donation] = useDisclosure(false);

  return (
    <Stack gap="xl" pb="xl">
      {/* Hero */}
      <Stack gap="xs" align="center" ta="center" pt="md" pb="md">
        <Badge variant="light" color="astral" size="lg">
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
            textShadow: "0 0 20px rgba(110, 38, 255, 0.3)",
          }}
        >
          Cosa stiamo costruendo oggi?
        </Title>
        <Text c="dimmed" size="md" maw={620}>
          FOB ti aiuta a scegliere una build, capire cosa fa, e pianificare
          l'upgrade dal day-0 al day-100 con i prezzi live di poe.ninja e GGG
          Trade.
        </Text>
      </Stack>

      {/* Three feature cards */}
      <SimpleGrid cols={{ base: 1, md: 3 }} spacing="lg">
        <FeatureCard
          to="/finder"
          icon={<IconSearch size={28} />}
          iconColor="astral"
          title="Build Finder"
          description={
            "Descrivi quello che cerchi in italiano o inglese. FOB legge l'intent, " +
            "interroga il ladder di poe.ninja e ti restituisce le build migliori " +
            "con score multidimensionale."
          }
          example='"voglio una cold dot comfy per mapping, budget 20 div"'
        />
        <FeatureCard
          to="/analyze"
          icon={<IconTool size={28} />}
          iconColor="violet"
          title="Analizza PoB"
          description={
            "Incolla un codice PoB o un link pobb.in / pastebin. FOB estrae " +
            "classe, ascendancy, skill principale, item chiave, profilo difensivo " +
            "e damage profile."
          }
          example="https://pobb.in/Sit6hlQU1uuZ"
        />
        <FeatureCard
          to="/planner"
          icon={<IconListCheck size={28} />}
          iconColor="grape"
          title="Planner"
          description={
            "Dal PoB al piano upgrade in 6 fasi (Early/Mid/End Campaign + Early/End " +
            "Mapping + High Investment) con prezzi live, gem progression e trigger " +
            "per avanzare."
          }
          example="Early Campaign → Mid Campaign → ... → High Investment"
        />
      </SimpleGrid>

      {/* What you can do — quick examples */}
      <Card p="lg" bg="rgba(110, 38, 255, 0.06)">
        <Stack gap="sm">
          <Title order={4}>Cosa ci puoi fare in pratica</Title>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                Trovare una build per la tua lega:
              </Text>{" "}
              "build tanky con CI per bossing, no minion" → top 10 build dal
              ladder filtrate sui tuoi vincoli.
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                Capire una guida che hai trovato:
              </Text>{" "}
              incolla il pobb.in e vedi subito che skill / ascendancy / item
              core ha. Niente Path of Building da aprire.
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                Pianificare il day-0 al day-100:
              </Text>{" "}
              il Planner ti dice cosa indossare in atto 1, atto 5, mid-campaign,
              prime maps, end-game con i prezzi live e l'ETA totale.
            </Text>
            <Text size="sm" c="dimmed">
              <Text component="span" fw={600} c="bright">
                Capire se una build è alla tua portata:
              </Text>{" "}
              il costo totale stimato è la somma dei budget per fase. Se il
              "High Investment" è 800 div, sai cosa ti aspetta.
            </Text>
          </SimpleGrid>
        </Stack>
      </Card>

      {/* Support card */}
      <Card
        p="lg"
        style={{
          borderColor: "rgba(255, 196, 15, 0.4)",
          background:
            "linear-gradient(135deg, rgba(110, 38, 255, 0.08) 0%, rgba(255, 196, 15, 0.06) 100%)",
        }}
      >
        <Group justify="space-between" wrap="wrap" gap="md">
          <Group gap="md" style={{ flex: 1, minWidth: 280 }}>
            <ThemeIcon variant="light" color="gold" size={48} radius="md">
              <IconHeart size={28} />
            </ThemeIcon>
            <Stack gap={4} style={{ flex: 1 }}>
              <Title order={4} style={{ margin: 0 }}>
                Ti piace FOB?
              </Title>
              <Text size="sm" c="dimmed">
                È un progetto personale. Mantenerlo aggiornato ogni lega
                richiede tempo: se ti è utile, considera un piccolo gesto.
              </Text>
            </Stack>
          </Group>
          <Button
            color="gold"
            size="md"
            rightSection={<IconArrowRight size={16} />}
            onClick={donation.open}
          >
            Supporta
          </Button>
        </Group>
      </Card>

      <Box ta="center" pt="md">
        <Text size="xs" c="dimmed">
          FOB v1 · Mirage League · ric.longobardi@outlook.it · open-source su
          GitHub
        </Text>
      </Box>

      <DonationModal opened={donationOpen} onClose={donation.close} />
    </Stack>
  );
}
