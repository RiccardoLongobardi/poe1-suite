/**
 * TheorycrafterPage — `/theorycrafter`, the build-from-scratch tool.
 *
 * Step 38 ships Pillar 1 only: the rule-based Build Generator. The user
 * describes the build they want in natural language; the backend
 * extracts an intent, ranks the poe.ninja ladder, and returns the
 * best-fit real build reformatted as a clean skeleton.
 *
 * The skeleton is *anchored on a real ladder character* — nothing is
 * invented. `source_*` fields link out to the original poe.ninja
 * profile so the user can verify it.
 */

import {
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Code,
  Divider,
  Group,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconExternalLink, IconFlask, IconWand } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { generateBuild } from "../api/fob";
import type { TheoryBuildSkeleton } from "../api/types";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { useT } from "../i18n";
import { usePageStore } from "../store/pageStore";

/** Compact ember badge for one budget tier. */
function tierLabel(tier: string): string {
  return tier.replace("_", " ");
}

function SkeletonCard({ skeleton }: { skeleton: TheoryBuildSkeleton }) {
  const t = useT();
  return (
    <Card withBorder padding="lg" className="vs-card-reveal">
      <Stack gap="md">
        {/* Identity */}
        <Group gap="sm" wrap="wrap">
          <Badge size="lg" color="ember" variant="filled">
            {skeleton.character_class}
            {skeleton.ascendancy ? ` · ${skeleton.ascendancy}` : ""}
          </Badge>
          <Badge size="lg" color="ember" variant="light" leftSection={<IconWand size={14} />}>
            {skeleton.main_skill}
          </Badge>
          <Badge size="lg" variant="default">
            {t({ it: "Livello", en: "Level" })} {skeleton.level}
          </Badge>
        </Group>

        <Text size="sm" c="dimmed">
          {skeleton.rationale}
        </Text>

        {/* 6-link */}
        {skeleton.support_gems.length > 0 && (
          <Box>
            <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={4}>
              {t({ it: "Collegamenti gemma", en: "Gem links" })}
            </Text>
            <Group gap={6}>
              <Badge color="ember" variant="filled">
                {skeleton.main_skill}
              </Badge>
              {skeleton.support_gems.map((g) => (
                <Badge key={g} variant="outline" color="gray">
                  {g}
                </Badge>
              ))}
            </Group>
          </Box>
        )}

        {/* Key uniques */}
        {skeleton.key_uniques.length > 0 && (
          <Box>
            <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={4}>
              {t({ it: "Oggetti unici chiave", en: "Key unique items" })}
            </Text>
            <Stack gap={4}>
              {skeleton.key_uniques.map((u) => (
                <Group key={`${u.slot}-${u.name}`} gap={8} wrap="nowrap">
                  <Badge size="sm" variant="light" color="ember" w={92}>
                    {tierLabel(u.tier)}
                  </Badge>
                  <Text size="sm" fw={600} style={{ color: "var(--vs-unique)" }}>
                    {u.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {u.slot}
                  </Text>
                </Group>
              ))}
            </Stack>
          </Box>
        )}

        {/* Tree milestones */}
        {skeleton.keystones.length > 0 && (
          <Box>
            <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={4}>
              {t({ it: "Keystone dell'albero", en: "Tree keystones" })} ·{" "}
              {skeleton.passive_count} {t({ it: "punti", en: "points" })}
            </Text>
            <Group gap={6}>
              {skeleton.keystones.map((k) => (
                <Badge key={k} variant="outline" color="ember">
                  {k}
                </Badge>
              ))}
            </Group>
          </Box>
        )}

        <Divider />
        <Group justify="space-between" wrap="wrap" gap="xs">
          <Text size="xs" c="dimmed">
            {t({
              it: "Scheletro derivato da una build reale in classifica:",
              en: "Skeleton derived from a real ladder build:",
            })}{" "}
            <Anchor href={skeleton.source_url} target="_blank" rel="noopener noreferrer">
              {skeleton.source_character}
              <IconExternalLink
                size={11}
                style={{ marginLeft: 3, verticalAlign: "-1px" }}
              />
            </Anchor>
          </Text>
          <Badge variant="default" size="sm">
            {skeleton.template_name}
          </Badge>
        </Group>
      </Stack>
    </Card>
  );
}

export function TheorycrafterPage() {
  const t = useT();
  const { query, result, editing } = usePageStore((s) => s.theory);
  const setTheory = usePageStore((s) => s.setTheory);

  const genMut = useMutation({
    mutationFn: () => generateBuild(query),
    onSuccess: (data) => setTheory({ result: data, editing: false }),
  });

  const handleGenerate = () => {
    if (!query.trim()) return;
    genMut.mutate();
  };

  return (
    <Stack gap="lg">
      {editing ? (
        <Stack align="center" gap="sm" py="md">
          <Title order={2} ta="center">
            {t({ it: "Theorycrafter", en: "Theorycrafter" })}
          </Title>
          <Text c="dimmed" ta="center" size="sm" maw={540}>
            {t({
              it: 'Descrivi la build che vuoi creare da zero — es. "build tanky con RF per tutti i contenuti" o "caster cold economico per mapping". Theorycrafter trova la build reale migliore e te la presenta come scheletro pronto.',
              en: 'Describe the build you want to create from scratch — e.g. "tanky RF build for all content" or "cheap cold caster for mapping". Theorycrafter finds the best real build and presents it as a ready skeleton.',
            })}
          </Text>
          <Textarea
            w="100%"
            maw={620}
            placeholder={t({
              it: "build tanky con RF per tutti i contenuti...",
              en: "tanky RF build for all content...",
            })}
            value={query}
            onChange={(e) => setTheory({ query: e.currentTarget.value })}
            minRows={2}
            autosize
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleGenerate();
            }}
          />
          <Button
            size="md"
            leftSection={<IconFlask size={16} />}
            onClick={handleGenerate}
            loading={genMut.isPending}
            disabled={!query.trim()}
          >
            {t({ it: "Genera build", en: "Generate build" })}
          </Button>
          <Text size="xs" c="dimmed">
            Ctrl+Enter
          </Text>
        </Stack>
      ) : (
        <Group gap={8} wrap="nowrap">
          <Code style={{ overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>
            {query}
          </Code>
          <Anchor
            size="xs"
            onClick={() => setTheory({ editing: true })}
            style={{ flexShrink: 0 }}
          >
            {t({ it: "modifica", en: "edit" })}
          </Anchor>
        </Group>
      )}

      {genMut.isError && (
        <Alert
          color="red"
          title={t({ it: "Errore generazione", en: "Generation error" })}
        >
          {genMut.error.message}
        </Alert>
      )}

      {genMut.isPending && (
        <Box className="vs-skeleton vs-skeleton-card" style={{ height: 260 }} />
      )}

      {!genMut.isPending && result && (
        <ErrorBoundary
          label={t({
            it: "Errore nel rendering dello scheletro",
            en: "Skeleton rendering error",
          })}
        >
          <SkeletonCard skeleton={result} />
        </ErrorBoundary>
      )}
    </Stack>
  );
}
