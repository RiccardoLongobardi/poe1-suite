/**
 * TradeSearchDialog — poe.ninja-style item Trade search.
 *
 * A modal opened from any "Trade" icon. The user picks:
 *
 *  - **Search by** — the unique name or the base type.
 *  - **Mods** — *every* mod line of the item is listed. Lines that
 *    resolve to a GGG stat (via `POST /fob/extract-trade-mods`, backed
 *    by the vendored GGG stat database) are toggleable filters, each
 *    with a 50-100 % strictness slider (min sent = `rolled value ×
 *    strictness`). Lines that resolve to no stat are still shown, just
 *    disabled.
 *  - **Links** — optional 5-link / 6-link socket constraint.
 *
 * "Cerca su Trade" builds a `TradeUrlRequest`, asks the backend for a
 * prefilled `/trade/search/<league>/<id>` URL and opens it.
 */

import {
  Badge,
  Button,
  Divider,
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
  /** Explicit mod text lines to offer as filters. */
  rawMods?: string[];
  /** Implicit mod text lines (resolved against implicit-domain stats). */
  rawImplicits?: string[];
}

interface ModRow {
  mod: ExtractedTradeMod;
  enabled: boolean;
  /** Strictness percent, 50-100. */
  strictness: number;
}

/** Whether a row resolved to a searchable GGG stat. */
function isSearchable(row: ModRow): boolean {
  return row.mod.stat_id != null;
}

/** Min value sent to Trade for a row, or null when the mod has no number. */
function rowMin(row: ModRow): number | null {
  if (row.mod.value == null) return null;
  return Math.max(
    1,
    Math.round(((row.mod.value * row.strictness) / 100) * 10) / 10,
  );
}

export function TradeSearchDialog({
  opened,
  onClose,
  title,
  itemName,
  itemType,
  rawMods,
  rawImplicits,
}: Props) {
  const t = useT();
  const [searchBy, setSearchBy] = useState<"name" | "type">(
    itemName ? "name" : "type",
  );
  const [links, setLinks] = useState<"any" | "5" | "6">("any");
  const [rows, setRows] = useState<ModRow[]>([]);
  const [extracting, setExtracting] = useState(false);

  const rawModsKey = `${(rawMods ?? []).join("")}|${(rawImplicits ?? []).join("")}`;

  // Reset the search-by choice + link filter whenever a new item opens.
  useEffect(() => {
    if (!opened) return;
    setSearchBy(itemName ? "name" : "type");
    setLinks("any");
  }, [opened, itemName]);

  // Extract every mod line into a row on open. Searchable mods come
  // first (default ON), unsearchable ones last (forced OFF).
  useEffect(() => {
    const explicits = rawMods ?? [];
    const implicits = rawImplicits ?? [];
    if (!opened || (explicits.length === 0 && implicits.length === 0)) {
      setRows([]);
      return;
    }
    let cancelled = false;
    setExtracting(true);
    extractTradeMods(explicits, implicits)
      .then((resp) => {
        if (cancelled) return;
        const mapped: ModRow[] = resp.mods.map((m) => ({
          mod: m,
          enabled: m.stat_id != null,
          strictness: 80,
        }));
        mapped.sort(
          (a, b) => Number(isSearchable(b)) - Number(isSearchable(a)),
        );
        setRows(mapped);
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
      .filter((r) => r.enabled && r.mod.stat_id != null)
      .map((r) => {
        const min = rowMin(r);
        return min != null
          ? { stat_id: r.mod.stat_id as string, min }
          : { stat_id: r.mod.stat_id as string };
      });
    // The base type is always sent: for a unique-by-name search GGG
    // wants name + type together (a name-only query is unreliable);
    // for a base search it's the only filter.
    const req: TradeUrlRequest = {
      item_name: byName ? itemName : undefined,
      item_type: itemType ?? undefined,
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

  const searchable = rows.filter(isSearchable);
  const unsearchable = rows.filter((r) => !isSearchable(r));
  const enabledCount = searchable.filter((r) => r.enabled).length;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      centered
      size="xl"
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
        <Group gap="xl" align="flex-start" wrap="wrap">
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
        </Group>

        {/* Mods */}
        <Stack gap={6}>
          <Group justify="space-between">
            <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
              {t({ it: "Mod dell'oggetto", en: "Item mods" })}
            </Text>
            {searchable.length > 0 && (
              <Text size="xs" c="dimmed">
                {enabledCount}/{searchable.length}{" "}
                {t({ it: "attivi", en: "active" })}
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
                it: "Nessun mod sull'oggetto — la ricerca userà solo nome / base.",
                en: "No mods on the item — the search will use name / base only.",
              })}
            </Text>
          )}
          {rows.length > 0 && (
            <ScrollArea.Autosize mah={420}>
              <Stack gap={12} pr={10}>
                {searchable.map((row) => {
                  const idx = rows.indexOf(row);
                  const min = rowMin(row);
                  return (
                    <Stack key={`${row.mod.stat_id}-${idx}`} gap={2}>
                      <Switch
                        size="xs"
                        color="ember"
                        checked={row.enabled}
                        onChange={(e) =>
                          patchRow(idx, { enabled: e.currentTarget.checked })
                        }
                        label={<Text size="sm">{row.mod.label}</Text>}
                      />
                      {row.enabled && row.mod.value != null && (
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
                            onChange={(v) => patchRow(idx, { strictness: v })}
                            marks={[
                              { value: 80, label: "80%" },
                              { value: 100, label: "100%" },
                            ]}
                          />
                          {min != null && (
                            <Badge variant="light" color="ember" size="sm">
                              min {min}
                            </Badge>
                          )}
                        </Group>
                      )}
                    </Stack>
                  );
                })}

                {/* Mods that resolved to no GGG stat — shown but not
                    filterable. */}
                {unsearchable.length > 0 && (
                  <>
                    <Divider
                      label={t({
                        it: "Non ricercabili su Trade",
                        en: "Not searchable on Trade",
                      })}
                      labelPosition="left"
                    />
                    {unsearchable.map((row, i) => (
                      <Text
                        key={`uns-${i}`}
                        size="sm"
                        c="dimmed"
                        style={{ opacity: 0.7 }}
                      >
                        {row.mod.label}
                      </Text>
                    ))}
                  </>
                )}
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
