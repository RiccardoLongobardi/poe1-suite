/**
 * FinderPage — the main "Build Finder" flow.
 *
 * Step 1: user types a free-text query → POST /fob/extract-intent
 * Step 2: parsed BuildIntent is shown; user presses "Find Builds"
 *         → POST /fob/recommend → ranked build list
 */

import {
  Alert,
  Box,
  Button,
  Divider,
  Group,
  Loader,
  NumberInput,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { extractIntent, recommend } from "../api/fob";
import type { BuildIntent, RecommendResponse } from "../api/types";
import { BuildCard } from "../components/BuildCard";
import { IntentCard } from "../components/IntentCard";

interface Props {
  onSendToPlanner?: (pobCode: string) => void;
}

export function FinderPage({ onSendToPlanner }: Props) {
  const [query, setQuery] = useState("");
  const [topN, setTopN] = useState<number>(10);
  const [intent, setIntent] = useState<BuildIntent | null>(null);
  const [result, setResult] = useState<RecommendResponse | null>(null);

  const extractMut = useMutation({
    mutationFn: () => extractIntent(query),
    onSuccess: (data) => {
      setIntent(data);
      setResult(null);
    },
  });

  const recommendMut = useMutation({
    mutationFn: () => recommend(intent!, topN),
    onSuccess: setResult,
  });

  const handleExtract = () => {
    if (!query.trim()) return;
    extractMut.mutate();
  };

  const handleRecommend = () => {
    if (!intent) return;
    recommendMut.mutate();
  };

  return (
    <Stack gap="md">
      <Title order={3}>Build Finder</Title>
      <Text c="dimmed" size="sm">
        Descrivi la build che cerchi in italiano o inglese. Es.:&nbsp;
        <em>"cold self-cast per mapping, budget basso"</em>
      </Text>

      {/* Query input */}
      <Textarea
        placeholder="cold mapping ssf, no minion, budget basso..."
        value={query}
        onChange={(e) => setQuery(e.currentTarget.value)}
        minRows={2}
        autosize
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) handleExtract();
        }}
      />

      <Group>
        <Button
          onClick={handleExtract}
          loading={extractMut.isPending}
          disabled={!query.trim()}
        >
          Analizza query
        </Button>
        <Text size="xs" c="dimmed">
          Ctrl+Enter
        </Text>
      </Group>

      {/* Extract error */}
      {extractMut.isError && (
        <Alert color="red" title="Errore extract-intent">
          {extractMut.error.message}
        </Alert>
      )}

      {/* Parsed intent */}
      {intent && (
        <>
          <IntentCard intent={intent} />

          <Group>
            <NumberInput
              label="Risultati"
              value={topN}
              onChange={(v) => setTopN(typeof v === "number" ? v : 10)}
              min={1}
              max={50}
              w={90}
            />
            <Button
              mt="xl"
              onClick={handleRecommend}
              loading={recommendMut.isPending}
              color="teal"
            >
              Trova build →
            </Button>
          </Group>
        </>
      )}

      {/* Recommend error */}
      {recommendMut.isError && (
        <Alert color="red" title="Errore recommend">
          {recommendMut.error.message}
        </Alert>
      )}

      {/* Results */}
      {result && (
        <>
          <Divider
            label={
              <Text size="sm" fw={500}>
                Top {result.ranked.length} builds su{" "}
                {result.total_candidates.toLocaleString()} candidati
              </Text>
            }
          />

          {recommendMut.isPending && (
            <Box ta="center" py="xl">
              <Loader />
            </Box>
          )}

          <Stack gap="xs">
            {result.ranked.map((b) => (
              <BuildCard
                key={b.ref.source_id}
                build={b}
                onSendToPlanner={onSendToPlanner}
              />
            ))}
          </Stack>

          {result.ranked.length === 0 && (
            <Text c="dimmed" ta="center" py="xl">
              Nessun candidato supera i filtri hard-constraint.
            </Text>
          )}
        </>
      )}
    </Stack>
  );
}
