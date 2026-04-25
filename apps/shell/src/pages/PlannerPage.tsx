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
  Progress,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { IconClock, IconCoinFilled, IconStack3 } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { planBuildStream } from "../api/fob";
import type {
  Build,
  BuildPlan,
  PriceRange,
  PricingProgress,
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

function formatSeconds(s: number): string {
  if (!Number.isFinite(s) || s <= 0) return "0s";
  if (s < 60) return `${Math.ceil(s)}s`;
  const mins = Math.floor(s / 60);
  const secs = Math.ceil(s - mins * 60);
  return secs === 0 ? `${mins}m` : `${mins}m ${secs}s`;
}

/**
 * Live progress card during a streaming plan request.
 *
 * Receives the latest PricingProgress event from the parent and
 * renders a Mantine Progress bar plus an ETA countdown that
 * decrements between events using a 100ms tick.
 */
function PricingProgressBar({ progress }: { progress: PricingProgress }) {
  const [displayEta, setDisplayEta] = useState(progress.eta_seconds);
  const lastEventAt = useRef(performance.now());

  // On every new event, reset the countdown anchor.
  useEffect(() => {
    lastEventAt.current = performance.now();
    setDisplayEta(progress.eta_seconds);
  }, [progress.eta_seconds, progress.kind, progress.item_index]);

  // Tick the countdown 10×/s so it feels alive.
  useEffect(() => {
    if (progress.kind === "done") return;
    const id = setInterval(() => {
      const since = (performance.now() - lastEventAt.current) / 1000;
      setDisplayEta(Math.max(0, progress.eta_seconds - since));
    }, 100);
    return () => clearInterval(id);
  }, [progress.eta_seconds, progress.kind]);

  const pct =
    progress.total_items > 0
      ? Math.min(100, (progress.item_index / progress.total_items) * 100)
      : 0;

  const isDone = progress.kind === "done";
  const color = isDone ? "teal" : "indigo";

  return (
    <Card withBorder radius="md" p="md">
      <Stack gap={8}>
        <Group justify="space-between" wrap="nowrap">
          <Group gap={8} wrap="nowrap">
            <ThemeIcon variant="light" color={color} radius="xl" size="md">
              <IconClock size={14} />
            </ThemeIcon>
            <Text size="sm" fw={500} truncate>
              {progress.status || "Pricing in corso..."}
            </Text>
          </Group>
          <Group gap={12} wrap="nowrap">
            <Text size="xs" c="dimmed" ff="monospace">
              {progress.item_index}/{progress.total_items}
            </Text>
            <Badge variant="light" color={color}>
              {isDone ? "completato" : `~${formatSeconds(displayEta)}`}
            </Badge>
          </Group>
        </Group>
        <Progress
          value={pct}
          color={color}
          size="md"
          radius="xl"
          animated={!isDone}
          striped={!isDone}
        />
        <Group justify="space-between">
          <Text size="xs" c="dimmed">
            elapsed: {formatSeconds(progress.elapsed_seconds)}
          </Text>
          <Text size="xs" c="dimmed">
            {pct.toFixed(0)}%
          </Text>
        </Group>
      </Stack>
    </Card>
  );
}

interface Props {
  initialInput?: string;
}

interface PlanResult {
  build: Build;
  plan: BuildPlan;
}

export function PlannerPage({ initialInput }: Props) {
  const [input, setInput] = useState(initialInput ?? "");
  const [target, setTarget] = useState<TargetGoal>("mapping_and_boss");
  const [progress, setProgress] = useState<PricingProgress | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const autoFired = useRef(false);

  const start = useCallback(async () => {
    if (!input.trim() || running) return;

    // Cancel any in-flight request.
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setError(null);
    setProgress(null);
    setResult(null);
    setRunning(true);

    try {
      let lastEvent: PricingProgress | null = null;
      for await (const event of planBuildStream(input, target, ctrl.signal)) {
        if (ctrl.signal.aborted) return;
        lastEvent = event;
        setProgress(event);
      }
      // The 'done' event carries the BuildPlan; we can't know the Build
      // separately from the stream, so we render the plan with a
      // stand-in synthesized from final_plan's source id.
      if (lastEvent?.kind === "done" && lastEvent.final_plan) {
        // Fetch build separately via /analyze-pob? For now we synthesize
        // a minimal Build header from the plan's source id.
        setResult({
          build: {
            source_id: lastEvent.final_plan.build_source_id,
            character_class: "",
            ascendancy: null,
            main_skill: null,
            level: 1,
          },
          plan: lastEvent.final_plan,
        });
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setRunning(false);
    }
  }, [input, target, running]);

  // Auto-trigger when the page is opened with a pre-filled PoB code
  // (coming from Build Finder "Pianifica →" button).
  useEffect(() => {
    if (initialInput && !autoFired.current) {
      autoFired.current = true;
      setInput(initialInput);
      setTimeout(() => start(), 50);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialInput]);

  // Cancel the in-flight stream when the page unmounts.
  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

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
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) start();
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
            onClick={start}
            loading={running}
            disabled={!input.trim() || running}
          >
            Genera piano
          </Button>
          <Text size="xs" c="dimmed">
            Ctrl+Enter
          </Text>
        </Group>
      </Group>

      {error && (
        <Alert color="red" title="Errore">
          {error}
        </Alert>
      )}

      {progress && <PricingProgressBar progress={progress} />}

      {result && (
        <>
          <Divider my="xs" label="Piano generato" labelPosition="center" />
          <PlanSummary plan={result.plan} />
          <Divider my="xs" label="Stage" labelPosition="center" />
          <Stack gap="md">
            {result.plan.stages.map((s, i) => (
              <StageCard key={s.label} stage={s} index={i} />
            ))}
          </Stack>
        </>
      )}
    </Stack>
  );
}
