/**
 * FinderPage — the main "Build Finder" flow.
 *
 * Step 1: user types a free-text query → POST /fob/extract-intent
 * Step 2: parsed BuildIntent is shown; user presses "Find Builds"
 *         → POST /fob/recommend → ranked build list
 */

import {
  Alert,
  Box,
  Button,
  Collapse,
  Divider,
  Group,
  Loader,
  NumberInput,
  Select,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChevronDown, IconChevronUp, IconFilter } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { extractIntent, recommend } from "../api/fob";
import type {
  BuildIntent,
  RecommendResponse,
  SortKey,
} from "../api/types";
import { BuildCard } from "../components/BuildCard";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { IntentCard } from "../components/IntentCard";
import { PopulationStatsPanel } from "../components/PopulationStatsPanel";

// Class & ascendancy options for the filter Select.
//
// Mantine v7 changed the grouped-data shape: in v6 you could pass a flat
// array where each item carried a `group` field; in v7 you MUST pass
// `[{group, items: [{value, label}, ...]}, ...]` or the internal
// `useMemo` on the normalised data crashes with
// `TypeError: Cannot read properties of undefined (reading 'map')`
// before our render even runs (QA 2026-05-15: the second blank-page bug).
// Values match the backend enum (lowercase); display labels are Title-Case.
const CLASS_OPTIONS: { group: string; items: { value: string; label: string }[] }[] = [
  {
    group: "Classi",
    items: [
      { value: "marauder", label: "Marauder" },
      { value: "duelist", label: "Duelist" },
      { value: "ranger", label: "Ranger" },
      { value: "shadow", label: "Shadow" },
      { value: "witch", label: "Witch" },
      { value: "templar", label: "Templar" },
      { value: "scion", label: "Scion" },
    ],
  },
  {
    group: "Marauder",
    items: [
      { value: "juggernaut", label: "Juggernaut" },
      { value: "berserker", label: "Berserker" },
      { value: "chieftain", label: "Chieftain" },
    ],
  },
  {
    group: "Duelist",
    items: [
      { value: "slayer", label: "Slayer" },
      { value: "gladiator", label: "Gladiator" },
      { value: "champion", label: "Champion" },
    ],
  },
  {
    group: "Ranger",
    items: [
      { value: "deadeye", label: "Deadeye" },
      { value: "raider", label: "Raider" },
      { value: "pathfinder", label: "Pathfinder" },
    ],
  },
  {
    group: "Shadow",
    items: [
      { value: "assassin", label: "Assassin" },
      { value: "saboteur", label: "Saboteur" },
      { value: "trickster", label: "Trickster" },
    ],
  },
  {
    group: "Witch",
    items: [
      { value: "necromancer", label: "Necromancer" },
      { value: "occultist", label: "Occultist" },
      { value: "elementalist", label: "Elementalist" },
    ],
  },
  {
    group: "Templar",
    items: [
      { value: "inquisitor", label: "Inquisitor" },
      { value: "hierophant", label: "Hierophant" },
      { value: "guardian", label: "Guardian" },
    ],
  },
  {
    group: "Scion",
    items: [{ value: "ascendant", label: "Ascendant" }],
  },
];

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "score", label: "Score (fit)" },
  { value: "dps", label: "DPS ↓" },
  { value: "life", label: "Vita ↓" },
  { value: "ehp", label: "EHP ↓" },
  { value: "level", label: "Livello ↓" },
];

interface Props {
  onSendToPlanner?: (pobCode: string) => void;
}

/** Subset of BuildIntent fields the user can override via the manual
 * filter UI. We keep these in a separate slice of state so editing them
 * never overwrites the parsed intent's other dimensions. */
interface FilterOverrides {
  class_filter: string | null;
  sort_by: SortKey;
  min_life: number | null;
  min_es: number | null;
  min_ehp: number | null;
  min_dps: number | null;
  min_level: number | null;
  max_level: number | null;
}

function emptyOverrides(): FilterOverrides {
  return {
    class_filter: null,
    sort_by: "score",
    min_life: null,
    min_es: null,
    min_ehp: null,
    min_dps: null,
    min_level: null,
    max_level: null,
  };
}

function overridesFromIntent(intent: BuildIntent): FilterOverrides {
  return {
    class_filter: intent.class_filter,
    sort_by: intent.sort_by ?? "score",
    min_life: intent.min_life,
    min_es: intent.min_es,
    min_ehp: intent.min_ehp,
    min_dps: intent.min_dps,
    min_level: intent.min_level,
    max_level: intent.max_level,
  };
}

