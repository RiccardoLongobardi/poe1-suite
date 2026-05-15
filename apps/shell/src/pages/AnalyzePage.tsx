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
import { analyzePob } from "../api/fob";
import type {
  AnalyzePobResponse,
  ItemRarity,
  PobItem,
  PobSkillGroup,
  PobSnapshot,
} from "../api/types";
import { ErrorBoundary } from "../components/ErrorBoundary";

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function compactNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(Math.round(n));
}

/** Left-border colour per rarity — the only rarity decoration we use. */
function rarityColor(rarity: ItemRarity): string {
  switch (rarity) {
    case "unique":
      return "#af6025";
    case "rare":
      return "#d9c850";
    case "magic":
      return "#8888ff";
    default:
      return "#7a7a7a";
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
              style={{ width: 6, height: 2, background: "var(--mantine-color-dark-2)" }}
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
          Corrotto
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
}: {
  label: string;
  item: PobItem | undefined;
  style?: React.CSSProperties;
}) {
  if (!item) {
    return (
      <Box
        style={{
          borderLeft: "3px solid var(--mantine-color-dark-4)",
          padding: "6px 10px",
          background: "var(--mantine-color-dark-7)",
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
          slot vuoto
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
        style={{
          borderLeft: `3px solid ${rarityColor(item.rarity)}`,
          padding: "6px 10px",
          background: "var(--mantine-color-dark-6)",
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
          {item.corrupted && (
            <Badge color="red" size="xs" variant="filled" px={5}>
              C
            </Badge>
          )}
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

/** One stat tile in the key-stats grid. */
function StatTile({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <Group gap={8} wrap="nowrap">
      <Box c="astral.4">{icon}</Box>
      <Stack gap={0}>
        <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
          {label}
        </Text>
        <Text size="sm" fw={700}>
          {value > 0 ? compactNumber(value) : "—"}
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
  const title = group.label?.trim() || group.slot?.trim() || "Gruppo gemme";
  return (
    <Group
      gap={8}
      wrap="wrap"
      align="center"
      p={6}
      style={{
        borderRadius: 6,
        background: isMain
          ? "var(--mantine-color-dark-5)"
          : "var(--mantine-color-dark-7)",
      }}
    >
      <Group gap={4} w={130} style={{ flexShrink: 0 }} wrap="nowrap">
        <Text size="xs" fw={600} c="dimmed" truncate>
          {title}
        </Text>
        {isMain && (
          <Badge size="xs" color="astral" variant="light">
            main
          </Badge>
        )}
      </Group>
      {group.gems.map((gem, i) => (
        <Badge
          key={`${gem.skill_id}-${i}`}
          variant={gem.is_support ? "outline" : "filled"}
          color={gem.is_support ? "gray" : "astral"}
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

function topDamageType(stats: Record<string, number>): { label: string; value: number } {
  const phys = stats.PhysicalDPS ?? 0;
  const ele = (stats.FireDPS ?? 0) + (stats.ColdDPS ?? 0) + (stats.LightningDPS ?? 0);
  const chaos = stats.ChaosDPS ?? 0;
  const max = Math.max(phys, ele, chaos);
  if (max === 0) return { label: "Danno tipo", value: 0 };
  if (max === phys) return { label: "DPS fisico", value: phys };
  if (max === ele) return { label: "DPS elementale", value: ele };
  return { label: "DPS caos", value: chaos };
}

function BuildDashboard({ data }: { data: AnalyzePobResponse }) {
  const snap: PobSnapshot = data.snapshot;
  const slots = snap.items_by_slot;
  const dmg = topDamageType(snap.stats);
  const enabledGroups = snap.skills.filter((g) => g.enabled);
  const treeUrl = snap.tree?.url?.trim();

  return (
    <Stack gap="md">
      {/* Two-column area: header/stats | gear */}
      <Box
        style={{
          display: "grid",
          gap: 16,
          gridTemplateColumns: "minmax(0, 1fr)",
        }}
        className="analyze-dashboard"
      >
        {/* Left — character header + stats */}
        <Card withBorder radius="md" p="md">
          <Stack gap="sm">
            <Group gap={8} align="center">
              <Title order={3}>{snap.ascendancy ?? snap.character_class}</Title>
              <Badge color="gray" variant="outline" size="lg">
                livello {snap.level}
              </Badge>
            </Group>
            <Group gap={6}>
              {snap.ascendancy && (
                <Badge color="indigo" variant="light">
                  {snap.character_class}
                </Badge>
              )}
              <Badge color="teal" variant="light">
                bandito: {snap.bandit}
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

            <Divider label="Statistiche chiave" labelPosition="left" />
            <Box
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))",
                gap: 12,
              }}
            >
              <StatTile
                icon={<IconHeart size={20} />}
                label="Vita"
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
                label="DPS totale"
                value={bestDps(snap.stats)}
              />
              <StatTile
                icon={<IconBolt size={20} />}
                label={dmg.label}
                value={dmg.value}
              />
              <StatTile
                icon={<IconShield size={20} />}
                label="Armatura"
                value={snap.stats.Armour ?? 0}
              />
              <StatTile
                icon={<IconEye size={20} />}
                label="Evasione"
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
                color="astral"
                leftSection={<IconExternalLink size={15} />}
                mt={4}
              >
                Apri albero passivo
              </Button>
            )}

            {snap.notes.trim() && (
              <Accordion variant="contained" mt={4}>
                <Accordion.Item value="notes">
                  <Accordion.Control>Note build</Accordion.Control>
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
        <Card withBorder radius="md" p="md">
          <Stack gap="sm">
            <Divider label="Equipaggiamento" labelPosition="left" />
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
              <GearCell label="Elmo" item={slots.helmet} style={{ gridArea: "helmet" }} />
              <GearCell
                label="Arma princ."
                item={slots.weapon_main}
                style={{ gridArea: "wmain" }}
              />
              <GearCell label="Corpo" item={slots.body_armour} style={{ gridArea: "body" }} />
              <GearCell
                label="Arma sec."
                item={slots.weapon_offhand}
                style={{ gridArea: "woff" }}
              />
              <GearCell label="Guanti" item={slots.gloves} style={{ gridArea: "gloves" }} />
              <GearCell label="Stivali" item={slots.boots} style={{ gridArea: "boots" }} />
              <GearCell label="Cintura" item={slots.belt} style={{ gridArea: "belt" }} />
              <GearCell label="Amuleto" item={slots.amulet} style={{ gridArea: "amulet" }} />
              <GearCell label="Anello" item={slots.ring} style={{ gridArea: "ring" }} />
            </Box>

            {snap.flasks.length > 0 && (
              <>
                <Divider label="Flasche" labelPosition="left" />
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
                    />
                  ))}
                </Box>
              </>
            )}

            {snap.jewels.length > 0 && (
              <>
                <Divider label={`Gioielli (${snap.jewels.length})`} labelPosition="left" />
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
                      label="Gioiello"
                      item={jewel.item}
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
        <Card withBorder radius="md" p="md">
          <Stack gap={8}>
            <Divider label="Gemme e collegamenti" labelPosition="left" />
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
  const [input, setInput] = useState("");
  const [result, setResult] = useState<AnalyzePobResponse | null>(null);
  const [editing, setEditing] = useState(true);

  const mut = useMutation({
    mutationFn: () => analyzePob(input),
    onSuccess: (data) => {
      setResult(data);
      setEditing(false);
    },
  });

  const submit = () => {
    if (input.trim()) mut.mutate();
  };

  return (
    <Stack gap="md">
      <Title order={3}>Analizza PoB</Title>

      {editing ? (
        <>
          <Text c="dimmed" size="sm">
            Incolla un codice di esportazione PoB oppure un link pobb.in /
            pastebin.
          </Text>
          <Group align="flex-end" gap="sm" wrap="nowrap">
            <TextInput
              flex={1}
              placeholder="https://pobb.in/xxxx  oppure  eNqtVct…"
              value={input}
              onChange={(e) => setInput(e.currentTarget.value)}
              styles={{ input: { fontFamily: "monospace" } }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) submit();
              }}
            />
            <Button onClick={submit} loading={mut.isPending} disabled={!input.trim()}>
              Analizza
            </Button>
          </Group>
          <Text size="xs" c="dimmed">
            Ctrl+Enter per inviare
          </Text>
        </>
      ) : (
        <Group gap={8} wrap="nowrap">
          <Code style={{ overflow: "hidden", textOverflow: "ellipsis" }}>
            {result?.build.source_id ?? input.slice(0, 48)}
          </Code>
          <Anchor size="xs" onClick={() => setEditing(true)} style={{ flexShrink: 0 }}>
            modifica
          </Anchor>
        </Group>
      )}

      {mut.isError && (
        <Alert color="red" title="Errore">
          {mut.error.message}
        </Alert>
      )}

      {result && (
        <ErrorBoundary label="Errore nel rendering della build">
          <BuildDashboard data={result} />
        </ErrorBoundary>
      )}
    </Stack>
  );
}
