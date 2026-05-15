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

function ContentFocusPills({ items }: { items: ContentFocusWeight[] | null | undefined }) {
  const safe = items ?? [];
  if (!safe.length) return null;
  return (
    <Group gap={4}>
      {safe.map((cfw) => (
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
  // Defensive: backend Pydantic models default these tuples to empty,
  // but in the wild (older deploys, partial payloads, fetch interceptors,
  // ad blockers rewriting JSON) we've seen them arrive `undefined`,
  // which crashes `.map`. See QA 2026-05-15.
  const hardConstraints = intent.hard_constraints ?? [];
  const contentFocus = intent.content_focus ?? [];
  const confidencePct = Math.round((intent.confidence ?? 0) * 100);
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
          {intent.main_skill_hint && (
            <Badge color="grape" variant="filled" tt="uppercase" size="sm">
              skill: {intent.main_skill_hint}
            </Badge>
          )}
          {pill(intent.damage_profile, "orange")}
          {pill(intent.playstyle, "violet")}
          {pill(intent.defense_profile, "blue")}
          {pill(intent.complexity_cap, "gray")}
          {intent.budget?.tier && pill(intent.budget.tier, "teal")}
          {hardConstraints.map((hc) => (
            <Badge key={hc} color="red" variant="outline" size="sm">
              {hc.replace(/_/g, " ")}
            </Badge>
          ))}
          {intent.class_filter && (
            <Badge color="indigo" variant="filled" tt="uppercase" size="sm">
              class: {intent.class_filter}
            </Badge>
          )}
          {intent.sort_by && intent.sort_by !== "score" && (
            <Badge color="pink" variant="light" size="sm">
              sort: {intent.sort_by}
            </Badge>
          )}
          {intent.min_life != null && (
            <Badge color="lime" variant="dot" size="sm">
              life ≥ {intent.min_life.toLocaleString()}
            </Badge>
          )}
          {intent.min_es != null && (
            <Badge color="lime" variant="dot" size="sm">
              ES ≥ {intent.min_es.toLocaleString()}
            </Badge>
          )}
          {intent.min_ehp != null && (
            <Badge color="lime" variant="dot" size="sm">
              EHP ≥ {intent.min_ehp.toLocaleString()}
            </Badge>
          )}
          {intent.min_dps != null && (
            <Badge color="lime" variant="dot" size="sm">
              DPS ≥ {intent.min_dps.toLocaleString()}
            </Badge>
          )}
          {(intent.min_level != null || intent.max_level != null) && (
            <Badge color="lime" variant="dot" size="sm">
              level {intent.min_level ?? "*"}–{intent.max_level ?? "100"}
            </Badge>
          )}
        </Group>

        <ContentFocusPills items={contentFocus} />

        <Text size="xs" c="dimmed" fs="italic">
          via {(intent.parser_origin ?? "rule_based").replace(/_/g, " ")}
        </Text>
      </Stack>
    </Card>
  );
}
