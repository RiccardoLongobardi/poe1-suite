/**
 * Top-level shell: routing + navbar.
 *
 * Routes:
 *   /          → WelcomePage (animated intro, redirected to /home if seen)
 *   /home      → HomePage   (dashboard)
 *   /finder    → FinderPage (Build Finder)
 *   /analyze   → AnalyzePage (PoB analyzer)
 *   /planner   → PlannerPage (Planner)
 *
 * Navbar appears on every route except /. The "Pianifica" button on
 * Build Finder cards still lifts state through this component, but we
 * now go via React Router instead of useState.
 */

import {
  ActionIcon,
  AppShell,
  Burger,
  Button,
  Container,
  Group,
  NavLink,
  Text,
  Title,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconHeart,
  IconHome,
  IconListCheck,
  IconMoon,
  IconSearch,
  IconSparkles,
  IconSun,
  IconTool,
} from "@tabler/icons-react";
import { useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { DonationModal } from "./components/DonationModal";
import { AnalyzePage } from "./pages/AnalyzePage";
import { FinderPage } from "./pages/FinderPage";
import { HomePage } from "./pages/HomePage";
import { PlannerPage } from "./pages/PlannerPage";
import { WelcomePage } from "./pages/WelcomePage";
import { hasSeenWelcome } from "./state/welcome";

/**
 * Root chrome. The welcome route renders edge-to-edge without the
 * AppShell so the cinematic intro feels uninterrupted; every other
 * route goes through ``ShellLayout`` for the navbar + container.
 */
export function App() {
  const location = useLocation();
  const isWelcome = location.pathname === "/";

  if (isWelcome) {
    return (
      <Routes>
        <Route
          path="/"
          element={hasSeenWelcome() ? <Navigate to="/home" replace /> : <WelcomePage />}
        />
      </Routes>
    );
  }

  return <ShellLayout />;
}

function ShellLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [opened, { toggle, close }] = useDisclosure();
  const [plannerInput, setPlannerInput] = useState<string | undefined>(undefined);
  const [donationOpen, donation] = useDisclosure(false);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  const onSendToPlanner = (pobCode: string) => {
    setPlannerInput(pobCode);
    navigate("/planner");
    close();
  };

  const navTo = (path: string) => () => {
    navigate(path);
    close();
  };

  const isActive = (path: string) =>
    location.pathname === path ||
    (path === "/home" && location.pathname === "/home");

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header
        style={{
          backgroundColor: "rgba(13, 4, 32, 0.85)",
          backdropFilter: "blur(8px)",
          borderBottom: "1px solid rgba(110, 38, 255, 0.25)",
        }}
      >
        <Group h="100%" px="md" justify="space-between">
          <Group gap={10}>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Group
              gap={8}
              style={{ cursor: "pointer" }}
              onClick={() => navigate("/home")}
            >
              <IconSparkles size={22} color="var(--astral-glow)" />
              <Title
                order={4}
                style={{ letterSpacing: "0.05em", margin: 0 }}
              >
                FOB
              </Title>
              <Text size="xs" c="dimmed" visibleFrom="sm">
                Frusta Oracle Builder
              </Text>
            </Group>
          </Group>
          <Group gap={8}>
            <Button
              size="xs"
              variant="subtle"
              color="gold"
              leftSection={<IconHeart size={14} />}
              onClick={donation.open}
              visibleFrom="sm"
            >
              Supporta
            </Button>
            <ActionIcon
              variant="subtle"
              onClick={toggleColorScheme}
              title="Cambia tema"
              size="lg"
            >
              {colorScheme === "dark" ? (
                <IconSun size={18} />
              ) : (
                <IconMoon size={18} />
              )}
            </ActionIcon>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar
        p="xs"
        style={{
          backgroundColor: "rgba(13, 4, 32, 0.7)",
          backdropFilter: "blur(8px)",
          borderRight: "1px solid rgba(110, 38, 255, 0.15)",
        }}
      >
        <NavLink
          label="Home"
          leftSection={<IconHome size={16} />}
          active={isActive("/home")}
          onClick={navTo("/home")}
          variant="light"
        />
        <NavLink
          label="Build Finder"
          leftSection={<IconSearch size={16} />}
          active={isActive("/finder")}
          onClick={navTo("/finder")}
          variant="light"
        />
        <NavLink
          label="Analizza PoB"
          leftSection={<IconTool size={16} />}
          active={isActive("/analyze")}
          onClick={navTo("/analyze")}
          variant="light"
        />
        <NavLink
          label="Planner"
          leftSection={<IconListCheck size={16} />}
          active={isActive("/planner")}
          onClick={navTo("/planner")}
          variant="light"
        />
        <Button
          size="xs"
          variant="subtle"
          color="gold"
          leftSection={<IconHeart size={14} />}
          onClick={donation.open}
          mt="auto"
          hiddenFrom="sm"
        >
          Supporta
        </Button>
      </AppShell.Navbar>

      <AppShell.Main>
        <Container size="lg">
          <Routes>
            <Route path="/home" element={<HomePage />} />
            <Route
              path="/finder"
              element={<FinderPage onSendToPlanner={onSendToPlanner} />}
            />
            <Route path="/analyze" element={<AnalyzePage />} />
            <Route
              path="/planner"
              element={<PlannerPage initialInput={plannerInput} />}
            />
            <Route path="*" element={<Navigate to="/home" replace />} />
          </Routes>
        </Container>
      </AppShell.Main>

      <DonationModal opened={donationOpen} onClose={donation.close} />
    </AppShell>
  );
}
