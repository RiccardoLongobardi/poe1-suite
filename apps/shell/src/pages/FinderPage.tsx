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
  Badge,
  Box,
  Button,
  Code,
  Group,
  NumberInput,
  Pill,
  Select,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { IconEye, IconSortDescending } from "@tabler/icons-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getPopulationStats } from "../api/builds";
import { extractIntent, recommend } from "../api/fob";
import type { BuildIntent, SortKey } from "../api/types";
import { BuildCard } from "../components/BuildCard";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { IntentCard } from "../components/IntentCard";
import { PopulationStatsPanel } from "../components/PopulationStatsPanel";
import { withViewTransition } from "../hooks/useViewTransition";
import { useT } from "../i18n";
import {
  emptyFinderFilters,
  type FinderFilters,
  usePageStore,
} from "../store/pageStore";

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

/** Sort options — labels resolved per-language inside the component. */
const SORT_KEYS: { value: SortKey; it: string; en: string }[] = [
  { value: "score", it: "Score (fit)", en: "Score (fit)" },
  { value: "dps", it: "DPS ↓", en: "DPS ↓" },
  { value: "life", it: "Vita ↓", en: "Life ↓" },
  { value: "ehp", it: "EHP ↓", en: "EHP ↓" },
  { value: "level", it: "Livello ↓", en: "Level ↓" },
];

interface Props {
  onSendToPlanner?: (pobCode: string) => void;
}

// The editable filter subset (`FinderFilters`) lives in the Zustand
// `pageStore` so it survives cross-route navigation. Kept separate
// from the parsed intent so editing a filter never clobbers the
// intent's other dimensions.

