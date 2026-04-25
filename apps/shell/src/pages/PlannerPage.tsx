/**
 * PlannerPage — POST /fob/plan
 *
 * Pastes a PoB code or pobb.in / pastebin URL, picks a target goal,
 * and renders the resulting staged upgrade plan with poe.ninja-priced
 * core items.
 */

import {
  Alert,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { IconCoinFilled, IconStack3 } from "@tabler/icons-react";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { planBuild } from "../api/fob";
import type {
  Build,
  BuildPlan,
  PriceRange,
  TargetGoal,
} from "../api/types";
import { StageCard } from "../components/StageCard";

const TARGET_OPTIONS: { value: TargetGoal; label: string }[] = [
  { value: "mapping_only", label: "Solo Mapping" },
  { value: "mapping_and_boss", label: "Mapping + Boss" },
  { value: "uber_capable", label: "Uber capable" },
];

function formatPrice(p: PriceRange): string {
  const fmt = (n: number) =>
    n >= 100 ? n.toFixed(0) : n >= 1 ? n.toFixed(1) : n.toFixed(2);
  const cur = p.currency === "divine" ? "div" : "c";
  if (p.min.amount === p.max.amount) return `${fmt(p.min.amount)} ${cur}`;
  return `${fmt(p.min.amount)}–${fmt(p.max.amount)} ${cur}`;
}

function BuildHeader({ build }: { build: Build }) {
  return (
    <Card withBorder radius="md" p="sm">
      <Group gap={6} wrap="wrap">
        <Badge color="blue">{build.character_class}</Badge>
        {build.ascendancy && (
          <Badge color="indigo" variant="light">
            {build.ascendancy}
          </Badge>
        )}
        {build.main_skill && (
          <Badge color="grape" variant="light">
            {build.main_skill}
          </Badge>
        )}
        <Badge color="gray" variant="outline">
          lv {build.level}
        </Badge>
        <Text size="xs" c="dimmed" ff="monospace" ml="auto">
          {build.source_id}
        </Text>
      </Group>
    </Card>
  );
}

function PlanSummary({ plan }: { plan: BuildPlan }) {
  const totalItems = plan.stages.reduce(
    (acc, s) => acc + s.core_items.length,
    0,
  );
  return (
    <Card withBorder radius="md" p="md" bg="dark.7">
      <Group justify="space-between" wrap="wrap">
        <Group gap={10}>
          <ThemeIcon variant="light" color="yellow" size="lg" radius="md">
            <IconCoinFilled size={20} />
          </ThemeIcon>
          <Stack gap={0}>
            <Text size="xs" c="dimmed">
              Costo totale stimato
            </Text>
            <Text size="xl" fw={700}>
              {formatPrice(plan.total_estimated_cost)}
            </Text>
          </Stack>
        </Group>
        <Group gap={10}>
          <ThemeIcon variant="light" color="cyan" size="lg" radius="md">
            <IconStack3 size={20} />
          </ThemeIcon>
          <Stack gap={0}>
            <Text size="xs" c="dimmed">
              Item core
            </Text>
            <Text size="xl" fw={700}>
              {totalItems}
            </Text>
          </Stack>
        </Group>
        <Badge size="lg" variant="light" color="grape">
          target: {plan.target_goal.replace("_", " ")}
        </Badge>
      </Group>
    </Card>
  );
}

interface Props {
  initialInput?: string;
}

export function PlannerPage({ initialInput }: Props) {
  const [input, setInput] = useState(initialInput ?? "");
  const [target, setTarget] = useState<TargetGoal>("mapping_and_boss");
  const autoFired = useRef(false);

  const mut = useMutation({
    mutationFn: () => planBuild(input, target),
  });

  // Auto-trigger when the page is opened with a pre-filled PoB code
  // (coming from Build Finder "Pianifica →" button).
  useEffect(() => {
    if (initialInput && !autoFired.current) {
      autoFired.current = true;
      setInput(initialInput);
      // Small delay so the textarea renders with the value first.
      setTimeout(() => mut.mutate(), 50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialInput]);

  return (
    <Stack gap="md">
      <Title order={3}>Planner build</Title>
      <Text c="dimmed" size="sm">
        Incolla un codice di esportazione PoB o un link pobb.in / pastebin: il
        planner analizza la build, prezza ogni unique su poe.ninja e ti
        restituisce un piano di upgrade in 3 stage.
      </Text>

      <Textarea
        placeholder="https://pobb.in/xxxx  oppure  eNqtVct..."
        value={input}
        onChange={(e) => setInput(e.currentTarget.value)}
        minRows={3}
        autosize
        ff="monospace"
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) mut.mutate();
        }}
      />

      <Group justify="space-between" wrap="wrap">
        <SegmentedControl
          data={TARGET_OPTIONS}
          value={target}
          onChange={(v) => setTarget(v as TargetGoal)}
          size="sm"
        />
        <Group>
          <Button
            onClick={() => mut.mutate()}
            loading={mut.isPending}
            disabled={!input.trim()}
          >
            Genera piano
          </Button>
          <Text size="xs" c="dimmed">
            Ctrl+Enter
          </Text>
        </Group>
      </Group>

      {mut.isError && (
        <Alert color="red" title="Errore">
          {mut.error.message}
        </Alert>
      )}

      {mut.data && (
        <>
          <Divider my="xs" label="Build analizzata" labelPosition="center" />
          <BuildHeader build={mut.data.build} />
          <PlanSummary plan={mut.data.plan} />
          <Divider my="xs" label="Stage" labelPosition="center" />
          <Stack gap="md">
            {mut.data.plan.stages.map((s, i) => (
              <StageCard key={s.label} stage={s} index={i} />
            ))}
          </Stack>
        </>
      )}
    </Stack>
  );
}
