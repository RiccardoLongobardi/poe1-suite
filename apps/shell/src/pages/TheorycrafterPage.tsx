/**
 * TheorycrafterPage — `/theorycrafter`, the from-scratch Build Generator.
 *
 * Step 39. The user describes a build in natural language; the backend
 * synthesises a `BuildSkeleton` from vendored PoE 3.28 data (archetype
 * catalogue + passive tree + item bases). It never retrieves builds
 * from the poe.ninja ladder — that is the Build Finder's job.
 *
 * Pillar 1 only. The other three Theorycrafter pillars (item browser,
 * atlas, loot filter) are disabled placeholder tabs.
 */

import {
  Accordion,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  CopyButton,
  Group,
  Select,
  Stack,
  Tabs,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconCheck, IconCopy, IconFlask, IconWand } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import type { BuildSkeleton, GearSlot, SkeletonBudget } from "../api/types";
import { generateBuild } from "../api/fob";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { useLang, useT } from "../i18n";
import { usePageStore } from "../store/pageStore";

// Budget / focus option keys — labels resolved per-language in-component.
const BUDGET_KEYS: { value: SkeletonBudget; it: string; en: string }[] = [
  { value: "starter", it: "Inizio lega", en: "League start" },
  { value: "mid", it: "Medio", en: "Mid" },
  { value: "endgame", it: "Endgame", en: "Endgame" },
];
const FOCUS_KEYS: { value: string; it: string; en: string }[] = [
  { value: "mapping", it: "Mappatura", en: "Mapping" },
  { value: "bossing", it: "Boss", en: "Bossing" },
  { value: "allcontent", it: "Tutti i contenuti", en: "All content" },
  { value: "league", it: "Meccaniche di lega", en: "League mechanic" },
];

function SkeletonResult({ skeleton }: { skeleton: BuildSkeleton }) {
  const t = useT();
  const { lang } = useLang();
  const rationale = lang === "en" ? skeleton.rationale_en : skeleton.rationale_it;

  return (
    <Stack gap="md" className="vs-card-reveal">
      {/* Header */}
      <Card withBorder padding="md">
        <Group gap="sm" wrap="wrap">
          <Badge size="lg" color="ember" variant="filled">
            {skeleton.class_name} · {skeleton.ascendancy}
          </Badge>
          <Badge
            size="lg"
            color="ember"
            variant="light"
            leftSection={<IconWand size={14} />}
          >
            {skeleton.core_skill}
          </Badge>
          <Badge size="lg" variant="default">
            {skeleton.budget_tier}
          </Badge>
          <Badge size="lg" variant="default">
            {skeleton.content_focus}
          </Badge>
        </Group>
      </Card>

      {/* Gem links */}
      <Card withBorder padding="md">
        <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
          {t({ it: "Collegamenti gemma", en: "Gem links" })}
        </Text>
        <Stack gap="sm">
          {skeleton.links.map((link) => (
            <Group key={link.skill} gap={6} wrap="wrap">
              <Badge
                color="ember"
                variant="filled"
                className="vs-rarity"
                data-rarity="unique"
              >
                {link.skill}
              </Badge>
              {link.supports.map((s) => (
                <Badge key={s} variant="outline" color="gray">
                  {s}
                </Badge>
              ))}
            </Group>
          ))}
        </Stack>
      </Card>

      {/* Tree milestones */}
      <Card withBorder padding="md">
        <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
          {t({ it: "Tappe dell'albero passivo", en: "Passive tree milestones" })}
        </Text>
        <Stack gap={6}>
          {skeleton.tree_milestones.map((m, i) => (
            <Group key={`${m.priority}-${i}`} gap={8} wrap="nowrap" align="flex-start">
              <Badge size="sm" circle variant="light" color="ember">
                {m.priority}
              </Badge>
              <Box style={{ flex: 1, minWidth: 0 }}>
                <Text size="sm">{m.label}</Text>
                {m.node_ids.length > 0 && (
                  <Text size="10px" c="dimmed" className="mono">
                    node id: {m.node_ids.join(", ")}
                  </Text>
                )}
              </Box>
            </Group>
          ))}
        </Stack>
      </Card>

      {/* Gear slots */}
      <Card withBorder padding="md">
        <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
          {t({ it: "Slot equipaggiamento", en: "Gear slots" })}
        </Text>
        <Box
          style={{
            display: "grid",
            gap: 10,
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
          }}
        >
          {skeleton.gear_slots.map((g: GearSlot) => (
            <Box
              key={g.slot}
              style={{
                border: "1px solid var(--vs-border-faint)",
                borderRadius: 6,
                padding: 8,
              }}
            >
              <Text size="sm" fw={600}>
                {g.slot}
              </Text>
              {g.recommended_bases.length > 0 && (
                <Text size="xs" c="dimmed" mt={2}>
                  {g.recommended_bases.join(" · ")}
                </Text>
              )}
              <Group gap={4} mt={4}>
                {g.priority_stats.map((s) => (
                  <Badge key={s} size="xs" variant="light" color="ember">
                    {s}
                  </Badge>
                ))}
              </Group>
            </Box>
          ))}
        </Box>
      </Card>

      {/* Rationale */}
      <Accordion variant="separated">
        <Accordion.Item value="rationale">
          <Accordion.Control>
            {t({ it: "Perche questa build", en: "Why this build" })}
          </Accordion.Control>
          <Accordion.Panel>
            <Text size="sm">{rationale}</Text>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>

      {/* PoB import hint */}
      <Card withBorder padding="md">
        <Group justify="space-between" mb={4}>
          <Text size="xs" tt="uppercase" fw={700} c="dimmed">
            {t({ it: "Come importarla in PoB", en: "How to import into PoB" })}
          </Text>
          <CopyButton value={skeleton.pob_import_hint}>
            {({ copied, copy }) => (
              <Button
                size="compact-xs"
                variant="subtle"
                color={copied ? "teal" : "ember"}
                leftSection={
                  copied ? <IconCheck size={12} /> : <IconCopy size={12} />
                }
                onClick={copy}
              >
                {copied
                  ? t({ it: "Copiato", en: "Copied" })
                  : t({ it: "Copia", en: "Copy" })}
              </Button>
            )}
          </CopyButton>
        </Group>
        <Text size="xs" c="dimmed" style={{ whiteSpace: "pre-wrap" }}>
          {skeleton.pob_import_hint}
        </Text>
      </Card>
    </Stack>
  );
}

