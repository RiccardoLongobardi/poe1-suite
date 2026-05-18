/**
 * AnalyzePage — POST /fob/analyze-pob
 *
 * Accepts a raw PoB export code or a pobb.in / pastebin link and renders
 * a full PoB-style build dashboard from the returned `PobSnapshot`:
 * character header + key stats, an equipment grid with per-item
 * tooltips, flasks, tree jewels, and the skill-link groups.
 *
 * Frontend-only — no new backend endpoints; the snapshot already
 * carries everything `POST /fob/analyze-pob` parsed from the PoB code.
 */

import {
  Accordion,
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Code,
  Divider,
  Group,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconBolt,
  IconExternalLink,
  IconEye,
  IconHeart,
  IconShield,
  IconShieldHalf,
  IconSword,
} from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { getDetail, parsePoeNinjaCharacterUrl } from "../api/builds";
import { analyzePob } from "../api/fob";
import { usePageStore } from "../store/pageStore";
import type {
  AnalyzePobResponse,
  ItemRarity,
  PobItem,
  PobSkillGroup,
  PobSnapshot,
} from "../api/types";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { TradeSearchDialog } from "../components/TradeSearchDialog";
import { useCountUp } from "../hooks/useCountUp";
import { useT } from "../i18n";

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function compactNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(Math.round(n));
}

/** Left-border colour per rarity — PoE1 rarity palette (Step 22a tokens). */
function rarityColor(rarity: ItemRarity): string {
  switch (rarity) {
    case "unique":
      return "var(--vs-unique)";
    case "rare":
      return "var(--vs-rare)";
    case "magic":
      return "var(--vs-magic)";
    default:
      return "var(--vs-normal)";
  }
}

const SOCKET_COLOR: Record<string, string> = {
  R: "#d32f2f",
  G: "#388e3c",
  B: "#1976d2",
  W: "#e0e0e0",
  A: "#3a2a4d",
};

// ---------------------------------------------------------------------------
// Small presentational pieces
// ---------------------------------------------------------------------------

/** Render a PoB socket string ("R-G-B B") as coloured dots + link bars. */
function SocketDots({ sockets }: { sockets: string }) {
  const chars = [...sockets];
  return (
    <Group gap={2} wrap="nowrap" align="center">
      {chars.map((ch, i) => {
        const key = `${ch}-${i}`;
        if (ch === "-") {
          return (
            <Box
              key={key}
              style={{ width: 6, height: 2, background: "var(--vs-border)" }}
            />
          );
        }
        if (ch === " ") return <Box key={key} style={{ width: 4 }} />;
        const color = SOCKET_COLOR[ch.toUpperCase()];
        if (!color) return null;
        return (
          <Box
            key={key}
            style={{
              width: 9,
              height: 9,
              borderRadius: "50%",
              background: color,
              border: "1px solid rgba(0,0,0,0.45)",
            }}
          />
        );
      })}
    </Group>
  );
}

/** Tooltip body: base type, item level, implicits / explicits. */
function ItemTooltipBody({ item }: { item: PobItem }) {
  const t = useT();
  return (
    <Stack gap={4} style={{ maxWidth: 320 }}>
      <Text size="xs" fw={600}>
        {item.name ?? item.base_type}
      </Text>
      {item.name && (
        <Text size="xs" c="dimmed">
          {item.base_type}
        </Text>
      )}
      {item.item_level != null && (
        <Text size="xs" c="dimmed">
          Item level {item.item_level}
        </Text>
      )}
      {item.implicits.length > 0 && (
        <>
          <Divider my={2} />
          {item.implicits.map((line, i) => (
            <Text key={`impl-${i}`} size="xs" c="grape.4">
              {line}
            </Text>
          ))}
        </>
      )}
      {item.explicits.length > 0 && (
        <>
          <Divider my={2} />
          {item.explicits.map((line, i) => (
            <Text key={`expl-${i}`} size="xs">
              {line}
            </Text>
          ))}
        </>
      )}
      {item.corrupted && (
        <Text size="xs" c="red.5" fw={600}>
          {t({ it: "Corrotto", en: "Corrupted" })}
        </Text>
      )}
    </Stack>
  );
}

