/**
 * PlannerPage — POST /fob/plan
 *
 * Pastes a PoB code or pobb.in / pastebin URL, picks a target goal,
 * and renders the resulting staged upgrade plan with poe.ninja-priced
 * core items.
 */

import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Code,
  Divider,
  Group,
  Progress,
  SegmentedControl,
  Stack,
  Switch,
  Text,
  Textarea,
  ThemeIcon,
  Title,
  Tooltip,
} from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import { IconClock, IconCoinFilled, IconStack3 } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { planBuildReverseStream, planBuildStream } from "../api/fob";
import type {
  Build,
  BuildPlan,
  PriceRange,
  PricingProgress,
  TargetGoal,
} from "../api/types";
import { StageCard } from "../components/StageCard";
import { useT } from "../i18n";

const TARGET_KEYS: { value: TargetGoal; it: string; en: string }[] = [
  { value: "mapping_only", it: "Solo Mapping", en: "Mapping only" },
  { value: "mapping_and_boss", it: "Mapping + Boss", en: "Mapping + Boss" },
  { value: "uber_capable", it: "Uber capable", en: "Uber capable" },
];

function formatPrice(p: PriceRange): string {
  const fmt = (n: number) =>
    n >= 100 ? n.toFixed(0) : n >= 1 ? n.toFixed(1) : n.toFixed(2);
  const cur = p.min.currency === "divine" ? "div" : "c";
  if (p.min.amount === p.max.amount) return `${fmt(p.min.amount)} ${cur}`;
  return `${fmt(p.min.amount)}–${fmt(p.max.amount)} ${cur}`;
}

function PlanSummary({ plan }: { plan: BuildPlan }) {
  const t = useT();
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
              {t({ it: "Costo totale stimato", en: "Total estimated cost" })}
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
              {t({ it: "Item core", en: "Core items" })}
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
  const t = useT();
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
              {progress.status ||
                t({ it: "Pricing in corso...", en: "Pricing in progress..." })}
            </Text>
          </Group>
          <Group gap={12} wrap="nowrap">
            <Text size="xs" c="dimmed" ff="monospace">
              {progress.item_index}/{progress.total_items}
            </Text>
            <Badge variant="light" color={color}>
              {isDone
                ? t({ it: "completato", en: "done" })
                : `~${formatSeconds(displayEta)}`}
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
            {t({ it: "trascorso", en: "elapsed" })}:{" "}
            {formatSeconds(progress.elapsed_seconds)}
          </Text>
          <Text size="xs" c="dimmed">
            {pct.toFixed(0)}%
          </Text>
        </Group>
      </Stack>
    </Card>
  );
}

const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"];

interface TimelineProps {
  stages: BuildPlan["stages"];
  templateName: string | null;
  characterClass: string | null;
  ascendancy: string | null;
  userPobCode: string | null;
}

/**
 * Desktop Planner layout — a horizontal Roman-numeral timeline.
 * Clicking a stage dot expands its StageCard inline below the
 * timeline; only one stage is open at a time. The dots fan in with a
 * staggered reveal as the plan first renders ("oracle computing").
 */
function StageTimeline({
  stages,
  templateName,
  characterClass,
  ascendancy,
  userPobCode,
}: TimelineProps) {
  const [expanded, setExpanded] = useState<number>(0);
  const safeIndex = Math.min(expanded, stages.length - 1);
  return (
    <Stack gap="sm">
      <div className="planner-timeline">
        {stages.map((s, i) => (
          <button
            key={s.label}
            type="button"
            className="planner-stage"
            data-expanded={i === safeIndex}
            style={{ "--dot-index": i } as React.CSSProperties}
            onClick={() => setExpanded(i)}
          >
            <span className="planner-dot" />
            <span className="planner-roman">{ROMAN[i] ?? String(i + 1)}</span>
            <span className="planner-stage-label">{s.label}</span>
          </button>
        ))}
      </div>
      {/* Keyed so the reveal animation replays each time the user
          opens a different stage. */}
      <div key={safeIndex} className="vs-card-reveal">
        <StageCard
          stage={stages[safeIndex]}
          index={0}
          templateName={templateName}
          characterClass={characterClass}
          ascendancy={ascendancy}
          userPobCode={userPobCode}
        />
      </div>
    </Stack>
  );
}

interface Props {
  initialInput?: string;
}

interface PlanResult {
  build: Build;
  plan: BuildPlan;
  /** Identifier of the template the planner picked (Step 14 T5+). */
  templateName: string | null;
}

