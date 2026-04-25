/**
 * AnalyzePage — POST /fob/analyze-pob
 *
 * Accepts a raw PoB export code or a pobb.in / pastebin URL and shows
 * the parsed build summary.
 */

import {
  Alert,
  Badge,
  Button,
  Card,
  Group,
  Stack,
  Text,
  Textarea,
  Title,
} from "@mantine/core";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { analyzePob } from "../api/fob";
import type { AnalyzePobResponse } from "../api/types";

function BuildSummary({ data }: { data: AnalyzePobResponse }) {
  const { build } = data;
  return (
    <Card withBorder radius="md" p="md">
      <Stack gap="xs">
        <Title order={5}>Build analizzata</Title>
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
        </Group>
        <Text size="xs" c="dimmed" ff="monospace">
          {build.source_id}
        </Text>
      </Stack>
    </Card>
  );
}

export function AnalyzePage() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<AnalyzePobResponse | null>(null);

  const mut = useMutation({
    mutationFn: () => analyzePob(input),
    onSuccess: setResult,
  });

  return (
    <Stack gap="md">
      <Title order={3}>Analizza PoB</Title>
      <Text c="dimmed" size="sm">
        Incolla un codice di esportazione PoB oppure un link pobb.in / pastebin.
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

      <Group>
        <Button
          onClick={() => mut.mutate()}
          loading={mut.isPending}
          disabled={!input.trim()}
        >
          Analizza
        </Button>
        <Text size="xs" c="dimmed">
          Ctrl+Enter
        </Text>
      </Group>

      {mut.isError && (
        <Alert color="red" title="Errore">
          {mut.error.message}
        </Alert>
      )}

      {result && <BuildSummary data={result} />}
    </Stack>
  );
}
