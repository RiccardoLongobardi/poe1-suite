/**
 * TradeSearchDialog — poe.ninja-style item Trade search.
 *
 * A modal opened from any "Trade" icon. The user picks:
 *
 *  - **Search by** — the unique name or the base type.
 *  - **Mods** — each recognised mod from the item, toggled on/off with
 *    a per-mod strictness slider (50-100 %, default 80). The min value
 *    sent to Trade is `rolled value × strictness`.
 *  - **Links** — optional 5-link / 6-link socket constraint.
 *
 * "Cerca su Trade" builds a `TradeUrlRequest`, asks the backend for a
 * prefilled `/trade/search/<league>/<id>` URL and opens it in a new
 * tab (see `openTradeUrl`).
 *
 * Mod rows come from `POST /fob/extract-trade-mods` — only mods the
 * backend can map to a GGG `stat_id` are shown; the rest are dropped.
 */

import {
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  ScrollArea,
  SegmentedControl,
  Slider,
  Stack,
  Switch,
  Text,
  ThemeIcon,
} from "@mantine/core";
import { IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { extractTradeMods } from "../api/fob";
import { openTradeUrl } from "../api/tradeRedirect";
import type { ExtractedTradeMod, TradeStatFilterInput, TradeUrlRequest } from "../api/types";
import { useT } from "../i18n";

interface Props {
  opened: boolean;
  onClose: () => void;
  /** Item display title shown in the modal header. */
  title: string;
  /** Unique name — pass only for uniques (a rare's rolled name is useless). */
  itemName?: string | null;
  /** Base type. */
  itemType?: string | null;
  /** Raw mod text lines (implicits + explicits) to offer as filters. */
  rawMods?: string[];
}

interface ModRow {
  mod: ExtractedTradeMod;
  enabled: boolean;
  /** Strictness percent, 50-100. */
  strictness: number;
}

/** Min value sent to Trade for a row: rolled value × strictness. */
function rowMin(row: ModRow): number {
  return Math.max(1, Math.round(((row.mod.value * row.strictness) / 100) * 10) / 10);
}

export function TradeSearchDialog({
  opened,
  onClose,
  title,
  itemName,
  itemType,
  rawMods,
}: Props) {
  const t = useT();
  const [searchBy, setSearchBy] = useState<"name" | "type">(
    itemName ? "name" : "type",
  );
  const [links, setLinks] = useState<"any" | "5" | "6">("any");
  const [rows, setRows] = useState<ModRow[]>([]);
  const [extracting, setExtracting] = useState(false);

  const rawModsKey = (rawMods ?? []).join("");

  // Reset the search-by choice + link filter whenever a new item opens.
  useEffect(() => {
    if (!opened) return;
    setSearchBy(itemName ? "name" : "type");
    setLinks("any");
  }, [opened, itemName]);

  // Extract the recognised mod rows from the raw mod text on open.
  useEffect(() => {
    if (!opened) {
      setRows([]);
      return;
    }
    if (!rawMods || rawMods.length === 0) {
      setRows([]);
      return;
    }
    let cancelled = false;
    setExtracting(true);
    extractTradeMods(rawMods)
      .then((resp) => {
        if (cancelled) return;
        setRows(
          resp.mods.map((m) => ({ mod: m, enabled: true, strictness: 80 })),
        );
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      })
      .finally(() => {
        if (!cancelled) setExtracting(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, rawModsKey]);

  function patchRow(idx: number, patch: Partial<ModRow>) {
    setRows((cur) => cur.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }

  function handleSearch() {
    const byName = searchBy === "name" && !!itemName;
    const stats: TradeStatFilterInput[] = rows
      .filter((r) => r.enabled)
      .map((r) => ({ stat_id: r.mod.stat_id, min: rowMin(r) }));
    const req: TradeUrlRequest = {
      item_name: byName ? itemName : undefined,
      item_type: byName ? undefined : (itemType ?? undefined),
      stats: stats.length > 0 ? stats : undefined,
      min_links: links === "any" ? undefined : Number(links),
    };
    openTradeUrl(req);
    onClose();
  }

  // search-by options — only offer the dimensions the item actually has.
  const searchByData: { value: string; label: string }[] = [];
  if (itemName) searchByData.push({ value: "name", label: t({ it: "Nome", en: "Name" }) });
  if (itemType) searchByData.push({ value: "type", label: t({ it: "Base", en: "Base" }) });

  const enabledCount = rows.filter((r) => r.enabled).length;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      centered
      size="lg"
      overlayProps={{ backgroundOpacity: 0.6, blur: 3 }}
      title={
        <Group gap={8}>
          <ThemeIcon variant="light" color="ember" size="md" radius="xl">
            <IconSearch size={15} />
          </ThemeIcon>
          <Text fw={600}>
            {t({ it: "Cerca su Trade", en: "Search on Trade" })} — {title}
          </Text>
        </Group>
      }
    >
      <Stack gap="md">
        {/* Search by — name vs base type */}
        {searchByData.length > 1 && (
          <Stack gap={4}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              {t({ it: "Cerca per", en: "Search by" })}
            </Text>
            <SegmentedControl
              size="xs"
              data={searchByData}
              value={searchBy}
              onChange={(v) => setSearchBy(v === "name" ? "name" : "type")}
            />
          </Stack>
        )}

        {/* Links */}
        <Stack gap={4}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
            {t({ it: "Link", en: "Links" })}
          </Text>
          <SegmentedControl
            size="xs"
            data={[
              { value: "any", label: t({ it: "Qualsiasi", en: "Any" }) },
              { value: "5", label: "5L" },
              { value: "6", label: "6L" },
            ]}
            value={links}
            onChange={(v) => setLinks(v as "any" | "5" | "6")}
          />
        </Stack>

        {/* Mods */}
        <Stack gap={6}>
          <Group justify="space-between">
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              {t({ it: "Mod", en: "Mods" })}
            </Text>
            {rows.length > 0 && (
              <Text size="xs" c="dimmed">
                {enabledCount}/{rows.length} {t({ it: "attivi", en: "active" })}
              </Text>
            )}
          </Group>
          {extracting && (
            <Group gap={8}>
              <Loader size="xs" />
              <Text size="xs" c="dimmed">
                {t({ it: "Estraggo i mod…", en: "Extracting mods…" })}
              </Text>
            </Group>
          )}
          {!extracting && rows.length === 0 && (
            <Text size="xs" c="dimmed" fs="italic">
              {t({
                it: "Nessun mod ricercabile — la ricerca userà solo nome / base.",
                en: "No searchable mods — the search will use name / base only.",
              })}
            </Text>
          )}
          {rows.length > 0 && (
            <ScrollArea.Autosize mah={280}>
              <Stack gap={10} pr={8}>
                {rows.map((row, i) => (
                  <Stack key={`${row.mod.stat_id}-${i}`} gap={2}>
                    <Switch
                      size="xs"
                      color="ember"
                      checked={row.enabled}
                      onChange={(e) =>
                        patchRow(i, { enabled: e.currentTarget.checked })
                      }
                      label={
                        <Text size="sm">
                          {row.mod.label}{" "}
                          <Text span c="dimmed" size="xs">
                            ({t({ it: "rollato", en: "rolled" })} {row.mod.value})
                          </Text>
                        </Text>
                      }
                    />
                    {row.enabled && (
                      <Group gap={8} pl={34} wrap="nowrap">
                        <Slider
                          flex={1}
                          size="xs"
                          color="ember"
                          min={50}
                          max={100}
                          step={5}
                          label={(v) => `${v}%`}
                          value={row.strictness}
                          onChange={(v) => patchRow(i, { strictness: v })}
                          marks={[
                            { value: 80, label: "80%" },
                            { value: 100, label: "100%" },
                          ]}
                        />
                        <Badge variant="light" color="ember" size="sm">
                          min {rowMin(row)}
                        </Badge>
                      </Group>
                    )}
                  </Stack>
                ))}
              </Stack>
            </ScrollArea.Autosize>
          )}
        </Stack>

        <Button
          fullWidth
          color="ember"
          leftSection={<IconSearch size={15} />}
          onClick={handleSearch}
        >
          {t({ it: "Cerca su Trade", en: "Search on Trade" })}
        </Button>
      </Stack>
    </Modal>
  );
}
