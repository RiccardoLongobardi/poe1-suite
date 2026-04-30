/**
 * TradeSearchDialog — poe.ninja-style item trade search.
 *
 * Opens a Mantine modal pre-populated with the item's name / base type
 * and optional mod filter list. The user can:
 *
 * * Toggle individual mods on/off (Switch).
 * * Adjust strictness per mod via a 50-100 % slider — defaults to 80 %
 *   (poe.ninja's default for budget search).
 * * Constrain to 5L / 6L sockets if applicable.
 * * Click "Apri su Trade" → POST to /fob/trade-search → ``window.open``
 *   the returned ``pathofexile.com/trade/search/<league>/<id>`` URL in
 *   a new tab.
 *
 * Designed to be reusable from any item-bearing context (Plan items,
 * analyzed PoB items, BuildCard expanded gear). Callers pass the item
 * identity + the mod list they've already extracted via
 * ``valuable_stat_filters_from_mods`` on the server side.
 */

import {
  Alert,
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  ScrollArea,
  Slider,
  Stack,
  Switch,
  Text,
  ThemeIcon,
} from "@mantine/core";
import { IconExternalLink, IconSearch } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { extractTradeMods, tradeSearch } from "../api/fob";
import type { TradeSearchModFilter } from "../api/types";

/**
 * One mod the user can toggle in the dialog. The pre-fetched
 * ``rolled_value`` (the actual stat value rolled on the item) lets the
 * strictness slider compute a sensible ``min`` automatically: at 80 %
 * we ask Trade for items with at least 80 % of that roll.
 */
export interface TradeDialogMod {
  stat_id: string;
  /** Human-readable label shown in the dialog (e.g. "+# to maximum Life"). */
  label: string;
  /** The value rolled on the source item (e.g. 122 for "+122 to maximum Life"). */
  rolled_value: number;
  /** Whether this mod starts checked. Defaults to true. */
  default_enabled?: boolean;
}

interface ModRowState {
  mod: TradeDialogMod;
  enabled: boolean;
  /** Strictness percent (50-100). 80 is the default. */
  strictness: number;
}

interface Props {
  opened: boolean;
  onClose: () => void;
  /** Display title — usually the item name or "Heavy Belt", "6L Body", etc. */
  title: string;
  /** Unique name for the search (set when matching a unique by name). */
  itemName?: string | null;
  /** Base type — for rares + uniques where Trade needs the base. */
  itemType?: string | null;
  /**
   * Pre-extracted mods (skip the server round-trip).
   * Use this when the caller already knows the dialog rows.
   */
  mods?: TradeDialogMod[];
  /**
   * Raw PoB mod text lines. Sent to ``/fob/extract-trade-mods`` on
   * mount; the server replies with the typed dialog rows. Either
   * ``mods`` or ``rawMods`` should be supplied — if both are set,
   * ``mods`` wins and the fetch is skipped.
   */
  rawMods?: string[];
  /** Allow the user to require a 6L? */
  allowLinks?: boolean;
}

