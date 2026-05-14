/**
 * StageCard — visualisation of one PlanStage.
 *
 * Step 14 T5: tabbed layout with Overview / Tree / Gear / Gems sections,
 * plus an "Importa in PoB" CTA that fetches the stage's PoB-importable
 * code from /fob/stage-export.
 *
 * The Tree/Gear/Gems tabs lazy-fetch from /fob/{tree,gear,gem}-progression
 * the first time they're opened. When the active template doesn't ship a
 * progression for the requested stage, the tab shows a "non disponibile
 * per questo template" hint and the user can still rely on the Overview
 * tab's free-form copy from the Build's gem/tree changes.
 */

import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Code,
  CopyButton,
  Group,
  List,
  Loader,
  Stack,
  Table,
  Tabs,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconArrowDown,
  IconBolt,
  IconCheck,
  IconCoin,
  IconCopy,
  IconExternalLink,
  IconHourglass,
  IconList,
  IconPackage,
  IconSparkles,
  IconStairsUp,
  IconTree,
} from "@tabler/icons-react";
import { useCallback, useState } from "react";
import {
  fetchGearProgression,
  fetchGemProgression,
  fetchStageExport,
  fetchTreeProgression,
} from "../api/fob";
import type {
  Confidence,
  CoreItem,
  PlanStage,
  PriceRange,
  StageGearSet,
  StageGemLinks,
  StageTree,
} from "../api/types";
import { openTradeForItem } from "../api/tradeRedirect";

const CONFIDENCE_COLOR: Record<Confidence, string> = {
  low: "gray",
  medium: "blue",
  high: "teal",
};

function formatPrice(p: PriceRange): string {
  const fmt = (n: number) =>
    n >= 100 ? n.toFixed(0) : n >= 1 ? n.toFixed(1) : n.toFixed(2);
  const currency = p.min.currency === "divine" ? "div" : "c";
  if (p.min.amount === p.max.amount) {
    return `${fmt(p.min.amount)} ${currency}`;
  }
  return `${fmt(p.min.amount)}–${fmt(p.max.amount)} ${currency}`;
}

function ItemRow({
  item,
  onTradeClick,
}: {
  item: CoreItem;
  onTradeClick: (item: CoreItem) => void;
}) {
  const price = item.price_estimate;
  return (
    <Table.Tr>
      <Table.Td>
        <Text size="xs" c="dimmed" ff="monospace">
          #{item.buy_priority}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="sm" fw={500}>
          {item.name}
        </Text>
      </Table.Td>
      <Table.Td>
        <Text size="xs" c="dimmed">
          {item.slot.replace("_", " ")}
        </Text>
      </Table.Td>
      <Table.Td ta="right">
        {price ? (
          <Group gap={6} justify="flex-end" wrap="nowrap">
            <Text size="sm" fw={600}>
              {formatPrice(price)}
            </Text>
            <Badge
              size="xs"
              variant="dot"
              color={CONFIDENCE_COLOR[price.confidence]}
            >
              {price.confidence}
            </Badge>
          </Group>
        ) : (
          <Text size="xs" c="dimmed" fs="italic">
            n/d
          </Text>
        )}
      </Table.Td>
      <Table.Td style={{ width: 36 }}>
        <Tooltip
          label="Apri pathofexile.com/trade — il nome è copiato negli appunti, incollalo nella search e premi Cerca"
          withArrow
          multiline
          w={260}
        >
          <ActionIcon
            variant="subtle"
            color="astral"
            size="sm"
            onClick={() => onTradeClick(item)}
            aria-label="Apri su Trade"
          >
            <IconExternalLink size={14} />
          </ActionIcon>
        </Tooltip>
      </Table.Td>
    </Table.Tr>
  );
}

interface Props {
  stage: PlanStage;
  index: number;
  /** Identifier of the active BuildTemplate, e.g. 'rf_pohx'. Step 14 T5+. */
  templateName?: string | null;
  /** Character class to use for stage-export / tree URL encoding. */
  characterClass?: string | null;
  /** Ascendancy passed through to stage-export / tree URL encoding. */
  ascendancy?: string | null;
  /**
   * The user's original PoB code (raw export). Passed to the
   * stage-export endpoint as a fallback when the matched template has
   * no curated tree progression — preserves the user's actual tree.
   */
  userPobCode?: string | null;
}

