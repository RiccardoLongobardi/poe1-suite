/**
 * TheorycrafterPage — `/theorycrafter`, placeholder.
 *
 * Step 38r (architectural reset): the first Build Generator shipped in
 * Step 38 was a poe.ninja *ladder retriever* — it found and reformatted
 * real ladder builds. That is what the Build Finder already does.
 *
 * Theorycrafter must instead **generate builds from scratch** using the
 * official 3.28 data vendored in the repo (passive tree, gem data, item
 * bases) — never the player ladder. The wrong engine was removed; the
 * correct from-scratch generator is a future step. This page is a
 * deliberate "coming soon" stub so the route stays reserved.
 */

import { Box, Stack, Text, Title } from "@mantine/core";
import { IconFlask } from "@tabler/icons-react";
import { useT } from "../i18n";

export function TheorycrafterPage() {
  const t = useT();
  return (
    <Stack align="center" gap="sm" py={64}>
      <Box
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: 72,
          height: 72,
          borderRadius: "50%",
          border: "1px solid var(--vs-ember-border)",
          background: "var(--vs-ember-dim)",
        }}
      >
        <IconFlask size={36} color="var(--vs-ember)" stroke={1.4} />
      </Box>
      <Title order={2} ta="center">
        Theorycrafter
      </Title>
      <Text size="sm" c="dimmed" ta="center" maw={460}>
        {t({
          it: "In arrivo: un generatore che costruisce build da zero usando i dati ufficiali di PoE 3.28 (albero passivo, gemme, basi oggetto). Non attinge dalla classifica dei giocatori — quello è il compito del Build Finder.",
          en: "Coming soon: a generator that builds from scratch using the official PoE 3.28 data (passive tree, gems, item bases). It does not draw from the player ladder — that is the Build Finder's job.",
        })}
      </Text>
    </Stack>
  );
}
