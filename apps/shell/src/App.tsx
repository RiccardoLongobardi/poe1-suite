import {
  AppShell,
  Burger,
  Container,
  Group,
  NavLink,
  Text,
  Title,
  useMantineColorScheme,
  ActionIcon,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconListCheck,
  IconMoon,
  IconSearch,
  IconSun,
  IconTool,
} from "@tabler/icons-react";
import { useState } from "react";
import { AnalyzePage } from "./pages/AnalyzePage";
import { FinderPage } from "./pages/FinderPage";
import { PlannerPage } from "./pages/PlannerPage";

type Page = "finder" | "analyze" | "planner";

export function App() {
  const [opened, { toggle }] = useDisclosure();
  const [page, setPage] = useState<Page>("finder");
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  const nav = (p: Page) => () => {
    setPage(p);
    // close sidebar on mobile
    if (opened) toggle();
  };

  return (
    <AppShell
      header={{ height: 52 }}
      navbar={{ width: 200, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap={8}>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={4} style={{ letterSpacing: -0.5 }}>
              poe1-suite
            </Title>
            <Text size="xs" c="dimmed" visibleFrom="sm">
              FOB Build Advisor
            </Text>
          </Group>
          <ActionIcon
            variant="subtle"
            onClick={toggleColorScheme}
            title="Cambia tema"
          >
            {colorScheme === "dark" ? (
              <IconSun size={18} />
            ) : (
              <IconMoon size={18} />
            )}
          </ActionIcon>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        <NavLink
          label="Build Finder"
          leftSection={<IconSearch size={16} />}
          active={page === "finder"}
          onClick={nav("finder")}
          variant="light"
        />
        <NavLink
          label="Analizza PoB"
          leftSection={<IconTool size={16} />}
          active={page === "analyze"}
          onClick={nav("analyze")}
          variant="light"
        />
        <NavLink
          label="Planner"
          leftSection={<IconListCheck size={16} />}
          active={page === "planner"}
          onClick={nav("planner")}
          variant="light"
        />
      </AppShell.Navbar>

      <AppShell.Main>
        <Container size="lg">
          {page === "finder" && <FinderPage />}
          {page === "analyze" && <AnalyzePage />}
          {page === "planner" && <PlannerPage />}
        </Container>
      </AppShell.Main>
    </AppShell>
  );
}
