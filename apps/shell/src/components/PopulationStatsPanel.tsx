/**
 * PopulationStatsPanel — Step 19 enrichment for the Build Finder.
 *
 * Renders aggregated poe.ninja ladder stats for a chosen ascendancy:
 *   - top 3 main skills with percentage share
 *   - life / EHP / DPS percentile bands (p25 / p50 / p75 / p90)
 *
 * Fetched lazily when an ascendancy filter is set; cached per-page-load
 * via TanStack Query so re-renders don't refetch.
 */

import {
  Badge,
  Card,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { IconChartHistogram, IconTrophy } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { getPopulationStats } from "../api/builds";
import type { StatDistribution } from "../api/types";
import { useT } from "../i18n";

interface Props {
  /** Ascendancy filter from the Finder. null/undefined disables the panel. */
  ascendancy: string | null | undefined;
}

function compactNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function DistributionRow({
  label,
  dist,
  noData,
}: {
  label: string;
  dist: StatDistribution | null;
  noData: string;
}) {
  if (!dist) {
    return (
      <Table.Tr>
        <Table.Td>{label}</Table.Td>
        <Table.Td colSpan={4} ta="center">
          <Text size="xs" c="dimmed" fs="italic">
            {noData}
          </Text>
        </Table.Td>
      </Table.Tr>
    );
  }
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="sm" fw={500}>
          {label}
        </Text>
      </Table.Td>
      <Table.Td ta="right">
        <Text size="sm" c="dimmed">
          {compactNumber(dist.p25)}
        </Text>
      </Table.Td>
      <Table.Td ta="right">
        <Text size="sm" fw={600}>
          {compactNumber(dist.p50)}
        </Text>
      </Table.Td>
      <Table.Td ta="right">
        <Text size="sm" c="dimmed">
          {compactNumber(dist.p75)}
        </Text>
      </Table.Td>
      <Table.Td ta="right">
        <Text size="sm" c="dimmed">
          {compactNumber(dist.p90)}
        </Text>
      </Table.Td>
    </Table.Tr>
  );
}

export function PopulationStatsPanel({ ascendancy }: Props) {
  const t = useT();
  const enabled = !!ascendancy && ascendancy.trim().length > 0;
  // Capitalise: backend matches poe.ninja's "Slayer" rather than "slayer".
  const ascCapitalised = ascendancy
    ? ascendancy.charAt(0).toUpperCase() + ascendancy.slice(1).toLowerCase()
    : null;
  const query = useQuery({
    queryKey: ["population-stats", ascCapitalised],
    queryFn: () => getPopulationStats(ascCapitalised),
    enabled,
    // Population stats refresh slowly — keep a session-long cache.
    staleTime: 10 * 60 * 1000,
  });

  if (!enabled) return null;
  if (query.isPending) {
    return (
      <Card withBorder radius="md" p="md">
        <Group gap={8}>
          <Loader size="xs" />
          <Text size="sm" c="dimmed">
            {t({
              it: `Carico le statistiche di popolazione per ${ascCapitalised}…`,
              en: `Loading population stats for ${ascCapitalised}…`,
            })}
          </Text>
        </Group>
      </Card>
    );
  }
  if (query.isError || !query.data) {
    return (
      <Card withBorder radius="md" p="md">
        <Text size="sm" c="red">
          {t({
            it: "Errore nel caricamento delle statistiche di popolazione.",
            en: "Failed to load population stats.",
          })}
        </Text>
      </Card>
    );
  }
  const stats = query.data;
  // Defensive: server returns these as arrays, but defend against
  // partial payloads (older deploys, broken caches, etc.) so a
  // missing field doesn't crash the whole Finder page.
  const topSkills = stats.top_skills ?? [];
  if (stats.total_builds === 0) {
    return (
      <Card withBorder radius="md" p="md">
        <Text size="sm" c="dimmed">
          {t({
            it: `Nessun build ${ascCapitalised} trovato nella ladder corrente.`,
            en: `No ${ascCapitalised} build found in the current ladder.`,
          })}
        </Text>
      </Card>
    );
  }

  return (
    <Card withBorder radius="md" p="md">
      <Stack gap="sm">
        <Group justify="space-between" align="center">
          <Group gap={8}>
            <ThemeIcon variant="light" color="ember" size="md" radius="md">
              <IconChartHistogram size={16} />
            </ThemeIcon>
            <Title order={5}>
              {t({ it: "Popolazione ladder", en: "Ladder population" })} —{" "}
              {stats.ascendancy ??
                t({ it: "tutte le classi", en: "all classes" })}
            </Title>
          </Group>
          <Tooltip
            label={t({
              it: "Dati live da poe.ninja, cache 15 min",
              en: "Live data from poe.ninja, 15 min cache",
            })}
            withArrow
          >
            <Text size="xs" c="dimmed">
              {t({
                it: `${(stats.total_builds ?? 0).toLocaleString()} build nel campione`,
                en: `${(stats.total_builds ?? 0).toLocaleString()} builds in the sample`,
              })}
            </Text>
          </Tooltip>
        </Group>

        {/* Top skills */}
        {topSkills.length > 0 && (
          <Stack gap={6}>
            <Group gap={6}>
              <IconTrophy size={14} />
              <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
                {t({ it: "Top skill", en: "Top skills" })}
              </Text>
            </Group>
            <Group gap={6} wrap="wrap">
              {topSkills.slice(0, 5).map((s, i) => (
                <Tooltip
                  key={s.skill}
                  label={t({
                    it: `${s.count} build su ${stats.total_builds ?? 0}`,
                    en: `${s.count} builds of ${stats.total_builds ?? 0}`,
                  })}
                  withArrow
                >
                  <Badge
                    color={i === 0 ? "ember" : "gray"}
                    variant={i === 0 ? "filled" : "light"}
                    size="md"
                  >
                    {s.skill} · {s.pct}%
                  </Badge>
                </Tooltip>
              ))}
            </Group>
          </Stack>
        )}

        {/* Stat distributions */}
        <Stack gap={4}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
            {t({
              it: "Distribuzione stat (percentili)",
              en: "Stat distribution (percentiles)",
            })}
          </Text>
          <Table withTableBorder withColumnBorders striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Stat</Table.Th>
                <Table.Th ta="right">p25</Table.Th>
                <Table.Th ta="right">
                  {t({ it: "mediana", en: "median" })}
                </Table.Th>
                <Table.Th ta="right">p75</Table.Th>
                <Table.Th ta="right">p90</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              <DistributionRow
                label={t({ it: "Vita", en: "Life" })}
                dist={stats.life}
                noData={t({ it: "n/d", en: "no data" })}
              />
              <DistributionRow
                label="ES"
                dist={stats.energy_shield}
                noData={t({ it: "n/d", en: "no data" })}
              />
              <DistributionRow
                label="EHP"
                dist={stats.ehp}
                noData={t({ it: "n/d", en: "no data" })}
              />
              <DistributionRow
                label="DPS"
                dist={stats.dps}
                noData={t({ it: "n/d", en: "no data" })}
              />
              <DistributionRow
                label={t({ it: "Livello", en: "Level" })}
                dist={stats.level}
                noData={t({ it: "n/d", en: "no data" })}
              />
            </Table.Tbody>
          </Table>
        </Stack>
      </Stack>
    </Card>
  );
}
