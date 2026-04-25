import {
  Badge,
  Button,
  Card,
  Collapse,
  Group,
  RingProgress,
  Stack,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconListCheck } from "@tabler/icons-react";
import { useState } from "react";
import { getDetail } from "../api/builds";
import type { RankedBuild } from "../api/types";
import { ScoreBar } from "./ScoreBar";

interface Props {
  build: RankedBuild;
  onSendToPlanner?: (pobCode: string) => void;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
  return String(n);
}

function scoreColor(total: number): string {
  if (total >= 0.75) return "green";
  if (total >= 0.55) return "yellow";
  if (total >= 0.35) return "orange";
  return "red";
}

export function BuildCard({ build, onSendToPlanner }: Props) {
  const [opened, { toggle }] = useDisclosure(false);
  const [loading, setLoading] = useState(false);
  const { ref, score } = build;

  async function handlePlan(e: React.MouseEvent) {
    e.stopPropagation(); // don't toggle collapse
    if (!onSendToPlanner) return;
    setLoading(true);
    try {
      const code = await getDetail(ref.account, ref.character);
      onSendToPlanner(code);
    } catch (err) {
      alert(`Errore nel caricare il PoB: ${(err as Error).message}`);
    } finally {
      setLoading(false);
    }
  }
  const pct = Math.round(score.total * 100);
  const color = scoreColor(score.total);
  const defLabel =
    ref.energy_shield > ref.life * 2
      ? "ES"
      : ref.energy_shield > 0
        ? "Hybrid"
        : "Life";

  return (
    <Card withBorder radius="md" p="sm">
      <UnstyledButton onClick={toggle} w="100%">
        <Group justify="space-between" wrap="nowrap">
          {/* Rank + score ring */}
          <Group gap={8} wrap="nowrap">
            <Text fw={700} c="dimmed" w={24} ta="right" style={{ flexShrink: 0 }}>
              #{build.rank}
            </Text>
            <RingProgress
              size={48}
              thickness={4}
              roundCaps
              sections={[{ value: pct, color }]}
              label={
                <Text ta="center" size="9px" fw={700} c={color} lh={1}>
                  {pct}%
                </Text>
              }
            />
          </Group>

          {/* Identity */}
          <Stack gap={2} flex={1} miw={0}>
            <Group gap={4} wrap="nowrap">
              <Text fw={600} size="sm" truncate>
                {ref["class"]}
              </Text>
              {ref.main_skill && (
                <Badge color="grape" variant="light" size="xs">
                  {ref.main_skill}
                </Badge>
              )}
            </Group>
            <Text size="xs" c="dimmed" truncate>
              {ref.character} · lv {ref.level}
            </Text>
          </Stack>

          {/* Stats */}
          <Group gap={12} wrap="nowrap" style={{ flexShrink: 0 }}>
            <Stack gap={0} align="center">
              <Text size="xs" c="dimmed">
                {defLabel}
              </Text>
              <Text size="xs" fw={600}>
                {defLabel === "ES"
                  ? fmt(ref.energy_shield)
                  : defLabel === "Hybrid"
                    ? `${fmt(ref.life)}/${fmt(ref.energy_shield)}`
                    : fmt(ref.life)}
              </Text>
            </Stack>
            <Stack gap={0} align="center">
              <Text size="xs" c="dimmed">
                DPS
              </Text>
              <Text size="xs" fw={600}>
                {fmt(ref.dps)}
              </Text>
            </Stack>
            {onSendToPlanner && (
              <Button
                size="xs"
                variant="light"
                color="teal"
                leftSection={<IconListCheck size={13} />}
                loading={loading}
                onClick={handlePlan}
              >
                Pianifica
              </Button>
            )}
          </Group>
        </Group>
      </UnstyledButton>

      {/* Expanded score breakdown */}
      <Collapse in={opened}>
        <Card.Section withBorder mt="sm" pt="sm" px="sm" pb="sm">
          <ScoreBar score={score} />
        </Card.Section>
      </Collapse>
    </Card>
  );
}
