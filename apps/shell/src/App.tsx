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
  Box,
  Burger,
  Button,
  Container,
  Divider,
  Group,
  Loader,
  NavLink,
  SegmentedControl,
  Text,
  Title,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconHeart,
  IconHistory,
  IconHome,
  IconKeyboard,
  IconListCheck,
  IconMoon,
  IconSearch,
  IconSparkles,
  IconSun,
  IconTool,
} from "@tabler/icons-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { prefetchLeague } from "./api/tradeRedirect";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { DonationModal } from "./components/DonationModal";
import { KeyboardShortcutsModal } from "./components/KeyboardShortcutsModal";
import { ParticleCanvas } from "./components/ParticleCanvas";
import { WarmupOverlay } from "./components/WarmupOverlay";
import { useLang, useT } from "./i18n";
import { HomePage } from "./pages/HomePage";
import { PatchNotesPage } from "./pages/PatchNotesPage";
import { WelcomePage } from "./pages/WelcomePage";
import { hasSeenWelcome } from "./state/welcome";

// Route-level code-splitting. The three heaviest feature pages (each
// pulls in its own chart/planner/analysis machinery) are lazy-loaded
// so the initial bundle only carries the shell + landing. They are
// named exports, hence the `.then(m => ({ default: ... }))` adapter.
// HomePage / WelcomePage / PatchNotesPage stay eager — they are small
// and HomePage is the first thing most sessions render.
const FinderPage = lazy(() =>
  import("./pages/FinderPage").then((m) => ({ default: m.FinderPage })),
);
const AnalyzePage = lazy(() =>
  import("./pages/AnalyzePage").then((m) => ({ default: m.AnalyzePage })),
);
const PlannerPage = lazy(() =>
  import("./pages/PlannerPage").then((m) => ({ default: m.PlannerPage })),
);

/**
 * Inline fallback shown while a lazy route chunk loads. Lives inside
 * `AppShell.Main` so the navbar/header stay put; it never overlaps the
 * full-viewport WarmupOverlay (which sits above everything at a higher
 * z-index during the Render cold-start).
 */
function RouteFallback() {
  const t = useT();
  return (
    <Box
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "50vh",
        gap: 12,
      }}
    >
      <Loader color="ember" />
      <Text size="sm" c="dimmed" style={{ fontFamily: "'Cinzel', serif" }}>
        {t({ it: "Evoco la pagina…", en: "Summoning the page…" })}
      </Text>
    </Box>
  );
}

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
      {/* Ambient ember particle field — fixed, behind all content. */}
      <ParticleCanvas />
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
  const [helpOpen, help] = useDisclosure(false);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const { lang, setLang } = useLang();
  const t = useT();

  const onSendToPlanner = (pobCode: string) => {
    setPlannerInput(pobCode);
    navigate("/planner");
    close();
  };

  const navTo = (path: string) => () => {
    navigate(path);
    close();
  };

  // Global keyboard shortcuts. `G` then F/A/P/N navigates; T/L toggle
  // theme/language; `?` opens this card. Ignored while typing in an
  // input/textarea or with a modifier held.
  const pendingG = useRef(false);
  const pendingGTimer = useRef<number | undefined>(undefined);
  useEffect(() => {
    const onKey = (e: KeyboardEvent): void => {
      const el = document.activeElement;
      if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const k = e.key.toLowerCase();
      if (pendingG.current) {
        pendingG.current = false;
        window.clearTimeout(pendingGTimer.current);
        const dest: Record<string, string> = {
          f: "/finder",
          a: "/analyze",
          p: "/planner",
          n: "/patch-notes",
        };
        if (dest[k]) {
          e.preventDefault();
          navigate(dest[k]);
        }
        return;
      }
      if (k === "g") {
        pendingG.current = true;
        pendingGTimer.current = window.setTimeout(() => {
          pendingG.current = false;
        }, 1000);
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        help.toggle();
        return;
      }
      if (k === "t") toggleColorScheme();
      else if (k === "l") setLang(lang === "it" ? "en" : "it");
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.clearTimeout(pendingGTimer.current);
    };
  }, [navigate, toggleColorScheme, setLang, lang, help]);

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
              <IconSparkles
                size={22}
                color="var(--vs-ember)"
                className="vs-logo-pulse"
              />
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
              {/* brand tagline kept untranslated — it is the project name */}
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
              {t({ it: "Supporta", en: "Support" })}
            </Button>
            <SegmentedControl
              size="xs"
              value={lang}
              onChange={(v) => setLang(v === "en" ? "en" : "it")}
              data={[
                { value: "it", label: "IT" },
                { value: "en", label: "EN" },
              ]}
              aria-label={t({ it: "Lingua", en: "Language" })}
            />
            <ActionIcon
              variant="subtle"
              onClick={help.open}
              title={t({
                it: "Scorciatoie da tastiera (?)",
                en: "Keyboard shortcuts (?)",
              })}
              size="lg"
              visibleFrom="sm"
            >
              <IconKeyboard size={18} />
            </ActionIcon>
            <ActionIcon
              variant="subtle"
              onClick={toggleColorScheme}
              title={t({ it: "Cambia tema", en: "Toggle theme" })}
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
          label={t({ it: "Home", en: "Home" })}
          leftSection={<IconHome size={16} />}
          active={isActive("/home")}
          onClick={navTo("/home")}
          variant="light"
        />
        <NavLink
          label={t({ it: "Build Finder", en: "Build Finder" })}
          leftSection={<IconSearch size={16} />}
          active={isActive("/finder")}
          onClick={navTo("/finder")}
          variant="light"
        />
        <NavLink
          label={t({ it: "Analizza PoB", en: "Analyse PoB" })}
          leftSection={<IconTool size={16} />}
          active={isActive("/analyze")}
          onClick={navTo("/analyze")}
          variant="light"
        />
        <NavLink
          label={t({ it: "Planner", en: "Planner" })}
          leftSection={<IconListCheck size={16} />}
          active={isActive("/planner")}
          onClick={navTo("/planner")}
          variant="light"
        />

        {/* Secondary — pushed to the bottom, low prominence. */}
        <Divider mt="auto" mb={4} color="var(--vs-border-faint)" />
        <NavLink
          label={t({ it: "Note di rilascio", en: "Patch notes" })}
          leftSection={<IconHistory size={14} />}
          active={isActive("/patch-notes")}
          onClick={navTo("/patch-notes")}
          variant="light"
          styles={{ label: { fontSize: "0.78rem", color: "var(--vs-text-muted)" } }}
        />
        <Button
          size="xs"
          variant="subtle"
          color="ember"
          leftSection={<IconHeart size={14} />}
          onClick={donation.open}
          hiddenFrom="sm"
        >
          {t({ it: "Supporta", en: "Support" })}
        </Button>
      </AppShell.Navbar>

      <AppShell.Main>
        <Container size="xl">
          {/* Keyed on the path so each route change replays the
              lightweight CSS fade-in (`.vs-route`). */}
          <div className="vs-route" key={location.pathname}>
            <Suspense fallback={<RouteFallback />}>
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
                <Route path="/patch-notes" element={<PatchNotesPage />} />
                <Route path="*" element={<Navigate to="/home" replace />} />
              </Routes>
            </Suspense>
          </div>
        </Container>
      </AppShell.Main>

      <DonationModal opened={donationOpen} onClose={donation.close} />
      <KeyboardShortcutsModal opened={helpOpen} onClose={help.close} />
    </AppShell>
  );
}