function applyOverrides(intent: BuildIntent, ov: FilterOverrides): BuildIntent {
  return {
    ...intent,
    class_filter: ov.class_filter,
    sort_by: ov.sort_by,
    min_life: ov.min_life,
    min_es: ov.min_es,
    min_ehp: ov.min_ehp,
    min_dps: ov.min_dps,
    min_level: ov.min_level,
    max_level: ov.max_level,
  };
}

export function FinderPage({ onSendToPlanner }: Props) {
  const [query, setQuery] = useState("");
  const [topN, setTopN] = useState<number>(10);
  const [intent, setIntent] = useState<BuildIntent | null>(null);
  const [overrides, setOverrides] = useState<FilterOverrides>(emptyOverrides());
  const [result, setResult] = useState<RecommendResponse | null>(null);
  const [filtersOpen, filterCtl] = useDisclosure(false);

  const extractMut = useMutation({
    mutationFn: () => extractIntent(query),
    onSuccess: (data) => {
      setIntent(data);
      setOverrides(overridesFromIntent(data));
      setResult(null);
    },
  });

  const recommendMut = useMutation({
    mutationFn: () => recommend(applyOverrides(intent!, overrides), topN),
    onSuccess: setResult,
  });

  // Open the filter panel whenever the parsed intent surfaces at least
  // one non-default filter — saves the user a click to see what was
  // extracted from their query.
  useEffect(() => {
    if (!intent) return;
    const ov = overridesFromIntent(intent);
    const hasAny =
      ov.class_filter ||
      ov.min_life !== null ||
      ov.min_es !== null ||
      ov.min_ehp !== null ||
      ov.min_dps !== null ||
      ov.min_level !== null ||
      ov.max_level !== null ||
      ov.sort_by !== "score";
    if (hasAny) filterCtl.open();
  }, [intent, filterCtl]);

  function patchOverrides(p: Partial<FilterOverrides>) {
    setOverrides((cur) => ({ ...cur, ...p }));
  }

  const handleExtract = () => {
    if (!query.trim()) return;
    extractMut.mutate();
  };

  const handleRecommend = () => {
    if (!intent) return;
    recommendMut.mutate();
  };

  return (
    <Stack gap="md">
      <Title order={3}>Build Finder</Title>
      <Text c="dimmed" size="sm">
        Descrivi la build che cerchi in italiano o inglese. Es.:&nbsp;
        <em>"cold self-cast per mapping, budget basso"</em>
      </Text>

      {/* Query input */}
      <Textarea
        placeholder="cold mapping ssf, no minion, budget basso..."
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        minRows={2}
        autosize
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleExtract();
        }}
      />

      <Group>
        <Button
          onClick={handleExtract}
          loading={extractMut.isPending}
          disabled={!query.trim()}
        >
          Analizza query
        </Button>
        <Text size="xs" c="dimmed">
          Ctrl+Enter
        </Text>
      </Group>

      {/* Extract error */}
      {extractMut.isError && (
        <Alert color="red" title="Errore extract-intent">
          {extractMut.error.message}
        </Alert>
      )}

      {/* Parsed intent — wrapped in a top-level ErrorBoundary so that
          ANY render error in this subtree (intent card, population
          panel, filter Select, NumberInputs, …) shows an inline alert
          instead of unmounting the whole page (QA 2026-05-15). */}
      {intent && (
        <ErrorBoundary label="Errore nel pannello Finder">
          <ErrorBoundary label="Errore nel riepilogo intent">
            <IntentCard intent={applyOverrides(intent, overrides)} />
          </ErrorBoundary>

          {/* Step 19 — population stats for the chosen ascendancy.
              Hidden when no class/ascendancy filter is active. */}
          <ErrorBoundary label="Errore nelle statistiche di popolazione">
            <PopulationStatsPanel ascendancy={overrides.class_filter} />
          </ErrorBoundary>

          {/* Manual filter overrides (collapsible) */}
          <Group justify="space-between" align="center">
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconFilter size={14} />}
              rightSection={
                filtersOpen ? (
                  <IconChevronUp size={14} />
                ) : (
                  <IconChevronDown size={14} />
                )
              }
              onClick={filterCtl.toggle}
            >
              {filtersOpen ? "Nascondi filtri" : "Filtri avanzati"}
            </Button>
            {(overrides.class_filter ||
              overrides.min_life ||
              overrides.min_es ||
              overrides.min_ehp ||
              overrides.min_dps ||
              overrides.min_level ||
              overrides.max_level ||
              (overrides.sort_by && overrides.sort_by !== "score")) && (
              <Button
                size="xs"
                variant="subtle"
                color="gray"
                onClick={() => setOverrides(emptyOverrides())}
              >
                Reset filtri
              </Button>
            )}
          </Group>

          <Collapse in={filtersOpen}>
            <Stack gap="xs" p="xs" style={{ background: "var(--mantine-color-dark-7)", borderRadius: 8 }}>
              <Group grow>
                <Select
                  label="Classe / Ascendency"
                  placeholder="Qualsiasi"
                  data={CLASS_OPTIONS}
                  value={overrides.class_filter}
                  onChange={(v) => patchOverrides({ class_filter: v })}
                  clearable
                  searchable
                />
                <Select
                  label="Ordina per"
                  data={SORT_OPTIONS}
                  value={overrides.sort_by}
                  onChange={(v) =>
                    patchOverrides({ sort_by: (v as SortKey) ?? "score" })
                  }
                  allowDeselect={false}
                />
              </Group>
              <Group grow>
                <NumberInput
                  label="Min Vita"
                  placeholder="es. 5000"
                  value={overrides.min_life ?? ""}
                  onChange={(v) =>
                    patchOverrides({
                      min_life: typeof v === "number" ? v : null,
                    })
                  }
                  min={0}
                  step={500}
                  thousandSeparator=","
                />
                <NumberInput
                  label="Min ES"
                  placeholder="es. 3000"
                  value={overrides.min_es ?? ""}
                  onChange={(v) =>
                    patchOverrides({
                      min_es: typeof v === "number" ? v : null,
                    })
                  }
                  min={0}
                  step={500}
                  thousandSeparator=","
                />
                <NumberInput
                  label="Min EHP"
                  placeholder="es. 8000"
                  value={overrides.min_ehp ?? ""}
                  onChange={(v) =>
                    patchOverrides({
                      min_ehp: typeof v === "number" ? v : null,
                    })
                  }
                  min={0}
                  step={1000}
                  thousandSeparator=","
                />
                <NumberInput
                  label="Min DPS"
                  placeholder="es. 500000"
                  value={overrides.min_dps ?? ""}
                  onChange={(v) =>
                    patchOverrides({
                      min_dps: typeof v === "number" ? v : null,
                    })
                  }
                  min={0}
                  step={100_000}
                  thousandSeparator=","
                />
              </Group>
              <Group grow>
                <NumberInput
                  label="Min Livello"
                  placeholder="es. 90"
                  value={overrides.min_level ?? ""}
                  onChange={(v) =>
                    patchOverrides({
                      min_level: typeof v === "number" ? v : null,
                    })
                  }
                  min={1}
                  max={100}
                />
                <NumberInput
                  label="Max Livello"
                  placeholder="es. 100"
                  value={overrides.max_level ?? ""}
                  onChange={(v) =>
                    patchOverrides({
                      max_level: typeof v === "number" ? v : null,
                    })
                  }
                  min={1}
                  max={100}
                />
              </Group>
            </Stack>
          </Collapse>

          <Group>
            <NumberInput
              label="Risultati"
              value={topN}
              onChange={(v) => setTopN(typeof v === "number" ? v : 10)}
              min={1}
              max={50}
              w={90}
            />
            <Button
              mt="xl"
              onClick={handleRecommend}
              loading={recommendMut.isPending}
              color="teal"
            >
              Trova build →
            </Button>
          </Group>
        </ErrorBoundary>
      )}

      {/* Recommend error */}
      {recommendMut.isError && (
        <Alert color="red" title="Errore recommend">
          {recommendMut.error.message}
        </Alert>
      )}

      {/* Results */}
      {result && (
        <ErrorBoundary label="Errore nel rendering dei risultati">
          {(() => {
            const ranked = result.ranked ?? [];
            return (
              <>
                <Divider
                  label={
                    <Text size="sm" fw={500}>
                      Top {ranked.length} builds su{" "}
                      {(result.total_candidates ?? 0).toLocaleString()} candidati
                    </Text>
                  }
                />

                {recommendMut.isPending && (
                  <Box ta="center" py="xl">
                    <Loader />
                  </Box>
                )}

                <Stack gap="xs">
                  {ranked.map((b) => (
                    <BuildCard
                      key={b.ref.source_id}
                      build={b}
                      onSendToPlanner={onSendToPlanner}
                    />
                  ))}
                </Stack>

                {ranked.length === 0 && (
                  <Text c="dimmed" ta="center" py="xl">
                    Nessun candidato supera i filtri hard-constraint.
                  </Text>
                )}
              </>
            );
          })()}
        </ErrorBoundary>
      )}
    </Stack>
  );
}
