/**
 * FinderPage — the "Build Finder": structured ladder search.
 *
 * Structured-search rework (Step 86): the primary input is a concrete
 * search panel — skill picker (catalogue-derived list from
 * GET /fob/finder/skills), class/ascendancy, content focus, sort and
 * stat floors — and the BuildIntent is built client-side from those
 * fields. No more natural-language query, no parsing confidence: what
 * you select is exactly what is searched.
 */

import {
  Alert,
  Badge,
  Box,
  Button,
  Group,
  NumberInput,
  Pill,
  Select,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconSearch, IconSortDescending } from "@tabler/icons-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { getPopulationStats } from "../api/builds";
import { getFinderSkills, recommend } from "../api/fob";
import type { BuildIntent, ContentFocus, SortKey } from "../api/types";
import { BuildCard } from "../components/BuildCard";
import { ErrorBoundary } from "../components/ErrorBoundary";
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

/** Content-focus options for the structured search. */
const FOCUS_KEYS: { value: ContentFocus; it: string; en: string }[] = [
  { value: "mapping", it: "Mapping", en: "Mapping" },
  { value: "bossing", it: "Bossing", en: "Bossing" },
  { value: "ubers", it: "Uber boss", en: "Uber bosses" },
  { value: "league_start", it: "League start", en: "League start" },
  { value: "delve", it: "Delve", en: "Delve" },
  { value: "sanctum", it: "Sanctum", en: "Sanctum" },
  { value: "simulacrum", it: "Simulacrum", en: "Simulacrum" },
  { value: "generalist", it: "Tutto il contenuto", en: "All content" },
];

interface Props {
  onSendToPlanner?: (pobCode: string) => void;
  onSendToAnalyze?: (input: string) => void;
}

/**
 * Build the full BuildIntent client-side from the structured criteria —
 * deterministic, no extraction step, confidence is always 1.
 */
function intentFromFilters(f: FinderFilters): BuildIntent {
  return {
    damage_profile: null,
    alternative_damage_profiles: [],
    playstyle: null,
    alternative_playstyles: [],
    content_focus: f.focus
      ? [{ focus: f.focus as ContentFocus, weight: 1.0 }]
      : [],
    budget: null,
    complexity_cap: null,
    defense_profile: null,
    hard_constraints: [],
    main_skill_hint: f.skill,
    class_filter: f.class_filter,
    min_life: f.min_life,
    min_es: f.min_es,
    min_ehp: f.min_ehp,
    min_dps: f.min_dps,
    min_level: f.min_level,
    max_level: f.max_level,
    sort_by: f.sort_by,
    confidence: 1.0,
    raw_input: [f.skill, f.class_filter, f.focus].filter(Boolean).join(" ") || "structured search",
    parser_origin: "rule_based",
  };
}

/** Centred placeholder shown before any search has been run. */
function OracleEmptyState() {
  const t = useT();
  return (
    <Stack align="center" gap={6} py={48}>
      <IconSearch size={48} color="var(--vs-ember-border)" stroke={1.4} />
      <Text fw={600} size="lg" style={{ fontFamily: "'Cinzel', serif" }}>
        {t({
          it: "Cerca una build reale dalla ladder",
          en: "Search a real build from the ladder",
        })}
      </Text>
      <Text size="sm" c="dimmed" ta="center" maw={460}>
        {t({
          it: "Scegli skill, classe o contenuto qui sopra e premi Trova build — i risultati sono personaggi reali della lega corrente, ordinati per quanto rispondono ai tuoi criteri.",
          en: "Pick a skill, class or content above and hit Find builds — results are real characters from the current league, ranked against your criteria.",
        })}
      </Text>
    </Stack>
  );
}

