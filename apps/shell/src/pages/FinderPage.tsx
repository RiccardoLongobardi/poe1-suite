/**
 * FinderPage — the "Build Finder" flow, the oracle's interface.
 *
 * Step 1: user types a free-text query → POST /fob/extract-intent.
 * Step 2: parsed BuildIntent shown; user presses "Trova build"
 *         → POST /fob/recommend → ranked build list.
 *
 * Step 22b redesign: a centred hero search that collapses after
 * submit, a horizontal filter-pill row, a two-column results + meta
 * sidebar layout, staggered card reveal, and an oracle empty state.
 */

import {
  Alert,
  Anchor,
  Box,
  Button,
  Code,
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
import { IconEye } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { extractIntent, recommend } from "../api/fob";
import type { BuildIntent, RecommendResponse, SortKey } from "../api/types";
import { BuildCard } from "../components/BuildCard";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { IntentCard } from "../components/IntentCard";
import { PopulationStatsPanel } from "../components/PopulationStatsPanel";

// Class & ascendancy options for the filter Select.
//
// Mantine v7's grouped-data shape: `[{group, items: [{value, label}]}]`.
// A flat array with a per-item `group` field crashes v7 on the internal
// `useMemo` before render (QA 2026-05-15). Values match the backend enum.
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

/** Subset of BuildIntent fields editable via the manual filter UI.
 * Kept in a separate state slice so editing them never overwrites the
 * parsed intent's other dimensions. */
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

/** Centred placeholder shown before any search has been run. */
function OracleEmptyState() {
  return (
    <Stack align="center" gap={6} py={48}>
      <IconEye size={48} color="var(--vs-ember-border)" stroke={1.4} />
      <Text fw={600} size="lg" style={{ fontFamily: "'Cinzel', serif" }}>
        L'oracolo attende la tua domanda
      </Text>
      <Text size="sm" c="dimmed" ta="center" maw={420}>
        Descrivi il build che cerchi — classe, skill, budget, contenuto.
      </Text>
    </Stack>
  );
}

export function FinderPage({ onSendToPlanner }: Props) {
  const [query, setQuery] = useState("");
  const [topN, setTopN] = useState<number>(10);
  const [intent, setIntent] = useState<BuildIntent | null>(null);
  const [overrides, setOverrides] = useState<FilterOverrides>(emptyOverrides());
  const [result, setResult] = useState<RecommendResponse | null>(null);
  // The hero search collapses to a compact row after a successful
  // extract; "modifica" expands it again.
  const [editing, setEditing] = useState(true);

  const extractMut = useMutation({
    mutationFn: () => extractIntent(query),
    onSuccess: (data) => {
      setIntent(data);
      setOverrides(overridesFromIntent(data));
      setResult(null);
      setEditing(false);
    },
  });

  const recommendMut = useMutation({
    mutationFn: () => recommend(applyOverrides(intent!, overrides), topN),
    onSuccess: setResult,
  });

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
    <Stack gap="lg">
      {/* ── Hero search / collapsed query row ───────────────────────── */}
      {editing ? (
        <Stack align="center" gap="sm" py="md">
          <Title order={2} ta="center">
            Consulta l'oracolo
          </Title>
          <Text c="dimmed" ta="center" size="sm" maw={520}>
            Descrivi il build che cerchi in italiano o inglese — es.{" "}
            <em>"cold self-cast per mapping, budget basso"</em>
          </Text>
          <Textarea
            w="100%"
            maw={620}
            placeholder="cerca RF con 6k life almeno..."
            value={query}
            onChange={(e) => setQuery(e.currentTarget.value)}
            minRows={2}
            autosize
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleExtract();
            }}
          />
          <Button
            size="md"
            onClick={handleExtract}
            loading={extractMut.isPending}
            disabled={!query.trim()}
          >
            Consulta l'Oracolo
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
            onClick={() => setEditing(true)}
            style={{ flexShrink: 0 }}
          >
            modifica
          </Anchor>
        </Group>
      )}

      {extractMut.isError && (
        <Alert color="red" title="Errore extract-intent">
          {extractMut.error.message}
        </Alert>
      )}

      {/* ── Parsed intent + filters + results ───────────────────────── */}
      {intent && (
        <ErrorBoundary label="Errore nel pannello Finder">
          <ErrorBoundary label="Errore nel riepilogo intent">
            <IntentCard intent={applyOverrides(intent, overrides)} />
          </ErrorBoundary>

          {/* Filter pill row — scrolls horizontally on mobile. */}
          <div className="finder-filter-row">
            <Select
              label="Classe / Asc."
              placeholder="Qualsiasi"
              data={CLASS_OPTIONS}
              value={overrides.class_filter}
              onChange={(v) => patchOverrides({ class_filter: v })}
              clearable
              searchable
              size="xs"
              w={170}
            />
            <Select
              label="Ordina"
              data={SORT_OPTIONS}
              value={overrides.sort_by}
              onChange={(v) => patchOverrides({ sort_by: (v as SortKey) ?? "score" })}
              allowDeselect={false}
              size="xs"
              w={130}
            />
            <NumberInput
              label="Min Vita"
              placeholder="5000"
              value={overrides.min_life ?? ""}
              onChange={(v) =>
                patchOverrides({ min_life: typeof v === "number" ? v : null })
              }
              min={0}
              step={500}
              thousandSeparator=","
              size="xs"
              w={110}
            />
            <NumberInput
              label="Min ES"
              placeholder="3000"
              value={overrides.min_es ?? ""}
              onChange={(v) =>
                patchOverrides({ min_es: typeof v === "number" ? v : null })
              }
              min={0}
              step={500}
              thousandSeparator=","
              size="xs"
              w={110}
            />
            <NumberInput
              label="Min EHP"
              placeholder="8000"
              value={overrides.min_ehp ?? ""}
              onChange={(v) =>
                patchOverrides({ min_ehp: typeof v === "number" ? v : null })
              }
              min={0}
              step={1000}
              thousandSeparator=","
              size="xs"
              w={110}
            />
            <NumberInput
              label="Min DPS"
              placeholder="500000"
              value={overrides.min_dps ?? ""}
              onChange={(v) =>
                patchOverrides({ min_dps: typeof v === "number" ? v : null })
              }
              min={0}
              step={100_000}
              thousandSeparator=","
              size="xs"
              w={120}
            />
            <NumberInput
              label="Min Lv"
              placeholder="90"
              value={overrides.min_level ?? ""}
              onChange={(v) =>
                patchOverrides({ min_level: typeof v === "number" ? v : null })
              }
              min={1}
              max={100}
              size="xs"
              w={90}
            />
            <NumberInput
              label="Max Lv"
              placeholder="100"
              value={overrides.max_level ?? ""}
              onChange={(v) =>
                patchOverrides({ max_level: typeof v === "number" ? v : null })
              }
              min={1}
              max={100}
              size="xs"
              w={90}
            />
            <NumberInput
              label="Risultati"
              value={topN}
              onChange={(v) => setTopN(typeof v === "number" ? v : 10)}
              min={1}
              max={50}
              size="xs"
              w={90}
            />
            <Button
              size="xs"
              onClick={handleRecommend}
              loading={recommendMut.isPending}
            >
              Trova build →
            </Button>
            <Button
              size="xs"
              variant="subtle"
              color="gray"
              onClick={() => setOverrides(emptyOverrides())}
            >
              Reset
            </Button>
          </div>

          {recommendMut.isError && (
            <Alert color="red" title="Errore recommend">
              {recommendMut.error.message}
            </Alert>
          )}

          {/* Two-column: results (2fr) + meta sidebar (1fr). */}
          <div className="finder-grid">
            {/* Results column */}
            <div>
              {recommendMut.isPending ? (
                <Box ta="center" py="xl">
                  <Loader />
                </Box>
              ) : result ? (
                <ErrorBoundary label="Errore nel rendering dei risultati">
                  {(() => {
                    const ranked = result.ranked ?? [];
                    return (
                      <Stack gap="xs">
                        <Divider
                          label={
                            <Text size="sm" fw={500}>
                              Top {ranked.length} builds su{" "}
                              {(result.total_candidates ?? 0).toLocaleString()}{" "}
                              candidati
                            </Text>
                          }
                        />
                        {ranked.map((b, i) => (
                          <BuildCard
                            key={b.ref.source_id}
                            build={b}
                            index={i}
                            onSendToPlanner={onSendToPlanner}
                          />
                        ))}
                        {ranked.length === 0 && (
                          <Text c="dimmed" ta="center" py="xl">
                            Nessun candidato supera i filtri hard-constraint.
                          </Text>
                        )}
                      </Stack>
                    );
                  })()}
                </ErrorBoundary>
              ) : (
                <OracleEmptyState />
              )}
            </div>

            {/* Meta sidebar — population stats. Above results on mobile. */}
            <div className="finder-sidebar">
              <ErrorBoundary label="Errore nelle statistiche di popolazione">
                <PopulationStatsPanel ascendancy={overrides.class_filter} />
              </ErrorBoundary>
            </div>
          </div>
        </ErrorBoundary>
      )}

      {/* Empty state before any search has been run. */}
      {!intent && !extractMut.isPending && <OracleEmptyState />}
    </Stack>
  );
}
