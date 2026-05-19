/**
 * GearCard — one cell of the Analyze equipment / flask / jewel grid.
 *
 * Compact card by default. **Hovering** it pops a details panel
 * (item level, implicits, explicits, corruption, unique price) — like
 * the old tooltip. **Clicking** the card *pins* that panel so it stays
 * open after the mouse leaves; clicking again (or clicking elsewhere)
 * unpins it. One card pinned at a time per dashboard — the parent owns
 * the `pinned` flag.
 */

import { Badge, Box, Divider, Group, Popover, Stack, Text } from "@mantine/core";
import { IconExternalLink, IconPinned } from "@tabler/icons-react";
import { useState } from "react";
import type { ItemRarity, PobItem } from "../../api/types";
import { useT } from "../../i18n";
import { PriceBadge } from "../PriceBadge";

const SOCKET_COLOR: Record<string, string> = {
  R: "#d32f2f",
  G: "#388e3c",
  B: "#1976d2",
  W: "#e0e0e0",
  A: "#3a2a4d",
};

/** Left-border colour per rarity — PoE1 rarity palette. */
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

/** Render a PoB socket string ("R-G-B B") as coloured dots + link bars. */
function SocketDots({ sockets }: { sockets: string }) {
  return (
    <Group gap={2} wrap="nowrap" align="center">
      {[...sockets].map((ch, i) => {
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

/** The hover/pin details panel body. */
function ItemDetails({ item, pinned }: { item: PobItem; pinned: boolean }) {
  const t = useT();
  return (
    <Stack gap={3}>
      {pinned && (
        <Group gap={4} c="ember">
          <IconPinned size={12} />
          <Text size="10px" tt="uppercase" fw={700}>
            {t({
              it: "Fissato — clicca la card per sganciare",
              en: "Pinned — click the card to unpin",
            })}
          </Text>
        </Group>
      )}
      <Text size="sm" fw={600} style={{ color: rarityColor(item.rarity) }}>
        {item.name ?? item.base_type}
      </Text>
      <Group gap={8} wrap="wrap">
        {item.name && (
          <Text size="xs" c="dimmed">
            {item.base_type}
          </Text>
        )}
        {item.item_level != null && (
          <Text size="xs" c="dimmed">
            · {t({ it: "Livello oggetto", en: "Item level" })} {item.item_level}
          </Text>
        )}
        {item.level_req != null && (
          <Text size="xs" c="dimmed">
            · {t({ it: "Req. livello", en: "Level req" })} {item.level_req}
          </Text>
        )}
      </Group>
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
      {item.rarity === "unique" && (
        <Group gap={6} mt={2}>
          <Text size="xs" c="dimmed">
            {t({ it: "Prezzo:", en: "Price:" })}
          </Text>
          <PriceBadge name={item.name ?? item.base_type} />
        </Group>
      )}
    </Stack>
  );
}

interface Props {
  label: string;
  item: PobItem | undefined;
  style?: React.CSSProperties;
  onTrade: (item: PobItem) => void;
  /** Whether this card's details panel is pinned open. */
  pinned: boolean;
  /** Toggle the pin (the parent enforces one-pinned-at-a-time). */
  onTogglePin: () => void;
}

export function GearCard({
  label,
  item,
  style,
  onTrade,
  pinned,
  onTogglePin,
}: Props) {
  const t = useT();
  const [hovered, setHovered] = useState(false);

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
    <Popover
      opened={hovered || pinned}
      position="top"
      withArrow
      shadow="md"
      width={300}
      transitionProps={{ duration: 120 }}
      onChange={(o) => {
        if (!o) {
          setHovered(false);
          if (pinned) onTogglePin();
        }
      }}
    >
      <Popover.Target>
        <Box
          className="vs-rarity"
          data-rarity={item.rarity}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          onClick={onTogglePin}
          style={{
            borderLeft: `3px solid ${rarityColor(item.rarity)}`,
            padding: "6px 10px",
            background: "var(--vs-surface-2)",
            borderRadius: 4,
            cursor: "pointer",
            minWidth: 0,
            position: "relative",
            outline: pinned ? "1px solid var(--vs-ember-border)" : undefined,
            ...style,
          }}
        >
          <Group justify="space-between" gap={4} wrap="nowrap">
            <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
              {label}
            </Text>
            <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
              {pinned && <IconPinned size={11} color="var(--vs-ember)" />}
              {item.corrupted && (
                <Badge color="red" size="xs" variant="filled" px={5}>
                  C
                </Badge>
              )}
              <IconExternalLink
                size={12}
                role="button"
                aria-label={t({ it: "Cerca su Trade", en: "Search on Trade" })}
                style={{ cursor: "pointer", color: "var(--vs-ember)" }}
                onClick={(e) => {
                  e.stopPropagation();
                  onTrade(item);
                }}
              />
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
          {item.rarity === "unique" && (
            <Box
              style={{
                position: "absolute",
                bottom: 3,
                right: 7,
                pointerEvents: "none",
              }}
            >
              <PriceBadge name={item.name ?? item.base_type} />
            </Box>
          )}
        </Box>
      </Popover.Target>
      {/* Not pinned → the panel is a passive hover tooltip (no pointer
          events). Pinned → interactive. */}
      <Popover.Dropdown style={{ pointerEvents: pinned ? "auto" : "none" }}>
        <ItemDetails item={item} pinned={pinned} />
      </Popover.Dropdown>
    </Popover>
  );
}
