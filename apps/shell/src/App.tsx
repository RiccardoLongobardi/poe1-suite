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
import { useEffect, useState } from "react";
import { prefetchLeague } from "./api/tradeRedirect";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { DonationModal } from "./components/DonationModal";
import { WarmupOverlay } from "./components/WarmupOverlay";
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

  // Prefetch the current league once per session so "Apri Trade"
  // buttons stay synchronous (popup blocker quiet) on first click.
  useEffect(() => {
    void prefetchLeague();
  }, []);

  return (
    <>
      {/* Cold-start overlay — covers the whole viewport above every
          route while the Render free-tier backend warms up. */}
      <WarmupOverlay />
      {isWelcome ? (
        <Routes>
          <Route
            path="/"
            element={hasSeenWelcome() ? <Navigate to="/home" replace /> : <WelcomePage />}
          />
        </Routes>
      ) : (
        <ShellLayout />
      )}
    </>
  );
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
          backgroundColor: "rgba(8, 6, 4, 0.85)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--vs-border-faint)",
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
              <IconSparkles size={22} color="var(--vs-ember)" />
              <Title
                order={4}
                style={{
                  letterSpacing: "0.08em",
                  margin: 0,
                  fontFamily: "'Cinzel', serif",
                  color: "var(--vs-ember)",
                }}
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
              color="ember"
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
          backgroundColor: "var(--vs-surface-1)",
          borderRight: "1px solid var(--vs-border-faint)",
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
          color="ember"
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