export function StageCard({
  stage,
  index,
  templateName,
  characterClass,
  ascendancy,
  userPobCode,
}: Props) {
  const accent = index === 0 ? "teal" : index === 1 ? "blue" : "grape";

  function openTradeDialog(item: CoreItem) {
    // Synchronous: opens pathofexile.com/trade/search/<league> in a new
    // tab and copies the item name to the clipboard. Server-side
    // pre-filtering via GGG /api/trade/search/<league> is blocked
    // (HTTP 403 from Render's IP range — datacenter blacklist). See
    // ../api/tradeRedirect.ts for the full diagnosis.
    openTradeForItem({
      name: item.name,
      rarity: item.rarity,
      base_type: item.base_type,
      mods: item.mods,
    });
  }

  // Lazy state for the tab content. Each tab fetches once on first open
  // and caches the result for the lifetime of the component.
  const [stageTree, setStageTree] = useState<StageTree | null | undefined>(
    undefined,
  );
  const [stageGear, setStageGear] = useState<StageGearSet | null | undefined>(
    undefined,
  );
  const [stageGems, setStageGems] = useState<
    StageGemLinks | null | undefined
  >(undefined);
  const [exportCode, setExportCode] = useState<string | null | undefined>(
    undefined,
  );
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportLoading, setExportLoading] = useState(false);

  const stageKey = stage.stage_key;
  const canQueryProgressions = !!templateName && !!stageKey;

  const loadTree = useCallback(async () => {
    if (!canQueryProgressions || stageTree !== undefined) return;
    try {
      const prog = await fetchTreeProgression(templateName!);
      setStageTree(prog?.stages.find((s) => s.stage_key === stageKey) ?? null);
    } catch {
      setStageTree(null);
    }
  }, [canQueryProgressions, stageTree, templateName, stageKey]);

  const loadGear = useCallback(async () => {
    if (!canQueryProgressions || stageGear !== undefined) return;
    try {
      const prog = await fetchGearProgression(templateName!);
      setStageGear(prog?.stages.find((s) => s.stage_key === stageKey) ?? null);
    } catch {
      setStageGear(null);
    }
  }, [canQueryProgressions, stageGear, templateName, stageKey]);

  const loadGems = useCallback(async () => {
    if (!canQueryProgressions || stageGems !== undefined) return;
    try {
      const prog = await fetchGemProgression(templateName!);
      setStageGems(prog?.stages.find((s) => s.stage_key === stageKey) ?? null);
    } catch {
      setStageGems(null);
    }
  }, [canQueryProgressions, stageGems, templateName, stageKey]);

  // Importa in PoB: fetch the export code on demand, copy to clipboard
  // and surface a CopyButton-style chip with the actual code so the user
  // can re-copy or paste manually.
  const [exportTreeSource, setExportTreeSource] = useState<
    "progression" | "user_pob" | "empty" | null
  >(null);

  const handleExport = useCallback(async () => {
    if (!canQueryProgressions || exportLoading) return;
    setExportLoading(true);
    setExportError(null);
    setExportTreeSource(null);
    try {
      const res = await fetchStageExport(
        templateName!,
        stageKey!,
        characterClass || "Marauder",
        ascendancy ?? null,
        userPobCode ?? null,
      );
      setExportCode(res.code);
      setExportTreeSource(res.tree_source ?? null);
      if (!res.code) {
        setExportError(
          "Codice non generato. Riprova o riapri il piano dal PoB.",
        );
      } else {
        // Eagerly write to clipboard for the common case (one-tap import).
        try {
          await navigator.clipboard.writeText(res.code);
        } catch {
          // Clipboard write may fail in non-secure contexts — UI still
          // shows the code so the user can copy manually.
        }
      }
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExportLoading(false);
    }
  }, [
    canQueryProgressions,
    exportLoading,
    templateName,
    stageKey,
    characterClass,
    ascendancy,
    userPobCode,
  ]);

  return (
    <Card withBorder radius="md" p="md">
      <Stack gap="sm">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Group gap={10} wrap="nowrap">
            <ThemeIcon variant="light" color={accent} size="lg" radius="md">
              <Text size="sm" fw={700}>
                {index + 1}
              </Text>
            </ThemeIcon>
            <Title order={4}>{stage.label}</Title>
          </Group>
          <Group gap={6} wrap="nowrap">
            <IconCoin size={16} />
            <Text size="sm" fw={600}>
              {formatPrice(stage.budget_range)}
            </Text>
          </Group>
        </Group>

        {stage.expected_content.length > 0 && (
          <Group gap={6} wrap="wrap">
            {stage.expected_content.map((c) => (
              <Badge key={c} size="sm" variant="light" color={accent}>
                {c.replace("_", " ")}
              </Badge>
            ))}
          </Group>
        )}

        <Tabs defaultValue="overview" variant="pills" color={accent}>
          <Tabs.List>
            <Tabs.Tab
              value="overview"
              leftSection={<IconList size={14} />}
            >
              Overview
            </Tabs.Tab>
            <Tabs.Tab
              value="tree"
              leftSection={<IconTree size={14} />}
              onClick={loadTree}
              disabled={!canQueryProgressions}
            >
              Tree
            </Tabs.Tab>
            <Tabs.Tab
              value="gear"
              leftSection={<IconPackage size={14} />}
              onClick={loadGear}
              disabled={!canQueryProgressions}
            >
              Gear
            </Tabs.Tab>
            <Tabs.Tab
              value="gems"
              leftSection={<IconSparkles size={14} />}
              onClick={loadGems}
              disabled={!canQueryProgressions}
            >
              Gems
            </Tabs.Tab>
          </Tabs.List>

          {/* OVERVIEW: rationale + items + free-form gem/tree changes */}
          <Tabs.Panel value="overview" pt="sm">
            <Stack gap="sm">
              {stage.upgrade_rationale && (
                <Text size="sm" c="dimmed">
                  {stage.upgrade_rationale}
                </Text>
              )}

              {stage.core_items.length > 0 && (
                <Table withTableBorder withRowBorders verticalSpacing={4}>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th style={{ width: 36 }} />
                      <Table.Th>Item</Table.Th>
                      <Table.Th>Slot</Table.Th>
                      <Table.Th ta="right">Prezzo</Table.Th>
                      <Table.Th style={{ width: 36 }} />
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {stage.core_items.map((item) => (
                      <ItemRow
                        key={`${item.slot}-${item.name}`}
                        item={item}
                        onTradeClick={openTradeDialog}
                      />
                    ))}
                  </Table.Tbody>
                </Table>
              )}

              {(() => {
                // Reverse-mode ladder rationales are tagged `[target] body`
                // so we render the template advice and the per-item
                // ladder advice in visually distinct blocks.
                const LADDER_RE = /^\[([^\]]+)\]\s*(.*)$/;
                const templateLines: string[] = [];
                const ladderByTarget = new Map<string, string[]>();
                for (const line of stage.gem_changes) {
                  const m = line.match(LADDER_RE);
                  if (m) {
                    const target = m[1];
                    const body = m[2];
                    if (!ladderByTarget.has(target))
                      ladderByTarget.set(target, []);
                    ladderByTarget.get(target)!.push(body);
                  } else {
                    templateLines.push(line);
                  }
                }
                return (
                  <>
                    {templateLines.length > 0 && (
                      <Stack gap={4}>
                        <Group gap={6}>
                          <IconBolt size={14} />
                          <Text size="sm" fw={600}>
                            Gem
                          </Text>
                        </Group>
                        <List
                          size="sm"
                          spacing={2}
                          icon={
                            <ThemeIcon
                              size={14}
                              radius="xl"
                              color={accent}
                              variant="light"
                            >
                              <IconCheck size={10} />
                            </ThemeIcon>
                          }
                        >
                          {templateLines.map((g, i) => (
                            <List.Item key={i}>{g}</List.Item>
                          ))}
                        </List>
                      </Stack>
                    )}
                    {ladderByTarget.size > 0 && (
                      <Stack gap={6}>
                        <Group gap={6}>
                          <IconStairsUp size={14} />
                          <Text size="sm" fw={600}>
                            Upgrade ladder
                          </Text>
                        </Group>
                        <Stack gap={6}>
                          {Array.from(ladderByTarget.entries()).map(
                            ([target, bodies]) => (
                              <Stack key={target} gap={2}>
                                <Badge
                                  size="sm"
                                  variant="light"
                                  color={accent}
                                  radius="sm"
                                >
                                  {target}
                                </Badge>
                                <List size="xs" spacing={2} ml={6}>
                                  {bodies.map((b, i) => (
                                    <List.Item key={i}>{b}</List.Item>
                                  ))}
                                </List>
                              </Stack>
                            ),
                          )}
                        </Stack>
                      </Stack>
                    )}
                  </>
                );
              })()}

              {stage.tree_changes.length > 0 && (
                <Stack gap={4}>
                  <Text size="sm" fw={600}>
                    Albero passive
                  </Text>
                  <List size="sm" spacing={2}>
                    {stage.tree_changes.map((t, i) => (
                      <List.Item key={i}>{t}</List.Item>
                    ))}
                  </List>
                </Stack>
              )}
            </Stack>
          </Tabs.Panel>

          {/* TREE: nodes count + notables + ascendancy + share URL */}
          <Tabs.Panel value="tree" pt="sm">
            <TreePanel stageTree={stageTree} accent={accent} />
          </Tabs.Panel>

          {/* GEAR: per-slot grid */}
          <Tabs.Panel value="gear" pt="sm">
            <GearPanel stageGear={stageGear} accent={accent} />
          </Tabs.Panel>

          {/* GEMS: socket-link groups */}
          <Tabs.Panel value="gems" pt="sm">
            <GemsPanel stageGems={stageGems} accent={accent} />
          </Tabs.Panel>
        </Tabs>

        {/* Importa in PoB CTA — visible whenever the template is known. */}
        {canQueryProgressions && (
          <Stack gap={6}>
            <Group justify="space-between" wrap="nowrap">
              <Button
                size="xs"
                variant="light"
                color="astral"
                leftSection={
                  exportLoading ? (
                    <Loader size={12} />
                  ) : (
                    <IconExternalLink size={14} />
                  )
                }
                onClick={handleExport}
                disabled={exportLoading}
              >
                {exportCode
                  ? "Codice PoB pronto (copiato negli appunti)"
                  : "Importa stage in PoB"}
              </Button>
              {exportCode && (
                <CopyButton value={exportCode} timeout={1500}>
                  {({ copied, copy }) => (
                    <Button
                      size="xs"
                      variant="subtle"
                      color={copied ? "teal" : "gray"}
                      leftSection={
                        copied ? (
                          <IconCheck size={14} />
                        ) : (
                          <IconCopy size={14} />
                        )
                      }
                      onClick={copy}
                    >
                      {copied ? "Copiato" : "Copia di nuovo"}
                    </Button>
                  )}
                </CopyButton>
              )}
            </Group>
            {exportError && (
              <Text size="xs" c="red">
                {exportError}
              </Text>
            )}
            {exportCode && exportTreeSource && (
              <Text size="xs" c="dimmed">
                {exportTreeSource === "progression"
                  ? "Tree: progressione curata per questo template."
                  : exportTreeSource === "user_pob"
                    ? "Tree: preservato dal tuo PoB originale (nessuna progressione curata per questo template)."
                    : "Tree: vuoto — incolla il tuo albero in PoB dopo l'import."}
              </Text>
            )}
            {exportCode && (
              <Code
                block
                style={{
                  fontSize: 10,
                  maxHeight: 60,
                  overflow: "auto",
                  wordBreak: "break-all",
                }}
              >
                {exportCode.slice(0, 240)}
                {exportCode.length > 240 ? "…" : ""}
              </Code>
            )}
          </Stack>
        )}

        {/* Trade dialog removed — clicks now redirect directly to
            pathofexile.com/trade with the item name pre-copied to
            the clipboard. See ../api/tradeRedirect.ts. */}

        {stage.next_step_trigger && (
          <Group gap={6} wrap="nowrap" align="flex-start">
            <ThemeIcon variant="light" color="orange" size="sm" radius="xl">
              <IconHourglass size={12} />
            </ThemeIcon>
            <Text size="xs" c="dimmed" fs="italic">
              <Text span fw={600} c="orange">
                Next step:{" "}
              </Text>
              {stage.next_step_trigger}
            </Text>
            <IconArrowDown size={12} style={{ opacity: 0.5 }} />
          </Group>
        )}
      </Stack>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Tab panels