function overridesFromIntent(intent: BuildIntent): FinderFilters {
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

function applyOverrides(intent: BuildIntent, ov: FinderFilters): BuildIntent {
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
  const t = useT();
  return (
    <Stack align="center" gap={6} py={48}>
      <IconEye size={48} color="var(--vs-ember-border)" stroke={1.4} />
      <Text fw={600} size="lg" style={{ fontFamily: "'Cinzel', serif" }}>
        {t({
          it: "L'oracolo attende la tua domanda",
          en: "The oracle awaits your question",
        })}
      </Text>
      <Text size="sm" c="dimmed" ta="center" maw={420}>
        {t({
          it: "Descrivi il build che cerchi — classe, skill, budget, contenuto.",
          en: "Describe the build you want — class, skill, budget, content.",
        })}
      </Text>
    </Stack>
  );
}

export function FinderPage({ onSendToPlanner }: Props) {
  const t = useT();
  const sortOptions = SORT_KEYS.map((s) => ({
    value: s.value,
    label: t({ it: s.it, en: s.en }),
  }));
  // Cross-route persistent state — query, parsed intent, filter
  // overrides, results, drill-down skill filter and the editing flag
  // all survive navigating away and back (Zustand `pageStore`).
  const { query, topN, intent, overrides, result, skillFilter, editing } =
    usePageStore((s) => s.finder);
  const setFinder = usePageStore((s) => s.setFinder);

  const extractMut = useMutation({
    mutationFn: () => extractIntent(query),
    onSuccess: (data) => {
      setFinder({
        intent: data,
        overrides: overridesFromIntent(data),
        result: null,
        skillFilter: null,
        editing: false,
      });
    },
  });

  const recommendMut = useMutation({
    mutationFn: () => recommend(applyOverrides(intent!, overrides), topN),
    onSuccess: (data) => {
      setFinder({ result: data, skillFilter: null });
    },
  });

  // Population stats keyed on the active class filter — shares the
  // TanStack cache with <PopulationStatsPanel> (same query key), so
  // this adds no extra HTTP call. Capitalised to match poe.ninja's
  // ascendancy casing. Only fetched once a result set exists.
  const ascCapitalised = overrides.class_filter
    ? overrides.class_filter.charAt(0).toUpperCase() +
      overrides.class_filter.slice(1).toLowerCase()
    : null;
  const popQuery = useQuery({
    queryKey: ["population-stats", ascCapitalised],
    queryFn: () => getPopulationStats(ascCapitalised),
    enabled: !!result,
    staleTime: 10 * 60 * 1000,
  });
  // Map of lower-cased skill name → ladder share %, for the "X% of
  // meta" line on each BuildCard.
  const metaPct = useMemo(() => {
    const m = new Map<string, number>();
    for (const s of popQuery.data?.top_skills ?? []) {
      m.set(s.skill.trim().toLowerCase(), s.pct);
    }
    return m;
  }, [popQuery.data]);

  /** Toggle the drill-down skill filter (clicking the active one clears it). */
  function handleDrillSkill(skill: string) {
    // Micro-transition: the result list cross-fades between the full
    // set and the skill-filtered subset instead of jumping.
    withViewTransition(() => {
      setFinder({
        skillFilter:
          skillFilter && skillFilter.toLowerCase() === skill.toLowerCase()
            ? null
            : skill,
      });
    });
  }

  function patchOverrides(p: Partial<FinderFilters>) {
    setFinder({ overrides: { ...overrides, ...p } });
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
            {t({ it: "Consulta l'oracolo", en: "Consult the oracle" })}
          </Title>
          <Text c="dimmed" ta="center" size="sm" maw={520}>
            {t({
              it: 'Descrivi il build che cerchi in italiano o inglese — es. "cold self-cast per mapping, budget basso"',
              en: 'Describe the build you want in Italian or English — e.g. "cold self-cast for mapping, low budget"',
            })}
          </Text>
          <Textarea
            w="100%"
            maw={620}
            placeholder={t({
              it: "cerca RF con 6k life almeno...",
              en: "search RF with at least 6k life...",
            })}
            value={query}
            onChange={(e) => setFinder({ query: e.currentTarget.value })}
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
            {t({ it: "Consulta l'Oracolo", en: "Consult the Oracle" })}
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
            onClick={() => setFinder({ editing: true })}
            style={{ flexShrink: 0 }}
          >
            {t({ it: "modifica", en: "edit" })}
          </Anchor>
        </Group>
      )}

      {extractMut.isError && (
        <Alert color="red" title={t({ it: "Errore extract-intent", en: "Intent extraction error" })}>
          {extractMut.error.message}
        </Alert>
      )}

      {/* ── Parsed intent + filters + results ───────────────────────── */}
      {intent && (
        <ErrorBoundary label={t({ it: "Errore nel pannello Finder", en: "Finder panel error" })}>
          <ErrorBoundary label={t({ it: "Errore nel riepilogo intent", en: "Intent summary error" })}>
            <IntentCard intent={applyOverrides(intent, overrides)} />
          </ErrorBoundary>

          {/* Filter pill row — scrolls horizontally on mobile. */}
          <div className="finder-filter-row">
            <Select
              label={t({ it: "Classe / Asc.", en: "Class / Asc." })}
              placeholder={t({ it: "Qualsiasi", en: "Any" })}
              data={CLASS_OPTIONS}
              value={overrides.class_filter}
              onChange={(v) => patchOverrides({ class_filter: v })}
              clearable
              searchable
              size="xs"
              w={170}
            />
            <Select
              label={t({ it: "Ordina", en: "Sort" })}
              data={sortOptions}
              value={overrides.sort_by}
              onChange={(v) => patchOverrides({ sort_by: (v as SortKey) ?? "score" })}
              allowDeselect={false}
              size="xs"
              w={130}
            />
            <NumberInput
              label={t({ it: "Min Vita", en: "Min Life" })}
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
              label={t({ it: "Min DPS", en: "Min DPS" })}
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
              label={t({ it: "Min Lv", en: "Min Lv" })}
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
              label={t({ it: "Max Lv", en: "Max Lv" })}
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
              label={t({ it: "Risultati", en: "Results" })}
              value={topN}
              onChange={(v) =>
                setFinder({ topN: typeof v === "number" ? v : 10 })
              }
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
              {t({ it: "Trova build →", en: "Find builds →" })}
            </Button>
            <Button
              size="xs"
              variant="subtle"
              color="gray"
              onClick={() => setFinder({ overrides: emptyFinderFilters() })}
            >
              {t({ it: "Reset", en: "Reset" })}
            </Button>
          </div>

          {recommendMut.isError && (
            <Alert color="red" title={t({ it: "Errore recommend", en: "Recommend error" })}>
              {recommendMut.error.message}
            </Alert>
          )}

          {/* Two-column: results (2fr) + meta sidebar (1fr). */}
          <div className="finder-grid">
            {/* Results column */}
            <div>
              {recommendMut.isPending ? (
                <Stack gap="xs">
                  {[0, 1, 2, 3, 4].map((i) => (
                    <Box key={i} className="vs-skeleton vs-skeleton-card" />
                  ))}
                </Stack>
              ) : result ? (
                <ErrorBoundary label={t({ it: "Errore nel rendering dei risultati", en: "Results rendering error" })}>
                  {(() => {
                    const ranked = result.ranked ?? [];
                    const total = (result.total_candidates ?? 0).toLocaleString();
                    const displayed = skillFilter
                      ? ranked.filter(
                          (b) =>
                            (b.ref.main_skill ?? "").toLowerCase() ===
                            skillFilter.toLowerCase(),
                        )
                      : ranked;
                    const sortLabel =
                      SORT_KEYS.find((s) => s.value === overrides.sort_by) ??
                      SORT_KEYS[0];
                    return (
                      <Stack
                        gap="xs"
                        style={{ viewTransitionName: "finder-results" }}
                      >
                        {/* Result header: count + active sort + drill-down chip */}
                        <Group justify="space-between" wrap="wrap" gap="xs">
                          <Text size="sm" fw={500}>
                            {skillFilter
                              ? t({
                                  it: `${displayed.length} di ${ranked.length} build (filtro skill)`,
                                  en: `${displayed.length} of ${ranked.length} builds (skill filter)`,
                                })
                              : t({
                                  it: `Top ${ranked.length} build su ${total} candidati`,
                                  en: `Top ${ranked.length} builds of ${total} candidates`,
                                })}
                          </Text>
                          <Group gap={6}>
                            {overrides.sort_by !== "score" && (
                              <Badge
                                variant="light"
                                color="ember"
                                leftSection={<IconSortDescending size={12} />}
                              >
                                {t({
                                  it: `Ordinato per ${t({ it: sortLabel.it, en: sortLabel.en })}`,
                                  en: `Sorted by ${t({ it: sortLabel.it, en: sortLabel.en })}`,
                                })}
                              </Badge>
                            )}
                            {skillFilter && (
                              <Pill
                                withRemoveButton
                                size="md"
                                onRemove={() =>
                                  withViewTransition(() =>
                                    setFinder({ skillFilter: null }),
                                  )
                                }
                              >
                                {t({ it: "skill", en: "skill" })}: {skillFilter}
                              </Pill>
                            )}
                          </Group>
                        </Group>
                        {displayed.map((b, i) => (
                          <BuildCard
                            key={b.ref.source_id}
                            build={b}
                            index={i}
                            onSendToPlanner={onSendToPlanner}
                            metaPct={metaPct.get(
                              (b.ref.main_skill ?? "").toLowerCase(),
                            )}
                            onDrillSkill={handleDrillSkill}
                          />
                        ))}
                        {ranked.length === 0 && (
                          <Text c="dimmed" ta="center" py="xl">
                            {t({
                              it: "Nessun candidato supera i filtri hard-constraint.",
                              en: "No candidate passes the hard-constraint filters.",
                            })}
                          </Text>
                        )}
                        {ranked.length > 0 && displayed.length === 0 && (
                          <Text c="dimmed" ta="center" py="xl">
                            {t({
                              it: `Nessun build con la skill "${skillFilter}" nei risultati.`,
                              en: `No build with the "${skillFilter}" skill in the results.`,
                            })}
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
              <ErrorBoundary label={t({ it: "Errore nelle statistiche di popolazione", en: "Population stats error" })}>
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
