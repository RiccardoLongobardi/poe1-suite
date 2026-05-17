/**
 * DonationModal — ask politely, link to PayPal.
 *
 * Triggered from the HomePage support card and from a navbar
 * "Supporta" button. We open the donor's link in a new tab rather
 * than embedding the PayPal flow inline; PayPal blocks iframe
 * embedding for security and the modal stays clean.
 *
 * Copy is in Italian to match the rest of the UX.
 */

import { Button, Group, Modal, Stack, Text, ThemeIcon, Title } from "@mantine/core";
import {
  IconCoffee,
  IconExternalLink,
  IconHeart,
  IconSparkles,
} from "@tabler/icons-react";
import { useT } from "../i18n";
import { PAYPAL_URL } from "../theme";

interface Props {
  opened: boolean;
  onClose: () => void;
}

export function DonationModal({ opened, onClose }: Props) {
  const t = useT();
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap={8}>
          <ThemeIcon variant="light" color="ember" size="lg" radius="xl">
            <IconHeart size={20} />
          </ThemeIcon>
          <Title order={3} style={{ margin: 0 }}>
            {t({ it: "Supporta FOB", en: "Support FOB" })}
          </Title>
        </Group>
      }
      size="md"
      centered
      overlayProps={{ backgroundOpacity: 0.7, blur: 4 }}
    >
      <Stack gap="md">
        <Text size="sm">
          {t({
            it: "FOB nasce come tool personale per Path of Exile. Mantenerlo aggiornato ogni lega (parser PoB, schema poe.ninja, GGG Trade API che cambia) richiede tempo e qualche caffè.",
            en: "FOB started as a personal Path of Exile tool. Keeping it updated every league (PoB parser, poe.ninja schema, the shifting GGG Trade API) takes time and a few coffees.",
          })}
        </Text>

        <Group gap="md" align="flex-start">
          <ThemeIcon variant="light" color="ember" size="lg" radius="md">
            <IconSparkles size={20} />
          </ThemeIcon>
          <Stack gap={2} flex={1}>
            <Text size="sm" fw={500}>
              {t({ it: "Cosa cambia se doni", en: "What changes if you donate" })}
            </Text>
            <Text size="xs" c="dimmed">
              {t({
                it: "Niente: il tool resta gratis e open-source. Però mi paghi una lattina di Red Bull a 2:00 AM mentre sistemo il parser per la prossima lega.",
                en: "Nothing: the tool stays free and open-source. But you'd buy me a can of Red Bull at 2:00 AM while I fix the parser for the next league.",
              })}
            </Text>
          </Stack>
        </Group>

        <Group gap="md" align="flex-start">
          <ThemeIcon variant="light" color="ember" size="lg" radius="md">
            <IconCoffee size={20} />
          </ThemeIcon>
          <Stack gap={2} flex={1}>
            <Text size="sm" fw={500}>
              {t({ it: "Quanto donare", en: "How much to donate" })}
            </Text>
            <Text size="xs" c="dimmed">
              {t({
                it: "Quello che vuoi. Anche 1 € è apprezzato. Anche solo passare a dire grazie su PayPal lo è.",
                en: "Whatever you want. Even €1 is appreciated. Even just stopping by to say thanks on PayPal counts.",
              })}
            </Text>
          </Stack>
        </Group>

        <Button
          component="a"
          href={PAYPAL_URL}
          target="_blank"
          rel="noopener noreferrer"
          color="ember"
          size="md"
          fullWidth
          rightSection={<IconExternalLink size={16} />}
          mt="sm"
        >
          {t({
            it: "Apri PayPal — paypal.me/riclong",
            en: "Open PayPal — paypal.me/riclong",
          })}
        </Button>

        <Text size="xs" c="dimmed" ta="center">
          {t({
            it: "Si apre in una nuova scheda. Non ti vengono richiesti dati finanziari da FOB.",
            en: "Opens in a new tab. FOB never asks you for financial details.",
          })}
        </Text>
      </Stack>
    </Modal>
  );
}
