import {
  Badge,
  Card,
  Group,
  Progress,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import type { BuildIntent, ContentFocusWeight } from "../api/types";

interface Props {
  intent: BuildIntent;
}

function pill(value: string | null, color: string) {
  if (!value) return null;
  return (
    <Badge color={color} variant="light" tt="uppercase">
      {value.replace(/_/g, " ")}
    </Badge>
  );
}

function ContentFocusPills({ items }: { items: ContentFocusWeight[] }) {
  if (!items.length) return null;
  return (
    <Group gap={4}>
      {items.map((cfw) => (
        <Badge
          key={cfw.focus}
          color="cyan"
          variant="dot"
          size="sm"
        >
          {cfw.focus.replace(/_/g, " ")} {Math.round(cfw.weight * 100)}%
        </Badge>
      ))}
    </Group>
  );
}

export function IntentCard({ intent }: Props) {
  const confidencePct = Math.round(intent.confidence * 100);
  const confidenceColor =
    confidencePct >= 70 ? "green" : confidencePct >= 40 ? "yellow" : "red";

  return (
    <Card withBorder radius="md" p="md">
      <Stack gap="xs">
        <Group justify="space-between" align="center">
          <Title order={5} c="dimmed">
            Intent parsed
          </Title>
          <Group gap={6}>
            <Text size="xs" c="dimmed">
              confidence
            </Text>
            <Progress
              value={confidencePct}
              color={confidenceColor}
              size="sm"
              w={80}
            />
            <Text size="xs" fw={600} c={confidenceColor}>
              {confidencePct}%
            </Text>
          </Group>
        </Group>

        <Group gap={6} wrap="wrap">
          {pill(intent.damage_profile, "orange")}
          {pill(intent.playstyle, "violet")}
          {pill(intent.defense_profile, "blue")}
          {pill(intent.complexity_cap, "gray")}
          {intent.budget?.tier && pill(intent.budget.tier, "teal")}
          {intent.hard_constraints.map((hc) => (
            <Badge key={hc} color="red" variant="outline" size="sm">
              {hc.replace(/_/g, " ")}
            </Badge>
          ))}
        </Group>

        <ContentFocusPills items={intent.content_focus} />

        <Text size="xs" c="dimmed" fs="italic">
          via {intent.parser_origin.replace(/_/g, " ")}
        </Text>
      </Stack>
    </Card>
  );
}