export function FinderPage({ onSendToPlanner, onSendToAnalyze }: Props) {
  const t = useT();
  const sortOptions = SORT_KEYS.map((s) => ({
    value: s.value,
    label: t({ it: s.it, en: s.en }),
  }));
  const focusOptions = FOCUS_KEYS.map((f) => ({
    value: f.value,
    label: t({ it: f.it, en: f.en }),
  }));
  // Cross-route persistent state — criteria, results and the drill-down
  // skill filter survive navigating away and back (Zustand `pageStore`).
  const { topN, overrides, result, skillFilter } = usePageStore((s) => s.finder);
  const setFinder = usePageStore((s) => s.setFinder);

  // The searchable skill list (213 catalogue-derived main skills).
  const skillsQuery = useQuery({
    queryKey: ["finder-skills"],
    queryFn: getFinderSkills,
    staleTime: Infinity,
  });

  const recommendMut = useMutation({
    mutationFn: (i: BuildIntent) => recommend(i, topN),
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

  const handleSearch = () => {
    recommendMut.mutate(intentFromFilters(overrides));
  };

  return (
    <Stack gap="lg">
      {/* ── Structured search panel — concrete criteria, no NL parsing ── */}
      <Stack align="center" gap="sm" py={result ? "xs" : "md"}>
        {!result && (
          <>
            <Title order={2} ta="center">
              {t({ it: "Trova la tua build", en: "Find your build" })}
            </Title>
            <Text c="dimmed" ta="center" size="sm" maw={520}>
              {t({
                it: "Cerca tra le build reali della ladder per skill, classe e contenuto.",
                en: "Search the real ladder builds by skill, class and content.",
              })}
            </Text>
          </>
        )}
        <Group justify="center" wrap="wrap" gap="sm" align="flex-end">
          <Select
            label={t({ it: "Skill principale", en: "Main skill" })}
            placeholder={t({ it: "Qualsiasi skill", en: "Any skill" })}
            data={skillsQuery.data?.skills ?? []}
            value={overrides.skill}
            onChange={(v) => patchOverrides({ skill: v })}
            clearable
            searchable
            nothingFoundMessage={t({ it: "Nessuna skill", en: "No skill" })}
            size="md"
            w={230}
          />
          <Select
            label={t({ it: "Classe / Ascendancy", en: "Class / Ascendancy" })}
            placeholder={t({ it: "Qualsiasi", en: "Any" })}
            data={CLASS_OPTIONS}
            value={overrides.class_filter}
            onChange={(v) => patchOverrides({ class_filter: v })}
            clearable
            searchable
            size="md"
            w={200}
          />
          <Select
            label={t({ it: "Contenuto", en: "Content" })}
            placeholder={t({ it: "Qualsiasi", en: "Any" })}
            data={focusOptions}
            value={overrides.focus}
            onChange={(v) => patchOverrides({ focus: v })}
            clearable
            size="md"
            w={170}
          />
          <Button
            size="md"
            leftSection={<IconSearch size={18} />}
            onClick={handleSearch}
            loading={recommendMut.isPending}
          >
            {t({ it: "Trova build", en: "Find builds" })}
          </Button>
        </Group>

        {/* Refinement row — sort, stat floors, level range, result count. */}
        <div className="finder-filter-row">
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
            onChange={(v) => setFinder({ topN: typeof v === "number" ? v : 10 })}
            min={1}
            max={50}
            size="xs"
            w={90}
          />
          <Button
            size="xs"
            variant="subtle"
            color="gray"
            onClick={() => setFinder({ overrides: emptyFinderFilters() })}
          >
            {t({ it: "Reset", en: "Reset" })}
          </Button>
        </div>
      </Stack>

      {recommendMut.isError && (
        <Alert color="red" title={t({ it: "Errore nella ricerca", en: "Search error" })}>
          {recommendMut.error.message}
        </Alert>
      )}

      {/* ── Results ─────────────────────────────────────────────────── */}
      {result || recommendMut.isPending ? (
        <ErrorBoundary label={t({ it: "Errore nel pannello Finder", en: "Finder panel error" })}>
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
                            onSendToAnalyze={onSendToAnalyze}
                            metaPct={metaPct.get(
                              (b.ref.main_skill ?? "").toLowerCase(),
                            )}
                            onDrillSkill={handleDrillSkill}
                          />
                        ))}
                        {ranked.length === 0 && (
                          <Text c="dimmed" ta="center" py="xl">
                            {t({
                              it: "Nessuna build trovata con questi criteri — prova ad allargare i filtri.",
                              en: "No build found with these criteria — try widening the filters.",
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
              ) : null}
            </div>

            {/* Meta sidebar — population stats. Above results on mobile. */}
            <div className="finder-sidebar">
              <ErrorBoundary label={t({ it: "Errore nelle statistiche di popolazione", en: "Population stats error" })}>
                <PopulationStatsPanel ascendancy={overrides.class_filter} />
              </ErrorBoundary>
            </div>
          </div>
        </ErrorBoundary>
      ) : (
        <OracleEmptyState />
      )}
    </Stack>
  );
}
