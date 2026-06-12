/**
 * PriceBadge — a small poe.ninja price hint for a gear item.
 *
 * Takes the item `name` and fetches the price via `usePriceHint`
 * (so the component is safe to render conditionally — only mount it
 * for uniques, where poe.ninja name-pricing actually resolves).
 *
 * Renders a compact Geist-Mono ember label (`≈ 5c` / `≈ 1.2 div`),
 * a shimmer skeleton pill while loading, or nothing when the item has
 * no price. Positioning is the caller's job — wrap it.
 */

import { Box, Text } from "@mantine/core";
import { usePriceHint } from "../hooks/usePriceHint";

interface Props {
  /** Item name to price. Null disables the fetch (renders nothing). */
  name: string | null;
}

export function PriceBadge({ name }: Props) {
  const { chaos, divine, loading } = usePriceHint(name);

  if (loading) {
    return (
      <Box
        className="vs-skeleton"
        style={{ width: 34, height: 9, borderRadius: 4 }}
      />
    );
  }
  if (chaos == null) return null;

  // Show divine when the item is worth ≥ 100c and poe.ninja gave a
  // divine value; otherwise the chaos value.
  const label =
    divine != null && chaos >= 100
      ? `≈ ${divine < 10 ? divine.toFixed(1) : Math.round(divine)} div`
      : `≈ ${Math.round(chaos)}c`;

  return (
    <Text
      className="mono"
      size="xs"
      fw={600}
      style={{ color: "var(--vs-ember)", whiteSpace: "nowrap" }}
    >
      {label}
    </Text>
  );
}