// ---------------------------------------------------------------------------

function TreePanel({
  stageTree,
  accent,
}: {
  stageTree: StageTree | null | undefined;
  accent: string;
}) {
  if (stageTree === undefined) return <PanelLoader label="Carico tree…" />;
  if (stageTree === null)
    return <PanelEmpty label="Tree progression non ancora disponibile per questo template." />;

  return (
    <Stack gap="sm">
      <Group gap={8} wrap="wrap">
        <Badge size="md" variant="light" color={accent}>
          {stageTree.node_ids.length} passive allocate
        </Badge>
        {stageTree.ascendancy_nodes.length > 0 && (
          <Badge size="md" variant="light" color="grape">
            {stageTree.ascendancy_nodes.length} ascendancy
          </Badge>
        )}
      </Group>
      {stageTree.notables.length > 0 && (
        <Stack gap={4}>
          <Text size="sm" fw={600}>
            Notables chiave
          </Text>
          <Group gap={4} wrap="wrap">
            {stageTree.notables.map((n) => (
              <Badge key={n} size="sm" variant="outline" color={accent}>
                {n}
              </Badge>
            ))}
          </Group>
        </Stack>
      )}
      {stageTree.ascendancy_nodes.length > 0 && (
        <Stack gap={4}>
          <Text size="sm" fw={600}>
            Ascendancy
          </Text>
          <Group gap={4} wrap="wrap">
            {stageTree.ascendancy_nodes.map((n) => (
              <Badge key={n} size="sm" variant="outline" color="grape">
                {n}
              </Badge>
            ))}
          </Group>
        </Stack>
      )}
      {stageTree.pob_url && (
        <Button
          size="xs"
          variant="subtle"
          color="astral"
          component="a"
          href={stageTree.pob_url}
          target="_blank"
          rel="noopener noreferrer"
          leftSection={<IconExternalLink size={14} />}
        >
          Apri tree su pathofexile.com
        </Button>
      )}
    </Stack>
  );
}

