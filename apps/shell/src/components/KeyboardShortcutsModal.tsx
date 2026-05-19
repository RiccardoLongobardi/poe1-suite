/**
 * KeyboardShortcutsModal — the `?` overlay listing FOB's keyboard
 * shortcuts. Bilingual via `useT()`.
 *
 * The actual key handling lives in `ShellLayout` (App.tsx) — this
 * component is just the discoverable reference card.
 */

import { Modal, Table, Text } from "@mantine/core";
import { useT } from "../i18n";

interface Props {
  opened: boolean;
  onClose: () => void;
}

const SHORTCUTS: { keys: string; it: string; en: string }[] = [
  { keys: "G F", it: "Vai al Finder", en: "Go to Finder" },
  { keys: "G A", it: "Vai ad Analizza", en: "Go to Analyse" },
  { keys: "G P", it: "Vai al Planner", en: "Go to Planner" },
  { keys: "G N", it: "Vai alle Note di rilascio", en: "Go to Patch Notes" },
  { keys: "?", it: "Mostra/nascondi le scorciatoie", en: "Show/hide shortcuts" },
  { keys: "T", it: "Cambia tema", en: "Toggle theme" },
  { keys: "L", it: "Cambia lingua", en: "Toggle language" },
];

export function KeyboardShortcutsModal({ opened, onClose }: Props) {
  const t = useT();
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="sm"
      centered
      title={t({ it: "Scorciatoie da tastiera", en: "Keyboard shortcuts" })}
    >
      <Table verticalSpacing={6}>
        <Table.Tbody>
          {SHORTCUTS.map((s) => (
            <Table.Tr key={s.keys}>
              <Table.Td style={{ width: 70 }}>
                <Text className="mono" size="sm" fw={700}>
                  {s.keys}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{t({ it: s.it, en: s.en })}</Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Modal>
  );
}