/** One cell of the equipment grid. */
function GearCell({
  label,
  item,
  style,
  onTrade,
}: {
  label: string;
  item: PobItem | undefined;
  style?: React.CSSProperties;
  onTrade: (item: PobItem) => void;
}) {
  const t = useT();
  if (!item) {
    return (
      <Box
        style={{
          borderLeft: "3px solid var(--vs-border-faint)",
          padding: "6px 10px",
          background: "var(--vs-surface-1)",
          borderRadius: 4,
          minWidth: 0,
          overflow: "hidden",
          ...style,
        }}
      >
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
          {label}
        </Text>
        <Text size="xs" c="dimmed" fs="italic">
          {t({ it: "slot vuoto", en: "empty slot" })}
        </Text>
      </Box>
    );
  }
  return (
    <Tooltip
      multiline
      withArrow
      label={<ItemTooltipBody item={item} />}
      transitionProps={{ duration: 120 }}
    >
      <Box
        className={item.rarity === "unique" ? "vs-unique-shimmer" : undefined}
        style={{
          borderLeft: `3px solid ${rarityColor(item.rarity)}`,
          padding: "6px 10px",
          background: "var(--vs-surface-2)",
          borderRadius: 4,
          cursor: "help",
          minWidth: 0,
          overflow: "hidden",
          ...style,
        }}
      >
        <Group justify="space-between" gap={4} wrap="nowrap">
          <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
            {label}
          </Text>
          <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
            {item.corrupted && (
              <Badge color="red" size="xs" variant="filled" px={5}>
                C
              </Badge>
            )}
            <ActionIcon
              variant="subtle"
              color="ember"
              size="xs"
              title={t({
                it: "Cerca questo item su pathofexile.com/trade",
                en: "Search this item on pathofexile.com/trade",
              })}
              aria-label={t({ it: "Cerca su Trade", en: "Search on Trade" })}
              onClick={(e) => {
                e.stopPropagation();
                onTrade(item);
              }}
            >
              <IconExternalLink size={11} />
            </ActionIcon>
          </Group>
        </Group>
        <Text size="xs" fw={600} truncate>
          {item.name ?? item.base_type}
        </Text>
        {item.name && (
          <Text size="10px" c="dimmed" truncate>
            {item.base_type}
          </Text>
        )}
        {item.sockets && (
          <Box mt={3}>
            <SocketDots sockets={item.sockets} />
          </Box>
        )}
      </Box>
    </Tooltip>
  );
}