function GearPanel({
  stageGear,
  accent,
}: {
  stageGear: StageGearSet | null | undefined;
  accent: string;
}) {
  if (stageGear === undefined) return <PanelLoader label="Carico gear…" />;
  if (stageGear === null)
    return <PanelEmpty label="Gear progression non ancora disponibile per questo template." />;

  const KIND_COLOR: Record<string, string> = {
    unique: "yellow",
    rare_craft: "orange",
    leveling: "gray",
    skip: "dark",
  };

  return (
    <Stack gap="sm">
      {stageGear.overall_notes && (
        <Text size="sm" c="dimmed" fs="italic">
          {stageGear.overall_notes}
        </Text>
      )}
      <Table withTableBorder verticalSpacing={4}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Slot</Table.Th>
            <Table.Th>Item</Table.Th>
            <Table.Th>Tipo</Table.Th>
            <Table.Th>Note</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {stageGear.slots.map((s) => (
            <Table.Tr key={s.slot}>
              <Table.Td>
                <Text size="xs" c="dimmed">
                  {s.slot.replace("_", " ")}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" fw={500}>
                  {s.item_name}
                </Text>
              </Table.Td>
              <Table.Td>
                <Badge size="xs" variant="light" color={KIND_COLOR[s.kind] ?? accent}>
                  {s.kind}
                </Badge>
              </Table.Td>
              <Table.Td>
                <Text size="xs" c="dimmed">
                  {s.notes}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

function GemsPanel({
  stageGems,
  accent,
}: {
  stageGems: StageGemLinks | null | undefined;
  accent: string;
}) {
  if (stageGems === undefined) return <PanelLoader label="Carico gemme…" />;
  if (stageGems === null)
    return <PanelEmpty label="Gem progression non ancora disponibile per questo template." />;

  return (
    <Stack gap="sm">
      {stageGems.notes && (
        <Text size="sm" c="dimmed" fs="italic">
          {stageGems.notes}
        </Text>
      )}
      {stageGems.links.map((link, i) => (
        <Card key={i} withBorder radius="sm" p="xs">
          <Stack gap={4}>
            <Group justify="space-between" wrap="nowrap">
              <Group gap={6} wrap="nowrap">
                <Badge size="sm" variant="light" color={accent}>
                  {link.slot.replace("_", " ")}
                </Badge>
                <Badge size="xs" variant="outline" color={accent}>
                  {link.sockets}L
                </Badge>
                {link.color_pattern && (
                  <Code style={{ fontSize: 10 }}>{link.color_pattern}</Code>
                )}
              </Group>
            </Group>
            <List size="sm" spacing={2}>
              {link.gems.map((g, j) => (
                <List.Item
                  key={j}
                  icon={
                    <ThemeIcon
                      size={14}
                      radius="xl"
                      color={g.is_support ? "gray" : accent}
                      variant="light"
                    >
                      <IconCheck size={10} />
                    </ThemeIcon>
                  }
                >
                  <Text size="sm" component="span" fw={g.is_support ? 400 : 500}>
                    {g.name}
                  </Text>
                  <Text size="xs" component="span" c="dimmed" ml={6}>
                    L{g.level} / Q{g.quality}
                    {g.alt_quality ? ` · ${g.alt_quality}` : ""}
                  </Text>
                  {g.notes && (
                    <Text size="xs" c="dimmed" fs="italic" mt={2}>
                      {g.notes}
                    </Text>
                  )}
                </List.Item>
              ))}
            </List>
            {link.notes && (
              <Text size="xs" c="dimmed" fs="italic">
                {link.notes}
              </Text>
            )}
          </Stack>
        </Card>
      ))}
    </Stack>
  );
}

function PanelLoader({ label }: { label: string }) {
  return (
    <Group gap={8}>
      <Loader size="sm" />
      <Text size="sm" c="dimmed">
        {label}
      </Text>
    </Group>
  );
}

function PanelEmpty({ label }: { label: string }) {
  return (
    <Text size="sm" c="dimmed" fs="italic">
      {label}
    </Text>
  );
}
