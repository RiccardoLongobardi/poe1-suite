/**
 * TheorycrafterPage — `/theorycrafter`, the from-scratch Build Generator (v2).
 *
 * Step 40. Form-driven (no free-text input): cascading selects for
 * Class → Ascendancy → Primary Skill → Damage Type → Defence → Budget
 * → Focus. The backend synthesises a `BuildSkeleton` from vendored
 * PoE 3.28 data (passive tree, gem tags, item bases). Each gear slot
 * card has a Trade icon that opens GGG Trade prefilled with the slot's
 * base + stat priorities — identical pattern to Analyze/Planner.
 *
 * No tab shell. Theorycrafter is one tool — the Build Generator.
 */

import {
  Accordion,
  ActionIcon,
  Alert,
  Badge,
  Box,
  Button,
  Card,
  CopyButton,
  Divider,
  Grid,
  Group,
  SegmentedControl,
  Select,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import {
  IconAlertTriangle,
  IconCheck,
  IconChevronDown,
  IconChevronUp,
  IconCircleCheck,
  IconCopy,
  IconExternalLink,
  IconFlask,
} from "@tabler/icons-react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { generateBuild, getTheorySkills } from "../api/fob";
import { TradeSearchDialog } from "../components/TradeSearchDialog";
import type {
  BuildSkeleton,
  DamageType,
  DefenceArchetype,
  SkeletonBudget,
  TheoryContentFocus,
  TheoryGearSlot,
  TheoryIntent,
  ViabilityReport,
} from "../api/types";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { useLang, useT } from "../i18n";
import { usePageStore } from "../store/pageStore";

// ---------------------------------------------------------------------------
// Static lookup tables
// ---------------------------------------------------------------------------

const CLASSES = [
  "Marauder",
  "Duelist",
  "Ranger",
  "Witch",
  "Templar",
  "Shadow",
  "Scion",
] as const;

const ASCENDANCIES: Record<string, string[]> = {
  Marauder: ["Juggernaut", "Berserker", "Chieftain"],
  Duelist: ["Slayer", "Gladiator", "Champion"],
  Ranger: ["Deadeye", "Raider", "Pathfinder"],
  Witch: ["Necromancer", "Occultist", "Elementalist"],
  Templar: ["Inquisitor", "Hierophant", "Guardian"],
  Shadow: ["Assassin", "Saboteur", "Trickster"],
  Scion: ["Ascendant"],
};

const DAMAGE_TYPES: { value: DamageType; it: string; en: string }[] = [
  { value: "fire", it: "Fuoco", en: "Fire" },
  { value: "cold", it: "Freddo", en: "Cold" },
  { value: "lightning", it: "Folgore", en: "Lightning" },
  { value: "chaos", it: "Caos", en: "Chaos" },
  { value: "physical", it: "Fisico", en: "Physical" },
  { value: "spell", it: "Incantesimo", en: "Spell" },
  { value: "attack", it: "Attacco", en: "Attack" },
];

const DEFENCES: { value: DefenceArchetype; it: string; en: string }[] = [
  { value: "life", it: "Vita", en: "Life" },
  { value: "es", it: "ES", en: "ES" },
  { value: "ward", it: "Ward", en: "Ward" },
  { value: "hybrid_life_es", it: "Vita+ES", en: "Life+ES" },
];

const BUDGETS: { value: SkeletonBudget; it: string; en: string }[] = [
  { value: "starter", it: "Inizio lega", en: "League start" },
  { value: "mid", it: "Medio", en: "Mid" },
  { value: "endgame", it: "Endgame", en: "Endgame" },
];

const FOCI: { value: TheoryContentFocus; it: string; en: string }[] = [
  { value: "mapping", it: "Mappatura", en: "Mapping" },
  { value: "bossing", it: "Boss", en: "Bossing" },
  { value: "allcontent", it: "Tutti i contenuti", en: "All content" },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Map a stat-priority phrase to the PoE-tooltip sigil it would carry. */
function _affixSigil(priority: string): string {
  if (priority.startsWith("to ")) return "+#";
  if (priority.toLowerCase().includes("speed") || priority.toLowerCase().includes("increased"))
    return "#%";
  if (priority.toLowerCase().includes("resistance")) return "+#%";
  if (priority.toLowerCase().includes("critical")) return "#%";
  return "+#";
}

interface GearSlotCardProps {
  slot: TheoryGearSlot;
  onTrade: (slot: TheoryGearSlot) => void;
}

/** One gear-slot card — same visual language as Analyze's `GearCard` but
 *  rendering a *recommendation* (base + stat priorities), not a real item.
 *  Click to expand the simulated affix list; Trade icon opens the
 *  `TradeSearchDialog` against the slot's base type + priority hints. */
function GearSlotCard({ slot, onTrade }: GearSlotCardProps) {
  const t = useT();
  const [expanded, setExpanded] = useState(false);
  const isFlaskOrJewel =
    slot.slot.startsWith("Flask") || slot.slot.startsWith("Jewel");

  return (
    <Box
      className="vs-rarity"
      data-rarity="rare"
      style={{
        borderLeft: "3px solid var(--vs-rare)",
        padding: "8px 10px",
        background: "var(--vs-surface-2)",
        borderRadius: 4,
        minWidth: 0,
      }}
    >
      <Group justify="space-between" gap={4} wrap="nowrap" align="flex-start">
        <Box
          component="button"
          type="button"
          aria-label={t({
            it: expanded ? "Nascondi affissi" : "Mostra affissi",
            en: expanded ? "Hide affixes" : "Show affixes",
          })}
          onClick={() => setExpanded((v) => !v)}
          style={{
            background: "transparent",
            border: "none",
            padding: 0,
            cursor: "pointer",
            textAlign: "left",
            flex: 1,
            minWidth: 0,
            color: "inherit",
          }}
        >
          <Group gap={4} wrap="nowrap">
            <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
              {slot.slot}
            </Text>
            {!isFlaskOrJewel &&
              (expanded ? (
                <IconChevronUp size={10} color="var(--vs-text-dim)" />
              ) : (
                <IconChevronDown size={10} color="var(--vs-text-dim)" />
              ))}
          </Group>
          <Text size="sm" fw={600} mt={2} truncate>
            {slot.base_name}
          </Text>
        </Box>
        <Tooltip label={t({ it: "Cerca su Trade", en: "Search on Trade" })}>
          <ActionIcon
            size="xs"
            variant="subtle"
            color="ember"
            onClick={(e) => {
              e.stopPropagation();
              onTrade(slot);
            }}
            aria-label={t({ it: "Cerca su Trade", en: "Search on Trade" })}
          >
            <IconExternalLink size={12} />
          </ActionIcon>
        </Tooltip>
      </Group>

      {isFlaskOrJewel ? (
        <Text size="10px" c="dimmed" fs="italic" mt={4}>
          {t({ it: "~ stimato", en: "~ estimated" })}
        </Text>
      ) : expanded ? (
        <Stack gap={2} mt={6}>
          <Text size="10px" c="dimmed" fs="italic">
            {t({ it: "~ stimato", en: "~ estimated" })}
          </Text>
          {slot.stat_priorities.map((s, i) => (
            <Text key={`${s}-${i}`} size="xs" c="dimmed">
              <span style={{ color: "var(--vs-rare)" }}>{_affixSigil(s)}</span>{" "}
              {s}
            </Text>
          ))}
        </Stack>
      ) : (
        <Group gap={3} mt={4}>
          {slot.stat_priorities.slice(0, 2).map((s) => (
            <Badge key={s} size="xs" variant="light" color="ember">
              {s}
            </Badge>
          ))}
          {slot.stat_priorities.length > 2 && (
            <Badge size="xs" variant="default" c="dimmed">
              +{slot.stat_priorities.length - 2}
            </Badge>
          )}
        </Group>
      )}
    </Box>
  );
}

/** Viability findings rendered as a stack of compact alert rows. */
function ViabilityPanel({ report }: { report: ViabilityReport }) {
  const t = useT();
  const { lang } = useLang();
  const errors = report.issues.filter((i) => i.severity === "error");
  const warnings = report.issues.filter((i) => i.severity === "warning");

  if (report.passed && warnings.length === 0) {
    return (
      <Alert color="green" icon={<IconCircleCheck size={16} />}>
        {t({
          it: "Build strutturalmente valida. Verifica sempre la cappatura delle resistenze sull'equipaggiamento.",
          en: "Build structurally valid. Always verify resistance cap on gear.",
        })}
      </Alert>
    );
  }

  const headerColor = errors.length > 0 ? "red" : "yellow";
  const headerText =
    errors.length > 0
      ? t({
          it: `${errors.length} errore${errors.length === 1 ? "" : "i"} bloccante${errors.length === 1 ? "" : "i"} — la build non è viable cosi com'è.`,
          en: `${errors.length} blocking error${errors.length === 1 ? "" : "s"} — the build is not viable as-is.`,
        })
      : t({
          it: `${warnings.length} avviso${warnings.length === 1 ? "" : "i"} di viabilità.`,
          en: `${warnings.length} viability warning${warnings.length === 1 ? "" : "s"}.`,
        });

  return (
    <Alert color={headerColor} icon={<IconAlertTriangle size={16} />}>
      <Stack gap={6}>
        <Text size="sm" fw={600}>
          {headerText}
        </Text>
        {report.issues.map((issue) => (
          <Group key={issue.code} gap={8} wrap="nowrap" align="flex-start">
            <Badge
              size="xs"
              color={issue.severity === "error" ? "red" : "yellow"}
              variant="light"
              style={{ flexShrink: 0, marginTop: 2 }}
            >
              {issue.severity === "error"
                ? t({ it: "errore", en: "error" })
                : t({ it: "avviso", en: "warning" })}
            </Badge>
            <Text size="xs" style={{ lineHeight: 1.4 }}>
              {lang === "en" ? issue.message_en : issue.message_it}
            </Text>
          </Group>
        ))}
      </Stack>
    </Alert>
  );
}

function SkeletonResult({ skeleton }: { skeleton: BuildSkeleton }) {
  const t = useT();
  const { lang } = useLang();
  const rationale =
    lang === "en" ? skeleton.rationale_en : skeleton.rationale_it;
  // Trade dialog: one open at a time, shape mirrors Analyze/Planner.
  const [tradeItem, setTradeItem] = useState<TheoryGearSlot | null>(null);

  return (
    <Stack gap="md" className="vs-card-reveal">
      {/* Header */}
      <Card withBorder padding="md">
        <Group gap="sm" wrap="wrap">
          <Badge size="lg" color="ember" variant="filled">
            {skeleton.intent.character_class} · {skeleton.intent.ascendancy}
          </Badge>
          <Badge size="lg" color="ember" variant="light">
            {skeleton.intent.primary_skill}
          </Badge>
          <Badge size="lg" variant="default">
            {skeleton.intent.damage_type}
          </Badge>
          <Badge size="lg" variant="default">
            {skeleton.intent.defence_archetype}
          </Badge>
          <Badge size="lg" variant="default">
            {skeleton.intent.budget}
          </Badge>
          <Badge size="lg" variant="default">
            {skeleton.intent.focus}
          </Badge>
        </Group>
      </Card>

      {/* Viability report (Step 43) */}
      <ViabilityPanel report={skeleton.viability} />

      {/* Stat estimates — or PoB-exact numbers for a precomputed optimum */}
      {(() => {
        const opt = skeleton.optimised && !skeleton.stats.estimated;
        const sig = opt ? "" : "~";
        return (
          <Card withBorder padding="md">
            <Group justify="space-between" mb={4}>
              <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                {opt
                  ? t({ it: "Statistiche reali", en: "Real stats" })
                  : t({ it: "Stime", en: "Estimates" })}
              </Text>
              {opt ? (
                <Tooltip
                  label={t({
                    it: "Build ottimizzata col motore di calcolo reale di PoB",
                    en: "Build optimised with PoB's real calc engine",
                  })}
                >
                  <Badge size="xs" variant="filled" color="teal">
                    {t({ it: "Ottimizzato con PoB", en: "PoB-optimised" })}
                  </Badge>
                </Tooltip>
              ) : (
                <Tooltip
                  label={t({
                    it: "Valori stimati — importa in PoB per calcoli precisi",
                    en: "Estimated values — import into PoB for precise math",
                  })}
                >
                  <Badge size="xs" variant="outline" color="yellow">
                    {t({ it: "~ stimato", en: "~ estimated" })}
                  </Badge>
                </Tooltip>
              )}
            </Group>
            <Group gap="xl" wrap="wrap">
              <Stack gap={0}>
                <Text size="xs" c="dimmed">
                  {t({ it: "Vita", en: "Life" })}
                </Text>
                <Text className="mono" size="lg" fw={700}>
                  {sig}
                  {skeleton.stats.life_estimate.toLocaleString()}
                </Text>
              </Stack>
              {skeleton.stats.es_estimate > 0 && (
                <Stack gap={0}>
                  <Text size="xs" c="dimmed">
                    {t({ it: "Energy shield", en: "Energy shield" })}
                  </Text>
                  <Text className="mono" size="lg" fw={700}>
                    {sig}
                    {skeleton.stats.es_estimate.toLocaleString()}
                  </Text>
                </Stack>
              )}
              {opt && skeleton.stats.full_dps > 0 && (
                <Stack gap={0}>
                  <Text size="xs" c="dimmed">
                    DPS
                  </Text>
                  <Text className="mono" size="lg" fw={700}>
                    {Math.round(skeleton.stats.full_dps).toLocaleString()}
                  </Text>
                </Stack>
              )}
              {opt && skeleton.stats.total_ehp > 0 && (
                <Stack gap={0}>
                  <Text size="xs" c="dimmed">
                    EHP
                  </Text>
                  <Text className="mono" size="lg" fw={700}>
                    {skeleton.stats.total_ehp.toLocaleString()}
                  </Text>
                </Stack>
              )}
            </Group>
            <Text size="xs" c="dimmed" mt={4}>
              {opt
                ? t({
                    it: "Versione ottimizzata: supporti, arma e albero scelti massimizzando il DPS reale di PoB mantenendo le resistenze al cap.",
                    en: "Optimised version: supports, weapon and tree chosen to maximise PoB's real DPS while keeping resistances capped.",
                  })
                : t({
                    it: "Il DPS reale dipende da gemme, link e item: importa in PoB per il calcolo preciso.",
                    en: "Real DPS depends on gems, links and items: import into PoB for the precise number.",
                  })}
            </Text>
            {skeleton.stats.resistance_warning && (
              <Alert mt="xs" color="yellow" variant="light">
                {skeleton.stats.resistance_warning}
              </Alert>
            )}
          </Card>
        );
      })()}

      {/* Two-column on md+: gems + tree on the left, gear grid on the right. */}
      <Grid gutter="md">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Stack gap="md">
            {/* Gem links */}
            <Card withBorder padding="md">
              <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
                {t({ it: "Collegamenti gemma", en: "Gem links" })}
              </Text>
              <Stack gap="sm">
                {skeleton.links.map((link) => (
                  <Group key={link.skill} gap={6} wrap="wrap">
                    <Badge color="ember" variant="filled">
                      {link.skill}
                    </Badge>
                    {link.supports.map((s, i) => (
                      <Badge
                        key={`${s}-${i}`}
                        variant="outline"
                        color={s === "(open)" ? "gray" : "ember"}
                        c={s === "(open)" ? "dimmed" : undefined}
                      >
                        {s}
                      </Badge>
                    ))}
                  </Group>
                ))}
              </Stack>
            </Card>

            {/* Tree nodes */}
            <Card withBorder padding="md">
              <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
                {t({ it: "Tappe dell'albero", en: "Tree milestones" })}
              </Text>
              <Stack gap={4}>
                {skeleton.tree_nodes
                  .filter((n) => n.type !== "travel")
                  .map((n) => (
                  <Group
                    key={`${n.type}-${n.node_id}-${n.name}`}
                    gap={6}
                    wrap="nowrap"
                    align="flex-start"
                  >
                    <Badge
                      size="xs"
                      color={
                        n.type === "keystone"
                          ? "red"
                          : n.type === "ascendancy"
                            ? "grape"
                            : n.type === "mastery"
                              ? "teal"
                              : n.type === "start"
                                ? "gray"
                                : "ember"
                      }
                      variant="light"
                      w={88}
                    >
                      {n.type}
                    </Badge>
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm">{n.name}</Text>
                      {n.type === "mastery" && n.stats[0] && (
                        <Text size="11px" c="dimmed">
                          {n.stats[0]}
                        </Text>
                      )}
                    </div>
                    {n.node_id > 0 && n.type !== "mastery" && (
                      <Text size="10px" c="dimmed" className="mono">
                        #{n.node_id}
                      </Text>
                    )}
                  </Group>
                ))}
              </Stack>
              {(() => {
                const total = skeleton.tree_nodes.length;
                const travel = skeleton.tree_nodes.filter(
                  (n) => n.type === "travel",
                ).length;
                return travel > 0 ? (
                  <Text size="10px" c="dimmed" fs="italic" mt={6}>
                    {t({
                      it: `Albero generato con ${total} nodi (inclusi ${travel} nodi di percorso).`,
                      en: `Tree generated with ${total} nodes (${travel} path nodes).`,
                    })}
                  </Text>
                ) : null;
              })()}
            </Card>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 7 }}>
          {/* Gear slots — narrower cards (1/2/3 cols) once affixes can expand. */}
          <Card withBorder padding="md">
            <Text size="xs" tt="uppercase" fw={700} c="dimmed" mb={6}>
              {t({ it: "Slot equipaggiamento", en: "Gear slots" })}
            </Text>
            <Box
              style={{
                display: "grid",
                gap: 8,
                gridTemplateColumns:
                  "repeat(auto-fill, minmax(min(100%, 200px), 1fr))",
              }}
            >
              {skeleton.gear_slots.map((g) => (
                <GearSlotCard key={g.slot} slot={g} onTrade={setTradeItem} />
              ))}
            </Box>
          </Card>
        </Grid.Col>
      </Grid>

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

      {/* PoB export */}
      <Card withBorder padding="md">
        <Group justify="space-between" mb={6}>
          <Text size="xs" tt="uppercase" fw={700} c="dimmed">
            {t({ it: "Esporta in PoB", en: "Export to PoB" })}
          </Text>
          <CopyButton value={skeleton.pob_code}>
            {({ copied, copy }) => (
              <Button
                color={copied ? "teal" : "ember"}
                leftSection={
                  copied ? <IconCheck size={14} /> : <IconCopy size={14} />
                }
                onClick={() => {
                  copy();
                  notifications.show({
                    color: "ember",
                    title: t({ it: "Copiato", en: "Copied" }),
                    message: t({
                      it: "Incolla il codice nel pulsante \"Import\" di PoB.",
                      en: 'Paste the code into PoB\'s "Import" button.',
                    }),
                  });
                }}
              >
                {copied
                  ? t({ it: "Copiato", en: "Copied" })
                  : t({ it: "Copia codice PoB", en: "Copy PoB code" })}
              </Button>
            )}
          </CopyButton>
        </Group>
        <Text size="10px" c="dimmed" style={{ wordBreak: "break-all" }}>
          {skeleton.pob_code.slice(0, 240)}…
        </Text>
      </Card>

      {/* Trade dialog — same pattern as Analyze/Planner. */}
      <TradeSearchDialog
        opened={tradeItem !== null}
        onClose={() => setTradeItem(null)}
        title={tradeItem ? `${tradeItem.slot} — ${tradeItem.base_name}` : ""}
        itemName={null}
        itemType={tradeItem?.base_name ?? null}
        rawMods={tradeItem?.stat_priorities ?? []}
        rawImplicits={[]}
      />
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function TheorycrafterPage() {
  const t = useT();
  const { form, result } = usePageStore((s) => s.theory);
  const setTheory = usePageStore((s) => s.setTheory);

  const skillsQuery = useQuery({
    queryKey: ["theory-skills"],
    queryFn: () => getTheorySkills(),
    staleTime: 60 * 60 * 1000,
  });

  const skillsByName = useMemo(() => {
    const m = new Map<string, { tags: string[]; damage_types: string[] }>();
    for (const s of skillsQuery.data?.skills ?? []) {
      m.set(s.name, { tags: s.tags, damage_types: s.damage_types });
    }
    return m;
  }, [skillsQuery.data]);

  const genMut = useMutation({
    mutationFn: (intent: TheoryIntent) => generateBuild(intent),
    onSuccess: (data) => setTheory({ result: data }),
  });

  const canSubmit =
    !!form.character_class &&
    !!form.ascendancy &&
    !!form.primary_skill &&
    !!form.damage_type;

  function patchForm(p: Partial<typeof form>): void {
    setTheory({ form: { ...form, ...p } });
  }

  function onSelectClass(v: string | null): void {
    patchForm({
      character_class: v ?? "",
      ascendancy: "",
      primary_skill: "",
      damage_type: "",
    });
  }

  function onSelectAsc(v: string | null): void {
    patchForm({ ascendancy: v ?? "", primary_skill: "", damage_type: "" });
  }

  function onSelectSkill(v: string | null): void {
    const meta = v ? skillsByName.get(v) : undefined;
    const dt = meta?.damage_types?.[0];
    patchForm({
      primary_skill: v ?? "",
      damage_type:
        (dt as DamageType | undefined) ??
        (meta?.tags.find((tg) =>
          ["fire", "cold", "lightning", "chaos", "physical"].includes(tg),
        ) as DamageType | undefined) ??
        "",
    });
  }

  function onGenerate(): void {
    if (!canSubmit) return;
    setTheory({ result: null });
    genMut.mutate({
      character_class: form.character_class,
      ascendancy: form.ascendancy,
      primary_skill: form.primary_skill,
      damage_type: form.damage_type as DamageType,
      defence_archetype: form.defence_archetype,
      budget: form.budget,
      focus: form.focus,
    });
  }

  const ascData = form.character_class
    ? ASCENDANCIES[form.character_class] ?? []
    : [];
  const skillData = (skillsQuery.data?.skills ?? []).map((s) => ({
    value: s.name,
    label: s.name,
  }));
  const damageData = DAMAGE_TYPES.map((d) => ({
    value: d.value,
    label: t({ it: d.it, en: d.en }),
  }));

  return (
    <Stack gap="md">
      <Title order={2}>Theorycrafter</Title>
      <Text size="sm" c="dimmed" maw={640}>
        {t({
          it: "Compila i campi per generare uno scheletro di build da zero — albero, gemme e basi vengono dai dati ufficiali di PoE 3.28. Nessun campo libero: niente classi inventate o oggetti che non esistono.",
          en: "Fill in the fields to generate a build skeleton from scratch — the tree, gems and bases come from official PoE 3.28 data. No free text input: no invented classes or items.",
        })}
      </Text>

      {/* Form */}
      <Card withBorder padding="md">
        <Stack gap="sm">
          <Group gap="sm" wrap="wrap" align="flex-end">
            <Select
              label={t({ it: "Classe", en: "Class" })}
              placeholder={t({ it: "Scegli", en: "Pick" })}
              data={CLASSES as unknown as string[]}
              value={form.character_class || null}
              onChange={onSelectClass}
              w={160}
            />
            <Select
              label="Ascendancy"
              placeholder={t({ it: "Scegli", en: "Pick" })}
              data={ascData}
              value={form.ascendancy || null}
              onChange={onSelectAsc}
              disabled={!form.character_class}
              w={170}
            />
            <Select
              label={t({ it: "Skill primaria", en: "Primary skill" })}
              placeholder={t({ it: "Scegli", en: "Pick" })}
              data={skillData}
              value={form.primary_skill || null}
              onChange={onSelectSkill}
              disabled={!form.ascendancy || skillsQuery.isLoading}
              searchable
              w={220}
            />
            <Select
              label={t({ it: "Tipo di danno", en: "Damage type" })}
              data={damageData}
              value={form.damage_type || null}
              onChange={(v) =>
                patchForm({ damage_type: (v as DamageType | null) ?? "" })
              }
              disabled={!form.primary_skill}
              w={170}
            />
          </Group>
          <Group gap="md" wrap="wrap">
            <Box>
              <Text size="xs" c="dimmed" mb={4}>
                {t({ it: "Difesa", en: "Defence" })}
              </Text>
              <SegmentedControl
                value={form.defence_archetype}
                onChange={(v) =>
                  patchForm({ defence_archetype: v as DefenceArchetype })
                }
                data={DEFENCES.map((d) => ({
                  value: d.value,
                  label: t({ it: d.it, en: d.en }),
                }))}
              />
            </Box>
            <Box>
              <Text size="xs" c="dimmed" mb={4}>
                {t({ it: "Budget", en: "Budget" })}
              </Text>
              <SegmentedControl
                value={form.budget}
                onChange={(v) => patchForm({ budget: v as SkeletonBudget })}
                data={BUDGETS.map((b) => ({
                  value: b.value,
                  label: t({ it: b.it, en: b.en }),
                }))}
              />
            </Box>
            <Box>
              <Text size="xs" c="dimmed" mb={4}>
                Focus
              </Text>
              <SegmentedControl
                value={form.focus}
                onChange={(v) => patchForm({ focus: v as TheoryContentFocus })}
                data={FOCI.map((f) => ({
                  value: f.value,
                  label: t({ it: f.it, en: f.en }),
                }))}
              />
            </Box>
          </Group>
          <Divider />
          <Group justify="flex-end">
            <Button
              leftSection={<IconFlask size={16} />}
              disabled={!canSubmit}
              loading={genMut.isPending}
              onClick={onGenerate}
            >
              {t({ it: "Genera build", en: "Generate build" })}
            </Button>
          </Group>
        </Stack>
      </Card>

      {/* Errors / loading / result */}
      {genMut.isError && (
        <Alert color="red" title={t({ it: "Errore", en: "Error" })}>
          {genMut.error.message}
        </Alert>
      )}
      {genMut.isPending && (
        <Box className="vs-skeleton vs-skeleton-card" style={{ height: 280 }} />
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
