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
  IconCheck,
  IconCopy,
  IconListCheck,
  IconSparkles,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { getDetail, getDetailFull, type GemRef, type SkillGroup } from "../api/builds";
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
            color={isSupport ? "gray" : "astral"}
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

export function BuildCard({ build, onSendToPlanner }: Props) {
  const [opened, { toggle }] = useDisclosure(false);
  const [planLoading, setPlanLoading] = useState(false);
  const [linkCopied, setLinkCopied] = useState(false);
  const [detailGroups, setDetailGroups] = useState<SkillGroup[] | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const { ref, score } = build;

  // Lazy-load the skill groups on first expand.
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
  }, [opened, ref.account, ref.character, detailGroups, detailLoading]);

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
          <Group gap={10} wrap="nowrap" style={{ flexShrink: 0 }}>
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
                EHP
              </Text>
              <Text size="xs" fw={600}>
                {fmt(ref.ehp)}
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
                loading={planLoading}
                onClick={handlePlan}
              >
                Pianifica
              </Button>
            )}
            <Tooltip
              label={linkCopied ? "Link copiato!" : "Copia link poe.ninja"}
              withArrow
              position="top"
            >
              <Button
                size="xs"
                variant="subtle"
                color={linkCopied ? "teal" : "astral"}
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
      </UnstyledButton>

      {/* Expanded content: score breakdown + main gems */}
      <Collapse in={opened}>
        <Card.Section withBorder mt="sm" pt="sm" px="sm" pb="sm">
          <Stack gap="md">
            {/* Main gems — lazy-fetched */}
            <Stack gap={6}>
              <Group gap={6}>
                <IconSparkles size={14} color="var(--astral-glow)" />
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