export function PlannerPage({ initialInput }: Props) {
  const [input, setInput] = useState(initialInput ?? "");
  const [target, setTarget] = useState<TargetGoal>("mapping_and_boss");
  const [reverseMode, setReverseMode] = useState(false);
  const [progress, setProgress] = useState<PricingProgress | null>(null);
  const [result, setResult] = useState<PlanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  // The input form collapses to a compact row once a plan starts
  // streaming; "modifica" expands it again.
  const [editing, setEditing] = useState(true);
  const abortRef = useRef<AbortController | null>(null);
  const autoFired = useRef(false);

  // Desktop gets the horizontal timeline; mobile keeps stacked cards.
  // useMediaQuery returns undefined on the first render — default to
  // desktop so there's no layout flash.
  const isDesktop = useMediaQuery("(min-width: 1024px)") !== false;

  const t = useT();
  const targetOptions = TARGET_KEYS.map((o) => ({
    value: o.value,
    label: t({ it: o.it, en: o.en }),
  }));

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
    setEditing(false);

    try {
      // Both template and reverse modes stream via SSE so the UI gets
      // per-item progress + ETA. Reverse mode's 'done' event carries
      // the merged plan with [target] ladder rationales.
      const stream = reverseMode
        ? planBuildReverseStream(input, target, ctrl.signal)
        : planBuildStream(input, target, ctrl.signal);
      let lastEvent: PricingProgress | null = null;
      for await (const event of stream) {
        if (ctrl.signal.aborted) return;
        lastEvent = event;
        setProgress(event);
      }
      // The 'done' event carries the BuildPlan + (Step 14 T5+) the
      // analyzed Build summary and the picked template name. Older
      // server versions return only `final_plan`, so we still
      // synthesize a stub Build when those fields are missing.
      if (lastEvent?.kind === "done" && lastEvent.final_plan) {
        const stubBuild: Build = {
          source_id: lastEvent.final_plan.build_source_id,
          character_class: "",
          ascendancy: null,
          main_skill: null,
          level: 1,
        };
        setResult({
          build: lastEvent.build ?? stubBuild,
          plan: lastEvent.final_plan,
          templateName: lastEvent.template_name ?? null,
        });
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        setError((err as Error).message);
      }
    } finally {
      setRunning(false);
    }
  }, [input, target, reverseMode, running]);

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
      <Title order={3}>{t({ it: "Planner build", en: "Build Planner" })}</Title>

      {editing ? (
        <>
          <Text c="dimmed" size="sm">
            {t({
              it: "Incolla un codice di esportazione PoB o un link pobb.in / pastebin: il planner analizza la build, prezza ogni unique su poe.ninja e ti restituisce un piano di upgrade in 6 stage.",
              en: "Paste a PoB export code or a pobb.in / pastebin link: the planner analyses the build, prices every unique on poe.ninja and returns a 6-stage upgrade plan.",
            })}
          </Text>

          <Textarea
            placeholder="https://pobb.in/xxxx  oppure  eNqtVct..."
            value={input}
            onChange={(e) => setInput(e.currentTarget.value)}
            minRows={3}
            autosize
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) start();
            }}
          />

          <Group justify="space-between" wrap="wrap">
            <SegmentedControl
              data={targetOptions}
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
                {t({ it: "Genera piano", en: "Generate plan" })}
              </Button>
              <Text size="xs" c="dimmed">
                Ctrl+Enter
              </Text>
            </Group>
          </Group>

          <Group gap={8}>
            <Tooltip
              multiline
              w={320}
              label={t({
                it: "Quando attivo, ogni KeyItem endgame della tua build genera una upgrade ladder personalizzata (Mageblood → Bottled Faith → flask rare; Awakened gem 5 → 1 → support regular). Le rationale dei rung vengono mostrate nei rispettivi stage.",
                en: "When enabled, each endgame KeyItem of your build generates a personalised upgrade ladder (Mageblood → Bottled Faith → rare flask; Awakened gem 5 → 1 → regular support). Each rung's rationale is shown in the matching stage.",
              })}
              withArrow
            >
              <Switch
                checked={reverseMode}
                onChange={(e) => setReverseMode(e.currentTarget.checked)}
                label={t({
                  it: "Modalità reverse-progression (sperimentale)",
                  en: "Reverse-progression mode (experimental)",
                })}
                size="sm"
              />
            </Tooltip>
          </Group>
        </>
      ) : (
        <Group gap={8} wrap="nowrap">
          <Code style={{ overflow: "hidden", textOverflow: "ellipsis", flex: 1 }}>
            {input.trim()}
          </Code>
          <Anchor
            size="xs"
            onClick={() => setEditing(true)}
            style={{ flexShrink: 0 }}
          >
            {t({ it: "modifica", en: "edit" })}
          </Anchor>
        </Group>
      )}

      {error && (
        <Alert color="red" title={t({ it: "Errore", en: "Error" })}>
          {error}
        </Alert>
      )}

      {progress && <PricingProgressBar progress={progress} />}

      {result && (
        <>
          <Divider
            my="xs"
            label={t({ it: "Piano generato", en: "Generated plan" })}
            labelPosition="center"
          />
          <PlanSummary plan={result.plan} />
          <Divider my="xs" label="Stage" labelPosition="center" />
          {isDesktop ? (
            <StageTimeline
              stages={result.plan.stages}
              templateName={result.templateName}
              characterClass={result.build.character_class || null}
              ascendancy={result.build.ascendancy ?? null}
              userPobCode={input.trim() || null}
            />
          ) : (
            <Stack gap="md">
              {result.plan.stages.map((s, i) => (
                <StageCard
                  key={s.label}
                  stage={s}
                  index={i}
                  templateName={result.templateName}
                  characterClass={result.build.character_class || null}
                  ascendancy={result.build.ascendancy ?? null}
                  userPobCode={input.trim() || null}
                />
              ))}
            </Stack>
          )}
        </>
      )}
    </Stack>
  );
}