export function TradeSearchDialog({
  opened,
  onClose,
  title,
  itemName,
  itemType,
  mods,
  rawMods,
  allowLinks = false,
}: Props) {
  const [rows, setRows] = useState<ModRowState[]>(() =>
    (mods ?? []).map((m) => ({
      mod: m,
      enabled: m.default_enabled ?? true,
      strictness: 80,
    })),
  );
  const [requireLinks, setRequireLinks] = useState(false);
  const [linkCount, setLinkCount] = useState(6);
  const [loading, setLoading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Lazy-load the dialog rows from raw mod text when ``rawMods`` is
  // provided and ``mods`` is empty. Skipped entirely when the caller
  // already supplied rows (component is identity-stable per item via
  // the ``key=`` set by StageCard).
  useEffect(() => {
    if (!opened) return;
    if (mods && mods.length > 0) return;
    if (!rawMods || rawMods.length === 0) return;
    // Already extracted at least once for this mount — skip refetch.
    if (rows.length > 0) return;

    let cancelled = false;
    setExtracting(true);
    extractTradeMods(rawMods)
      .then((resp) => {
        if (cancelled) return;
        setRows(
          resp.mods.map((m) => ({
            mod: {
              stat_id: m.stat_id,
              label: m.label,
              rolled_value: m.value,
              default_enabled: true,
            },
            enabled: true,
            strictness: 80,
          })),
        );
      })
      .catch(() => {
        // Extraction is non-fatal: the dialog still works with name/type.
        if (!cancelled) setRows([]);
      })
      .finally(() => {
        if (!cancelled) setExtracting(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, rawMods, mods]);

  function setRow(idx: number, patch: Partial<ModRowState>) {
    setRows((cur) =>
      cur.map((r, i) => (i === idx ? { ...r, ...patch } : r)),
    );
  }

  async function handleSearch() {
    setError(null);
    setLoading(true);
    try {
      const filters: TradeSearchModFilter[] = rows
        .filter((r) => r.enabled)
        .map((r) => {
          const min = r.mod.rolled_value * (r.strictness / 100);
          // Round to 1 decimal for cleanliness on the trade site.
          return {
            stat_id: r.mod.stat_id,
            min: Math.max(1, Math.round(min * 10) / 10),
            max: null,
          };
        });

      if (!itemName && !itemType && filters.length === 0) {
        setError(
          "Niente da cercare: attiva almeno un mod o specifica un nome/base.",
        );
        return;
      }

      const resp = await tradeSearch({
        item_name: itemName ?? null,
        item_type: itemType ?? null,
        mods: filters,
        online_only: true,
        min_links: requireLinks ? linkCount : null,
      });

      // Open the official trade page in a new tab.
      window.open(resp.url, "_blank", "noopener,noreferrer");
      onClose();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const enabledCount = rows.filter((r) => r.enabled).length;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap={8}>
          <ThemeIcon variant="light" color="astral" size="md" radius="xl">
            <IconSearch size={16} />
          </ThemeIcon>
          <Text fw={600}>Cerca su Trade — {title}</Text>
        </Group>
      }
      size="lg"
      centered
      overlayProps={{ backgroundOpacity: 0.7, blur: 4 }}
    >
      <Stack gap="md">
        {/* Identity summary */}
        <Group gap={6} wrap="wrap">
          {itemName && (
            <Badge color="grape" variant="light">
              Nome: {itemName}
            </Badge>
          )}
          {itemType && (
            <Badge color="cyan" variant="light">
              Base: {itemType}
            </Badge>
          )}
          {!itemName && !itemType && (
            <Badge color="gray" variant="outline">
              Solo filtri stat
            </Badge>
          )}
        </Group>

        {/* Loader while we extract mod rows from raw text */}
        {extracting && (
          <Group gap={8}>
            <Loader size="xs" />
            <Text size="xs" c="dimmed">
              Estrazione mod in corso...
            </Text>
          </Group>
        )}

        {/* Mod toggles */}
        {rows.length > 0 && !extracting && (
          <Stack gap={4}>
            <Text size="xs" c="dimmed" fw={500} tt="uppercase">
              Mod ({enabledCount}/{rows.length} attivi)
            </Text>
            <ScrollArea.Autosize mah={320}>
              <Stack gap="sm" pr="md">
                {rows.map((r, i) => (
                  <Stack
                    key={`${r.mod.stat_id}-${i}`}
                    gap={4}
                    p="xs"
                    style={{
                      borderRadius: 8,
                      backgroundColor: r.enabled
                        ? "rgba(110, 38, 255, 0.06)"
                        : "transparent",
                      border: "1px solid rgba(110, 38, 255, 0.15)",
                    }}
                  >
                    <Group justify="space-between" wrap="nowrap" gap={8}>
                      <Switch
                        size="sm"
                        checked={r.enabled}
                        onChange={(e) =>
                          setRow(i, { enabled: e.currentTarget.checked })
                        }
                        label={
                          <Text size="sm" fw={500}>
                            {r.mod.label}
                          </Text>
                        }
                      />
                      <Badge variant="light" color="astral">
                        ≥{" "}
                        {Math.round(
                          (r.mod.rolled_value * r.strictness) / 100,
                        )}
                      </Badge>
                    </Group>
                    {r.enabled && (
                      <Group gap="sm" wrap="nowrap" pl={42}>
                        <Text size="xs" c="dimmed" miw={70}>
                          Strictness
                        </Text>
                        <Slider
                          flex={1}
                          size="sm"
                          min={50}
                          max={100}
                          step={5}
                          marks={[
                            { value: 50 },
                            { value: 80, label: "80%" },
                            { value: 100, label: "100%" },
                          ]}
                          value={r.strictness}
                          onChange={(v) => setRow(i, { strictness: v })}
                          label={(v) => `${v}%`}
                        />
                      </Group>
                    )}
                  </Stack>
                ))}
              </Stack>
            </ScrollArea.Autosize>
          </Stack>
        )}

        {rows.length === 0 && !extracting && (
          <Text size="sm" c="dimmed">
            Questo item non ha mod riconosciuti dal pattern table — la
            ricerca userà solo nome/base.
          </Text>
        )}

        {/* Links option */}
        {allowLinks && (
          <Group gap="md">
            <Switch
              size="sm"
              checked={requireLinks}
              onChange={(e) => setRequireLinks(e.currentTarget.checked)}
              label="Richiedi link socket"
            />
            {requireLinks && (
              <Group gap="xs">
                {[5, 6].map((n) => (
                  <Button
                    key={n}
                    size="xs"
                    variant={linkCount === n ? "filled" : "light"}
                    color="astral"
                    onClick={() => setLinkCount(n)}
                  >
                    {n}L
                  </Button>
                ))}
              </Group>
            )}
          </Group>
        )}

        {error && (
          <Alert color="red" variant="light">
            {error}
          </Alert>
        )}

        {/* CTA */}
        <Group justify="flex-end" gap="sm">
          <Button variant="subtle" color="gray" onClick={onClose}>
            Annulla
          </Button>
          <Button
            color="astral"
            rightSection={<IconExternalLink size={16} />}
            loading={loading}
            onClick={handleSearch}
          >
            Apri su Trade
          </Button>
        </Group>

        <Text size="xs" c="dimmed" ta="center">
          Si apre una nuova scheda su pathofexile.com con i filtri pre-applicati.
        </Text>
      </Stack>
    </Modal>
  );
}
