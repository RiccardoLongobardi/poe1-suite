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
import { PAYPAL_URL } from "../theme";

interface Props {
  opened: boolean;
  onClose: () => void;
}

export function DonationModal({ opened, onClose }: Props) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap={8}>
          <ThemeIcon variant="light" color="gold" size="lg" radius="xl">
            <IconHeart size={20} />
          </ThemeIcon>
          <Title order={3} style={{ margin: 0 }}>
            Supporta FOB
          </Title>
        </Group>
      }
      size="md"
      centered
      overlayProps={{ backgroundOpacity: 0.7, blur: 4 }}
    >
      <Stack gap="md">
        <Text size="sm">
          FOB nasce come tool personale per Path of Exile. Mantenerlo aggiornato
          ogni lega (parser PoB, schema poe.ninja, GGG Trade API che cambia)
          richiede tempo e qualche caffè.
        </Text>

        <Group gap="md" align="flex-start">
          <ThemeIcon variant="light" color="astral" size="lg" radius="md">
            <IconSparkles size={20} />
          </ThemeIcon>
          <Stack gap={2} flex={1}>
            <Text size="sm" fw={500}>
              Cosa cambia se doni
            </Text>
            <Text size="xs" c="dimmed">
              Niente: il tool resta gratis e open-source. Però mi paghi una
              lattina di Red Bull a 2:00 AM mentre sistemo il parser per la
              prossima lega.
            </Text>
          </Stack>
        </Group>

        <Group gap="md" align="flex-start">
          <ThemeIcon variant="light" color="gold" size="lg" radius="md">
            <IconCoffee size={20} />
          </ThemeIcon>
          <Stack gap={2} flex={1}>
            <Text size="sm" fw={500}>
              Quanto donare
            </Text>
            <Text size="xs" c="dimmed">
              Quello che vuoi. Anche 1 € è apprezzato. Anche solo passare a
              dire grazie su PayPal lo è.
            </Text>
          </Stack>
        </Group>

        <Button
          component="a"
          href={PAYPAL_URL}
          target="_blank"
          rel="noopener noreferrer"
          color="gold"
          size="md"
          fullWidth
          rightSection={<IconExternalLink size={16} />}
          mt="sm"
        >
          Apri PayPal — paypal.me/riclong
        </Button>

        <Text size="xs" c="dimmed" ta="center">
          Si apre in una nuova scheda. Non ti vengono richiesti dati
          finanziari da FOB.
        </Text>
      </Stack>
    </Modal>
  );
}
