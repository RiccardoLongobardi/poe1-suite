/**
 * StageCard — visualisation of one PlanStage.
 *
 * Renders the stage label, total budget band, expected content focus,
 * core item list with per-item prices, gem/tree changes, the upgrade
 * rationale prose, and the "next step" trigger condition.
 */

import {
  ActionIcon,
  Badge,
  Card,
  Group,
  List,
  Stack,
  Table,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconArrowDown,
  IconBolt,
  IconCheck,
  IconCoin,
  IconHourglass,
  IconSearch,
  IconStairsUp,
} from "@tabler/icons-react";
import { useState } from "react";
import type {
  Confidence,
  CoreItem,
  PlanStage,
  PriceRange,
} from "../api/types";
import { TradeSearchDialog } from "./TradeSearchDialog";

const CONFIDENCE_COLOR: Record<Confidence, string> = {
  low: "gray",
  medium: "blue",
  high: "teal",
};

function formatPrice(p: PriceRange): string {
  const fmt = (n: number) =>
    n >= 100 ? n.toFixed(0) : n >= 1 ? n.toFixed(1) : n.toFixed(2);
  // PriceRange carries currency on each PriceValue end; min/max share
  // the same currency in practice.
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
        <Tooltip label="Cerca su pathofexile.com" withArrow>
          <ActionIcon
            variant="subtle"
            color="astral"
            size="sm"
            onClick={() => onTradeClick(item)}
            aria-label="Cerca su Trade"
          >
            <IconSearch size={14} />
          </ActionIcon>
        </Tooltip>
      </Table.Td>
    </Table.Tr>
  );
}

interface Props {
  stage: PlanStage;
  index: number;
}

export function StageCard({ stage, index }: Props) {
  const accent =
    index === 0 ? "teal" : index === 1 ? "blue" : "grape";

  // Trade search dialog state. We hold the active item so re-opening
  // the modal with a different row resets the row state cleanly.
  const [tradeOpen, tradeCtl] = useDisclosure(false);
  const [tradeItem, setTradeItem] = useState<CoreItem | null>(null);

  function openTradeDialog(item: CoreItem) {
    setTradeItem(item);
    tradeCtl.open();
  }

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

        {/* Trade search dialog — keyed on the item identity so opening
            for a different row resets internal row state. */}
        {tradeItem && (
          <TradeSearchDialog
            key={`${tradeItem.slot}-${tradeItem.name}`}
            opened={tradeOpen}
            onClose={tradeCtl.close}
            title={tradeItem.name}
            itemName={tradeItem.rarity === "unique" ? tradeItem.name : null}
            itemType={tradeItem.base_type ?? null}
            rawMods={tradeItem.mods ?? []}
            allowLinks={tradeItem.slot === "body_armour"}
          />
        )}

        {(() => {
          // Step 13.C: gem_changes can include reverse-mode ladder rungs
          // tagged with `[target_name] rationale`. Split them out so the
          // template advice and the per-item ladder advice render in
          // visually distinct blocks (template = clean bullets, ladder
          // = grouped by target).
          const LADDER_RE = /^\[([^\]]+)\]\s*(.*)$/;
          const templateLines: string[] = [];
          const ladderByTarget = new Map<string, string[]>();
          for (const line of stage.gem_changes) {
            const m = line.match(LADDER_RE);
            if (m) {
              const target = m[1];
              const body = m[2];
              if (!ladderByTarget.has(target)) ladderByTarget.set(target, []);
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
