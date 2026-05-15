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
import { IntentCard } from "../components/IntentCard";
import { PopulationStatsPanel } from "../components/PopulationStatsPanel";

// Class & ascendancy options — keep flat for a single Select. Display
// labels are Title-Cased; values match the backend enum (lowercase).
const CLASS_OPTIONS: { value: string; label: string; group?: string }[] = [
  // Bare classes
  { value: "marauder", label: "Marauder", group: "Classi" },
  { value: "duelist", label: "Duelist", group: "Classi" },
  { value: "ranger", label: "Ranger", group: "Classi" },
  { value: "shadow", label: "Shadow", group: "Classi" },
  { value: "witch", label: "Witch", group: "Classi" },
  { value: "templar", label: "Templar", group: "Classi" },
  { value: "scion", label: "Scion", group: "Classi" },
  // Ascendancies
  { value: "juggernaut", label: "Juggernaut", group: "Marauder" },
  { value: "berserker", label: "Berserker", group: "Marauder" },
  { value: "chieftain", label: "Chieftain", group: "Marauder" },
  { value: "slayer", label: "Slayer", group: "Duelist" },
  { value: "gladiator", label: "Gladiator", group: "Duelist" },
  { value: "champion", label: "Champion", group: "Duelist" },
  { value: "deadeye", label: "Deadeye", group: "Ranger" },
  { value: "raider", label: "Raider", group: "Ranger" },
  { value: "pathfinder", label: "Pathfinder", group: "Ranger" },
  { value: "assassin", label: "Assassin", group: "Shadow" },
  { value: "saboteur", label: "Saboteur", group: "Shadow" },
  { value: "trickster", label: "Trickster", group: "Shadow" },
  { value: "necromancer", label: "Necromancer", group: "Witch" },
  { value: "occultist", label: "Occultist", group: "Witch" },
  { value: "elementalist", label: "Elementalist", group: "Witch" },
  { value: "inquisitor", label: "Inquisitor", group: "Templar" },
  { value: "hierophant", label: "Hierophant", group: "Templar" },
  { value: "guardian", label: "Guardian", group: "Templar" },
  { value: "ascendant", label: "Ascendant", group: "Scion" },
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

      {/* Parsed intent */}
      {intent && (
        <>
          <IntentCard intent={applyOverrides(intent, overrides)} />

          {/* Step 19 — population stats for the chosen ascendancy.
              Hidden when no class/ascendancy filter is active. */}
          <PopulationStatsPanel ascendancy={overrides.class_filter} />

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
        </>
      )}

      {/* Recommend error */}
      {recommendMut.isError && (
        <Alert color="red" title="Errore recommend">
          {recommendMut.error.message}
        </Alert>
      )}

      {/* Results */}
      {result && (
        <>
          <Divider
            label={
              <Text size="sm" fw={500}>
                Top {result.ranked.length} builds su{" "}
                {result.total_candidates.toLocaleString()} candidati
              </Text>
            }
          />

          {recommendMut.isPending && (
            <Box ta="center" py="xl">
              <Loader />
            </Box>
          )}

          <Stack gap="xs">
            {result.ranked.map((b) => (
              <BuildCard
                key={b.ref.source_id}
                build={b}
                onSendToPlanner={onSendToPlanner}
              />
            ))}
          </Stack>

          {result.ranked.length === 0 && (
            <Text c="dimmed" ta="center" py="xl">
              Nessun candidato supera i filtri hard-constraint.
            </Text>
          )}
        </>
      )}
    </Stack>
  );
}