function BuildGeneratorPanel() {
  const t = useT();
  const { query, budgetTier, contentFocus, result } = usePageStore(
    (s) => s.theory,
  );
  const setTheory = usePageStore((s) => s.setTheory);

  const genMut = useMutation({
    mutationFn: () => generateBuild(query, budgetTier, contentFocus),
    onSuccess: (data) => setTheory({ result: data }),
  });

  const handleGenerate = () => {
    if (!query.trim()) return;
    setTheory({ result: null });
    genMut.mutate();
  };

  const budgetData = BUDGET_KEYS.map((b) => ({
    value: b.value,
    label: t({ it: b.it, en: b.en }),
  }));
  const focusData = FOCUS_KEYS.map((f) => ({
    value: f.value,
    label: t({ it: f.it, en: f.en }),
  }));

  return (
    <Stack gap="md">
      <Textarea
        label={t({ it: "Descrivi la tua build", en: "Describe your build" })}
        placeholder={t({
          it: "es. Elementalist con Fireball, mapping veloce",
          en: "e.g. Elementalist with Fireball, fast mapping",
        })}
        value={query}
        onChange={(e) => setTheory({ query: e.currentTarget.value })}
        minRows={2}
        autosize
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleGenerate();
        }}
      />
      <Group gap="sm" align="flex-end" wrap="wrap">
        <Select
          label={t({ it: "Budget", en: "Budget" })}
          data={budgetData}
          value={budgetTier}
          onChange={(v) =>
            setTheory({ budgetTier: (v as SkeletonBudget | null) ?? "mid" })
          }
          allowDeselect={false}
          w={160}
        />
        <Select
          label={t({ it: "Focus", en: "Focus" })}
          data={focusData}
          value={contentFocus}
          onChange={(v) => setTheory({ contentFocus: v ?? "mapping" })}
          allowDeselect={false}
          w={200}
        />
        <Button
          leftSection={<IconFlask size={16} />}
          onClick={handleGenerate}
          loading={genMut.isPending}
          disabled={!query.trim()}
        >
          {t({ it: "Genera", en: "Generate" })}
        </Button>
      </Group>

      {genMut.isError && (
        <Alert
          color="red"
          title={t({ it: "Errore di generazione", en: "Generation error" })}
        >
          {genMut.error.message}
        </Alert>
      )}

      {genMut.isPending && (
        <Box className="vs-skeleton vs-skeleton-card" style={{ height: 240 }} />
      )}

      {!genMut.isPending && result && (
        <ErrorBoundary
          label={t({
            it: "Errore nel rendering dello scheletro",
            en: "Skeleton rendering error",
          })}
        >
          <SkeletonResult skeleton={result} />
        </ErrorBoundary>
      )}
    </Stack>
  );
}

export function TheorycrafterPage() {
  const t = useT();
  return (
    <Stack gap="md">
      <Title order={2}>Theorycrafter</Title>
      <Text size="sm" c="dimmed" maw={620}>
        {t({
          it: "Descrivi la build che vuoi giocare e ricevi uno scheletro completo — costruito da zero con i dati ufficiali di PoE 3.28, non copiato dalla classifica.",
          en: "Describe the build you want to play and get a complete skeleton — built from scratch with official PoE 3.28 data, not copied from the ladder.",
        })}
      </Text>
      <Tabs defaultValue="genera" color="ember">
        <Tabs.List>
          <Tabs.Tab value="genera">
            {t({ it: "Genera build", en: "Generate build" })}
          </Tabs.Tab>
          <Tabs.Tab value="oggetti" disabled>
            {t({ it: "Oggetti & mod — in arrivo", en: "Items & mods — soon" })}
          </Tabs.Tab>
          <Tabs.Tab value="atlas" disabled>
            {t({ it: "Atlas — in arrivo", en: "Atlas — soon" })}
          </Tabs.Tab>
          <Tabs.Tab value="filter" disabled>
            {t({ it: "Loot filter — in arrivo", en: "Loot filter — soon" })}
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="genera" pt="md">
          <BuildGeneratorPanel />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}