/** One stat tile in the key-stats grid — value counts up on render. */
function StatTile({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  const animated = useCountUp(value);
  return (
    <Group gap={8} wrap="nowrap">
      <Box c="ember.4">{icon}</Box>
      <Stack gap={0}>
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
          {label}
        </Text>
        <Text className="mono" size="sm" fw={700}>
          {value > 0 ? compactNumber(animated) : "—"}
        </Text>
      </Stack>
    </Group>
  );
}

/** One skill-link group as a horizontal gem strip. */
function SkillGroupStrip({
  group,
  isMain,
}: {
  group: PobSkillGroup;
  isMain: boolean;
}) {
  const t = useT();
  const title =
    group.label?.trim() ||
    group.slot?.trim() ||
    t({ it: "Gruppo gemme", en: "Gem group" });
  return (
    <Group
      gap={8}
      wrap="wrap"
      align="center"
      p={6}
      style={{
        borderRadius: 6,
        background: isMain
          ? "var(--vs-surface-3)"
          : "var(--vs-surface-1)",
      }}
    >
      <Group gap={4} w={130} style={{ flexShrink: 0 }} wrap="nowrap">
        <Text size="xs" fw={600} c="dimmed" truncate>
          {title}
        </Text>
        {isMain && (
          <Badge size="xs" color="ember" variant="light">
            main
          </Badge>
        )}
      </Group>
      {group.gems.map((gem, i) => (
        <Badge
          key={`${gem.skill_id}-${i}`}
          variant={gem.is_support ? "outline" : "filled"}
          color={gem.is_support ? "gray" : "ember"}
          size="sm"
          style={{ opacity: gem.enabled ? 1 : 0.4, textTransform: "none" }}
        >
          {gem.name} {gem.level}/{gem.quality}
        </Badge>
      ))}
    </Group>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

function bestDps(stats: Record<string, number>): number {
  return (
    stats.FullDPS || stats.CombinedDPS || stats.TotalDPS || stats.AverageHit || 0
  );
}

type DamageKind = "none" | "phys" | "ele" | "chaos";

function topDamageType(stats: Record<string, number>): {
  kind: DamageKind;
  value: number;
} {
  const phys = stats.PhysicalDPS ?? 0;
  const ele = (stats.FireDPS ?? 0) + (stats.ColdDPS ?? 0) + (stats.LightningDPS ?? 0);
  const chaos = stats.ChaosDPS ?? 0;
  const max = Math.max(phys, ele, chaos);
  if (max === 0) return { kind: "none", value: 0 };
  if (max === phys) return { kind: "phys", value: phys };
  if (max === ele) return { kind: "ele", value: ele };
  return { kind: "chaos", value: chaos };
}

function BuildDashboard({ data }: { data: AnalyzePobResponse }) {
  const t = useT();
  const snap: PobSnapshot = data.snapshot;
  const slots = snap.items_by_slot;
  const dmg = topDamageType(snap.stats);
  const dmgLabel = t(
    {
      none: { it: "Danno tipo", en: "Damage type" },
      phys: { it: "DPS fisico", en: "Physical DPS" },
      ele: { it: "DPS elementale", en: "Elemental DPS" },
      chaos: { it: "DPS caos", en: "Chaos DPS" },
    }[dmg.kind],
  );
  const enabledGroups = snap.skills.filter((g) => g.enabled);
  const treeUrl = snap.tree?.url?.trim();

  // The equipment item whose Trade-search dialog is open (null = closed).
  const [tradeItem, setTradeItem] = useState<PobItem | null>(null);

  return (
    <Stack gap="md">
      {tradeItem && (
        <TradeSearchDialog
          key={tradeItem.pob_id}
          opened
          onClose={() => setTradeItem(null)}
          title={tradeItem.name ?? tradeItem.base_type}
          itemName={tradeItem.rarity === "unique" ? tradeItem.name : null}
          itemType={tradeItem.base_type}
          rawMods={[...tradeItem.implicits, ...tradeItem.explicits]}
        />
      )}
      {/* Sticky character header — a full-width bar above the dashboard
          so it stays visible while scrolling through gear/skills
          without covering the left card's own stat tiles. */}
      <Box
        className="vs-card-reveal vs-glass"
        style={
          {
            position: "sticky",
            top: 56,
            zIndex: 10,
            padding: "10px 14px",
            border: "1px solid var(--vs-border)",
            borderRadius: "var(--vs-radius-md)",
            "--card-index": 0,
          } as React.CSSProperties
        }
      >
        <Group gap={8} align="center">
          <Title order={3}>{snap.ascendancy ?? snap.character_class}</Title>
          <Badge color="gray" variant="outline" size="lg">
            {t({ it: "livello", en: "level" })} {snap.level}
          </Badge>
        </Group>
        <Group gap={6} mt={6}>
          {snap.ascendancy && (
            <Badge color="indigo" variant="light">
              {snap.character_class}
            </Badge>
          )}
          <Badge color="teal" variant="light">
            {t({ it: "bandito", en: "bandit" })}: {snap.bandit}
          </Badge>
          {snap.pantheon.major && (
            <Badge color="grape" variant="light">
              {snap.pantheon.major}
            </Badge>
          )}
          {snap.pantheon.minor && (
            <Badge color="grape" variant="light">
              {snap.pantheon.minor}
            </Badge>
          )}
        </Group>
      </Box>

      {/* Two-column area: stats | gear */}
      <Box
        style={{
          display: "grid",
          gap: 16,
          gridTemplateColumns: "minmax(0, 1fr)",
        }}
        className="analyze-dashboard"
      >
        {/* Left — key stats */}
        <Card
          withBorder
          radius="md"
          p="md"
          className="vs-card-reveal"
          style={{ "--card-index": 1 } as React.CSSProperties}
        >
          <Stack gap="sm">
            <Divider
              label={t({ it: "Statistiche chiave", en: "Key stats" })}
              labelPosition="left"
            />
            <Box
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
                gap: 12,
              }}
            >
              <StatTile
                icon={<IconHeart size={20} />}
                label={t({ it: "Vita", en: "Life" })}
                value={snap.stats.Life ?? 0}
              />
              <StatTile
                icon={<IconShieldHalf size={20} />}
                label="Energy Shield"
                value={snap.stats.EnergyShield ?? 0}
              />
              <StatTile
                icon={<IconShield size={20} />}
                label="EHP"
                value={snap.stats.TotalEHP ?? 0}
              />
              <StatTile
                icon={<IconSword size={20} />}
                label={t({ it: "DPS totale", en: "Total DPS" })}
                value={bestDps(snap.stats)}
              />
              <StatTile
                icon={<IconBolt size={20} />}
                label={dmgLabel}
                value={dmg.value}
              />
              <StatTile
                icon={<IconShield size={20} />}
                label={t({ it: "Armatura", en: "Armour" })}
                value={snap.stats.Armour ?? 0}
              />
              <StatTile
                icon={<IconEye size={20} />}
                label={t({ it: "Evasione", en: "Evasion" })}
                value={snap.stats.Evasion ?? 0}
              />
            </Box>

            {treeUrl && (
              <Button
                component="a"
                href={treeUrl}
                target="_blank"
                rel="noopener noreferrer"
                variant="light"
                color="ember"
                leftSection={<IconExternalLink size={15} />}
                mt={4}
              >
                {t({ it: "Apri albero passivo", en: "Open passive tree" })}
              </Button>
            )}

            {snap.notes.trim() && (
              <Accordion variant="contained" mt={4}>
                <Accordion.Item value="notes">
                  <Accordion.Control>
                    {t({ it: "Note build", en: "Build notes" })}
                  </Accordion.Control>
                  <Accordion.Panel>
                    <Text size="xs" style={{ whiteSpace: "pre-wrap" }}>
                      {snap.notes}
                    </Text>
                  </Accordion.Panel>
                </Accordion.Item>
              </Accordion>
            )}
          </Stack>
        </Card>

        {/* Right — gear grid + flasks + jewels */}
        <Card
          withBorder
          radius="md"
          p="md"
          className="vs-card-reveal"
          style={{ "--card-index": 2 } as React.CSSProperties}
        >
          <Stack gap="sm">
            <Divider
              label={t({ it: "Equipaggiamento", en: "Equipment" })}
              labelPosition="left"
            />
            <Box
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                gridTemplateAreas: [
                  '".      helmet ."',
                  '"wmain  body   woff"',
                  '"gloves .      boots"',
                  '"belt   belt   belt"',
                  '"amulet ring   ring"',
                ].join(" "),
                gap: 8,
              }}
            >
              <GearCell
                label={t({ it: "Elmo", en: "Helmet" })}
                item={slots.helmet}
                style={{ gridArea: "helmet" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Arma princ.", en: "Main weapon" })}
                item={slots.weapon_main}
                style={{ gridArea: "wmain" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Corpo", en: "Body" })}
                item={slots.body_armour}
                style={{ gridArea: "body" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Arma sec.", en: "Off-hand" })}
                item={slots.weapon_offhand}
                style={{ gridArea: "woff" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Guanti", en: "Gloves" })}
                item={slots.gloves}
                style={{ gridArea: "gloves" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Stivali", en: "Boots" })}
                item={slots.boots}
                style={{ gridArea: "boots" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Cintura", en: "Belt" })}
                item={slots.belt}
                style={{ gridArea: "belt" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Amuleto", en: "Amulet" })}
                item={slots.amulet}
                style={{ gridArea: "amulet" }}
                onTrade={setTradeItem}
              />
              <GearCell
                label={t({ it: "Anello", en: "Ring" })}
                item={slots.ring}
                style={{ gridArea: "ring" }}
                onTrade={setTradeItem}
              />
            </Box>

            {snap.flasks.length > 0 && (
              <>
                <Divider
                  label={t({ it: "Flasche", en: "Flasks" })}
                  labelPosition="left"
                />
                <Box
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(5, 1fr)",
                    gap: 6,
                  }}
                >
                  {snap.flasks.map((flask, i) => (
                    <GearCell
                      key={`flask-${flask.pob_id}-${i}`}
                      label={`Flask ${i + 1}`}
                      item={flask}
                      onTrade={setTradeItem}
                    />
                  ))}
                </Box>
              </>
            )}

            {snap.jewels.length > 0 && (
              <>
                <Divider
                  label={t({
                    it: `Gioielli (${snap.jewels.length})`,
                    en: `Jewels (${snap.jewels.length})`,
                  })}
                  labelPosition="left"
                />
                <Box
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                    gap: 6,
                  }}
                >
                  {snap.jewels.map((jewel, i) => (
                    <GearCell
                      key={`jewel-${jewel.item.pob_id}-${i}`}
                      label={t({ it: "Gioiello", en: "Jewel" })}
                      item={jewel.item}
                      onTrade={setTradeItem}
                    />
                  ))}
                </Box>
              </>
            )}
          </Stack>
        </Card>
      </Box>

      {/* Full-width — skill links */}
      {enabledGroups.length > 0 && (
        <Card
          withBorder
          radius="md"
          p="md"
          className="vs-card-reveal"
          style={{ "--card-index": 4 } as React.CSSProperties}
        >
          <Stack gap={8}>
            <Divider
              label={t({ it: "Gemme e collegamenti", en: "Gems and links" })}
              labelPosition="left"
            />
            {enabledGroups.map((group) => (
              <SkillGroupStrip
                key={group.socket_group}
                group={group}
                isMain={group.socket_group === snap.main_skill_group_index}
              />
            ))}
          </Stack>
        </Card>
      )}
    </Stack>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AnalyzePage() {
  const t = useT();
  // Cross-route persistent state — survives navigation away and back.
  const { input, result, editing } = usePageStore((s) => s.analyze);
  const setAnalyze = usePageStore((s) => s.setAnalyze);

  // Resolve the input then analyse it. The input may be:
  //  - a raw PoB export code or a pobb.in / pastebin link → passed
  //    straight to /fob/analyze-pob (it already accepts those);
  //  - a poe.ninja character URL → resolved client-side to a PoB code
  //    via /builds/detail before analysing (no new backend endpoint).
  const mut = useMutation({
    mutationFn: async () => {
      const raw = input.trim();
      if (/^https?:\/\//i.test(raw) && /poe\.ninja/i.test(raw)) {
        const parsed = parsePoeNinjaCharacterUrl(raw);
        if (!parsed) {
          throw new Error(
            t({
              it: "Link poe.ninja non valido — incolla l'URL di un personaggio (…/character/<account>/<nome>).",
              en: "Invalid poe.ninja link — paste a character URL (…/character/<account>/<name>).",
            }),
          );
        }
        const code = await getDetail(parsed.account, parsed.character);
        return analyzePob(code);
      }
      return analyzePob(raw);
    },
    onSuccess: (data) => {
      setAnalyze({ result: data, editing: false });
    },
  });

  const submit = () => {
    if (input.trim()) mut.mutate();
  };

  return (
    <Stack gap="md">
      <Title order={3}>{t({ it: "Analizza PoB", en: "Analyse PoB" })}</Title>

      {editing ? (
        <>
          <Text c="dimmed" size="sm">
            {t({
              it: "Incolla un codice di esportazione PoB, un link pobb.in / pastebin oppure l'URL di un personaggio poe.ninja.",
              en: "Paste a PoB export code, a pobb.in / pastebin link, or a poe.ninja character URL.",
            })}
          </Text>
          <Group align="flex-end" gap="sm" wrap="nowrap">
            <TextInput
              flex={1}
              placeholder="https://pobb.in/xxxx  ·  poe.ninja/builds/…  ·  eNqtVct…"
              value={input}
              onChange={(e) => setAnalyze({ input: e.currentTarget.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
              }}
            />
            <Button onClick={submit} loading={mut.isPending} disabled={!input.trim()}>
              {t({ it: "Analizza", en: "Analyse" })}
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            {t({ it: "Ctrl+Enter per inviare", en: "Ctrl+Enter to submit" })}
          </Text>
        </>
      ) : (
        <Group gap={8} wrap="nowrap">
          <Code style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
            {result?.build.source_id ?? input.slice(0, 48)}
          </Code>
          <Anchor
            size="xs"
            onClick={() => setAnalyze({ editing: true })}
            style={{ flexShrink: 0 }}
          >
            {t({ it: "modifica", en: "edit" })}
          </Anchor>
        </Group>
      )}

      {mut.isError && (
        <Alert color="red" title={t({ it: "Errore", en: "Error" })}>
          {mut.error.message}
        </Alert>
      )}

      {mut.isPending && (
        <Card withBorder radius="md" p="md">
          <Stack gap="sm">
            <Box className="vs-skeleton vs-skeleton-heading" />
            <Box className="vs-skeleton vs-skeleton-text" />
            <Box className="vs-skeleton vs-skeleton-text" />
            <Box className="vs-skeleton vs-skeleton-text" />
          </Stack>
        </Card>
      )}

      {result && (
        <ErrorBoundary
          label={t({
            it: "Errore nel rendering della build",
            en: "Build rendering error",
          })}
        >
          <BuildDashboard data={result} />
        </ErrorBoundary>
      )}
    </Stack>
  );
}
