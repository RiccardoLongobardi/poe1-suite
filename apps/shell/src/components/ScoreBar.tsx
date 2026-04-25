import { Group, Progress, Stack, Text, Tooltip } from "@mantine/core";
import type { ScoreBreakdown } from "../api/types";

interface DimRowProps {
  label: string;
  value: number;
  weight: number;
  tooltip: string;
}

function DimRow({ label, value, weight, tooltip }: DimRowProps) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 70 ? "green" : pct >= 40 ? "yellow" : pct >= 20 ? "orange" : "red";
  return (
    <Tooltip label={tooltip} position="right" withArrow>
      <Group gap={6} wrap="nowrap">
        <Text size="xs" w={64} ta="right" c="dimmed" style={{ flexShrink: 0 }}>
          {label}
        </Text>
        <Progress value={pct} color={color} size={6} flex={1} />
        <Text size="xs" w={28} c={color} fw={600} style={{ flexShrink: 0 }}>
          {pct}%
        </Text>
        <Text size="xs" c="dimmed" w={28} style={{ flexShrink: 0 }}>
          ×{weight}
        </Text>
      </Group>
    </Tooltip>
  );
}

interface Props {
  score: ScoreBreakdown;
}

const DIMS: {
  key: keyof Omit<ScoreBreakdown, "total">;
  label: string;
  weight: string;
  tooltip: string;
}[] = [
  {
    key: "damage",
    label: "Damage",
    weight: ".30",
    tooltip: "Main skill vs. requested damage profile",
  },
  {
    key: "playstyle",
    label: "Playstyle",
    weight: ".25",
    tooltip: "Skill mechanic vs. requested playstyle",
  },
  {
    key: "budget",
    label: "Budget",
    weight: ".20",
    tooltip: "DPS percentile rank as investment proxy",
  },
  {
    key: "content",
    label: "Content",
    weight: ".15",
    tooltip: "Content-focus fit (limited signal at ref level)",
  },
  {
    key: "defense",
    label: "Defense",
    weight: ".05",
    tooltip: "Life/ES ratio vs. requested defense profile",
  },
  {
    key: "complexity",
    label: "Complexity",
    weight: ".05",
    tooltip: "Skill complexity vs. complexity cap",
  },
];

export function ScoreBar({ score }: Props) {
  return (
    <Stack gap={4} w="100%">
      {DIMS.map((d) => (
        <DimRow
          key={d.key}
          label={d.label}
          value={score[d.key]}
          weight={parseFloat(d.weight)}
          tooltip={d.tooltip}
        />
      ))}
    </Stack>
  );
}
