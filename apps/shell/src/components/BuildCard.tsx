/**
 * BuildCard — one row in the Build Finder result list.
 *
 * Compact summary in the always-visible header (rank, score, class,
 * main skill, defensive pool, EHP, DPS) plus an expandable section
 * that reveals the score breakdown and lazy-loads the build's main
 * skill group (active gem + supports) from /builds/detail.
 *
 * Two side actions next to the stats:
 *
 * * **Pianifica** — fetches the PoB code and opens the Planner
 *   pre-filled.
 * * **Copia link** — copies the poe.ninja character URL to the
 *   clipboard, so the user can share or open the public profile.
 */

import {
  Badge,
  Box,
  Button,
  Card,
  Collapse,
  Group,
  Loader,
  RingProgress,
  Stack,
  Text,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconBolt,
  IconCheck,
  IconCopy,
  IconExternalLink,
  IconHeart,
  IconListCheck,
  IconShieldHalf,
  IconSparkles,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { getDetail, getDetailFull, type GemRef, type SkillGroup } from "../api/builds";
import type { RankedBuild } from "../api/types";
import { ScoreBar } from "./ScoreBar";

interface Props {
  build: RankedBuild;
  /** Position in the result list — drives the staggered reveal delay. */
  index?: number;
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

/**
 * Build the public poe.ninja profile URL for a character.
 *
 * Format observed on live poe.ninja (post-PoE2 migration):
 * ``https://poe.ninja/builds/<league-slug>/character/<account>/<character>``
 *
 * The league field on RemoteBuildRef is the human-readable name
 * ("Mirage"); poe.ninja's URL slug is the lower-case version.
 */
function poeNinjaUrl(league: string, account: string, character: string): string {
  const slug = league.trim().toLowerCase().replace(/\s+/g, "-");
  return `https://poe.ninja/builds/${slug}/character/${encodeURIComponent(account)}/${encodeURIComponent(character)}`;
}

/**
 * Pick the build's main skill group from a hydrated detail payload.
 *
 * poe.ninja's API doesn't flag which group is "main" directly; the
 * heuristic is: the group whose **first** active (non-support) gem
 * matches the ref's main_skill string. Falls back to the first
 * non-empty group if no match.
 */
function pickMainGroup(
  groups: SkillGroup[],
  hint: string | null,
): SkillGroup | undefined {
  const needle = (hint ?? "").trim().toLowerCase();
  if (needle && groups.length > 0) {
    const match = groups.find((g) =>
      g.allGems.some(
        (gem) => !gem.isBuiltInSupport && gem.name.toLowerCase() === needle,
      ),
    );
    if (match) return match;
  }
  return groups.find((g) => g.allGems.length > 0);
}

/**
 * Render a chip-list of gems for the main skill group. Active gems get
 * a coloured background; supports stay subtle.
 */
function GemChips({ gems }: { gems: GemRef[] }) {
  if (gems.length === 0) {
    return (
      <Text size="xs" c="dimmed">
        Nessun gem visibile.
      </Text>
    );
  }
  return (
    <Group gap={6} wrap="wrap">
      {gems.map((gem, i) => {
        const isSupport = gem.name.toLowerCase().startsWith("support") || i > 0;
        return (
          <Badge
            key={`${gem.name}-${i}`}
            color={isSupport ? "gray" : "ember"}
            variant={isSupport ? "outline" : "filled"}
            size="sm"
          >
            {gem.name} {gem.level}/{gem.quality}
          </Badge>
        );
      })}
    </Group>
  );
}

/**
 * One stat chip — icon + value in Geist Mono, tinted by PoE1 rarity
 * convention (life red, dps ember gold, ehp gem teal).
 */
function StatChip({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <Group
      gap={4}
      wrap="nowrap"
      px={8}
      py={3}
      style={{
        background: "rgba(255,255,255,0.04)",
        border: "1px solid var(--vs-border-stone)",
        borderRadius: 4,
      }}
    >
      <Box style={{ color, display: "flex" }}>{icon}</Box>
      <Text size="10px" c="dimmed" tt="uppercase" fw={600}>
        {label}
      </Text>
      <Text className="mono" size="xs" fw={700} style={{ color }}>
        {value}
      </Text>
    </Group>
  );
}

export function BuildCard({ build, index, onSendToPlanner }: Props) {
  const [opened, { toggle }] = useDisclosure(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [detailGroups, setDetailGroups] = useState<SkillGroup[] | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { ref, score } = build;

  // Lazy-load the skill groups on first expand.
  //
  // Critical: ``detailLoading`` is INTENTIONALLY excluded from the deps
  // array. Including it creates a race where setDetailLoading(true)
  // re-fires the effect, the cleanup sets cancelled=true on the
  // in-flight promise, and the result never lands in state →
  // permanent "loading" loader. The same applies to ``detailGroups``
  // when we set it to []: re-firing the effect would cancel the
  // result before it commits. Stale-closure linting is silenced
  // because we read those values once at effect start via the guard.
  useEffect(() => {
    if (!opened || detailGroups !== null || detailLoading) return;
    let cancelled = false;
    setDetailLoading(true);
    getDetailFull(ref.account, ref.character)
      .then(({ skills }) => {
        if (!cancelled) setDetailGroups(skills);
      })
      .catch(() => {
        if (!cancelled) setDetailGroups([]);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, ref.account, ref.character]);

  async function handlePlan(e: React.MouseEvent) {
    e.stopPropagation(); // don't toggle collapse
    if (!onSendToPlanner) return;
    setPlanLoading(true);
    try {
      const code = await getDetail(ref.account, ref.character);
      onSendToPlanner(code);
    } catch (err) {
      alert(`Errore nel caricare il PoB: ${(err as Error).message}`);
    } finally {
      setPlanLoading(false);
    }
  }

  async function handleCopyLink(e: React.MouseEvent) {
    e.stopPropagation(); // don't toggle collapse
    const url = poeNinjaUrl(ref.league, ref.account, ref.character);
    try {
      await navigator.clipboard.writeText(url);
      setLinkCopied(true);
      // Reset the icon after a short window so the user sees the confirmation
      // but the button stays usable.
      setTimeout(() => setLinkCopied(false), 1500);
    } catch {
      // Fallback for browsers that block clipboard access (Safari old, etc.).
      window.prompt("Copia il link manualmente:", url);
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

  const mainGroup = detailGroups ? pickMainGroup(detailGroups, ref.main_skill) : null;

  const defValue =
    defLabel === "ES"
      ? fmt(ref.energy_shield)
      : defLabel === "Hybrid"
        ? `${fmt(ref.life)}/${fmt(ref.energy_shield)}`
        : fmt(ref.life);

  return (
    <Card
      withBorder
      radius="md"
      p="sm"
      className="vs-card-reveal vs-glass"
      style={{ "--card-index": index ?? 0 } as React.CSSProperties}
    >
      <UnstyledButton onClick={toggle} w="100%">
        <Stack gap={8}>
          {/* Row 1 — score ring + identity + rank */}
          <Group justify="space-between" wrap="nowrap" align="flex-start">
            <Group gap={8} wrap="nowrap" miw={0}>
              <RingProgress
                size={44}
                thickness={4}
                roundCaps
                sections={[{ value: pct, color }]}
                label={
                  <Text ta="center" size="9px" fw={700} c={color} lh={1}>
                    {pct}%
                  </Text>
                }
              />
              <Stack gap={2} miw={0}>
                <Group gap={6} wrap="nowrap" miw={0}>
                  <Badge color="ember" variant="light" size="sm">
                    {ref["class"]}
                  </Badge>
                  {ref.main_skill && (
                    <Text fw={700} size="sm" truncate>
                      {ref.main_skill}
                    </Text>
                  )}
                  <Text
                    className="mono"
                    size="xs"
                    c="dimmed"
                    style={{ flexShrink: 0 }}
                  >
                    — Lv. {ref.level}
                  </Text>
                </Group>
                <Text
                  size="xs"
                  truncate
                  style={{ color: "var(--vs-text-faint)" }}
                >
                  {ref.character}
                </Text>
              </Stack>
            </Group>
            <Text
              fw={700}
              size="sm"
              style={{
                fontFamily: "'Cinzel', serif",
                color: "var(--vs-ember)",
                flexShrink: 0,
              }}
            >
              #{build.rank}
            </Text>
          </Group>

          {/* Row 2 — stat chips + actions */}
          <Group justify="space-between" wrap="wrap" gap={8}>
            <Group gap={6} wrap="wrap">
              <StatChip
                icon={<IconHeart size={13} />}
                label={defLabel}
                value={defValue}
                color="#c84040"
              />
              <StatChip
                icon={<IconBolt size={13} />}
                label="DPS"
                value={fmt(ref.dps)}
                color="var(--vs-ember)"
              />
              <StatChip
                icon={<IconShieldHalf size={13} />}
                label="EHP"
                value={fmt(ref.ehp)}
                color="#4fa8a8"
              />
            </Group>
            <Group gap={6} wrap="nowrap">
              {onSendToPlanner && (
                <Button
                  size="xs"
                  variant="light"
                  color="teal"
                  leftSection={<IconListCheck size={13} />}
                  loading={planLoading}
                  onClick={handlePlan}
                >
                  Pianifica
                </Button>
              )}
              <Tooltip
                label="Apri il profilo poe.ninja in una nuova scheda"
                withArrow
                position="top"
              >
                <Button
                  size="xs"
                  variant="light"
                  color="blue"
                  leftSection={<IconExternalLink size={13} />}
                  component="a"
                  href={poeNinjaUrl(ref.league, ref.account, ref.character)}
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                >
                  Apri PoB
                </Button>
              </Tooltip>
              <Tooltip
                label={linkCopied ? "Link copiato!" : "Copia link poe.ninja"}
                withArrow
                position="top"
              >
                <Button
                  size="xs"
                  variant="light"
                  color={linkCopied ? "teal" : "ember"}
                  leftSection={
                    linkCopied ? <IconCheck size={13} /> : <IconCopy size={13} />
                  }
                  onClick={handleCopyLink}
                  px="xs"
                >
                  {linkCopied ? "Copiato" : "Copia link"}
                </Button>
              </Tooltip>
            </Group>
          </Group>
        </Stack>
      </UnstyledButton>

      {/* Expanded content: score breakdown + main gems */}
      <Collapse in={opened}>
        <Card.Section withBorder mt="sm" pt="sm" px="sm" pb="sm">
          <Stack gap="md">
            {/* Main gems — lazy-fetched */}
            <Stack gap={6}>
              <Group gap={6}>
                <IconSparkles size={14} color="var(--vs-ember)" />
                <Text size="xs" fw={600} c="dimmed" tt="uppercase">
                  Main gems
                </Text>
                {detailLoading && <Loader size={12} />}
              </Group>
              {detailGroups === null && !detailLoading && (
                <Text size="xs" c="dimmed">
                  Espandi la card per caricare i gem...
                </Text>
              )}
              {mainGroup ? (
                <GemChips gems={mainGroup.allGems} />
              ) : (
                detailGroups !== null &&
                !detailLoading && (
                  <Text size="xs" c="dimmed">
                    Skill groups non disponibili per questa build.
                  </Text>
                )
              )}
            </Stack>

            {/* Score breakdown */}
            <ScoreBar score={score} />
          </Stack>
        </Card.Section>
      </Collapse>
    </Card>
  );
}
