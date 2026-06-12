/**
 * FOB v2 — "Obsidian Pro" shell: routing + sticky top navbar.
 *
 * v2 chrome decisions (vs v1):
 * - Sticky top navbar with horizontal tool tabs (professional-tool
 *   layout) instead of the v1 side rail. On narrow screens the tab
 *   row scrolls horizontally — no burger, no drawer.
 * - No welcome/splash gate: "/" lands straight on the Home dashboard.
 * - No particle canvas: a static ambient glow lives in index.css.
 * - Footer carries the secondary links (patch notes / FAQ / privacy).
 *
 * Everything functional is inherited from v1: routes, the Finder →
 * Planner / Analyze lifts, global keyboard shortcuts, the donation
 * modal and the cold-start warmup overlay.
 */

import {
  ActionIcon,
  Box,
  Button,
  Group,
  Loader,
  SegmentedControl,
  Text,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconFlask,
  IconHeart,
  IconHelpCircle,
  IconHistory,
  IconHome,
  IconKeyboard,
  IconListCheck,
  IconMoon,
  IconSearch,
  IconShieldLock,
  IconSparkles,
  IconSun,
  IconTool,
} from "@tabler/icons-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { prefetchLeague } from "./api/tradeRedirect";
import { DonationModal } from "./components/DonationModal";
import { KeyboardShortcutsModal } from "./components/KeyboardShortcutsModal";
import { WarmupOverlay } from "./components/WarmupOverlay";
import { useLang, useT } from "./i18n";
import { FaqPage } from "./pages/FaqPage";
import { HomePage } from "./pages/HomePage";
import { PatchNotesPage } from "./pages/PatchNotesPage";
import { PrivacyPage } from "./pages/PrivacyPage";
import { usePageStore } from "./store/pageStore";

// Route-level code-splitting — the heavy feature pages load on demand.
const FinderPage = lazy(() =>
  import("./pages/FinderPage").then((m) => ({ default: m.FinderPage })),
);
const AnalyzePage = lazy(() =>
  import("./pages/AnalyzePage").then((m) => ({ default: m.AnalyzePage })),
);
const PlannerPage = lazy(() =>
  import("./pages/PlannerPage").then((m) => ({ default: m.PlannerPage })),
);
const TheorycrafterPage = lazy(() =>
  import("./pages/TheorycrafterPage").then((m) => ({
    default: m.TheorycrafterPage,
  })),
);

/** Inline fallback while a lazy route chunk loads. */
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
      <Text size="sm" c="dimmed">
        {t({ it: "Carico la pagina…", en: "Loading the page…" })}
      </Text>
    </Box>
  );
}

interface NavItem {
  path: string;
  it: string;
  en: string;
  icon: React.ReactNode;
}

const NAV_ITEMS: NavItem[] = [
  { path: "/home", it: "Home", en: "Home", icon: <IconHome size={16} /> },
  {
    path: "/finder",
    it: "Build Finder",
    en: "Build Finder",
    icon: <IconSearch size={16} />,
  },
  {
    path: "/analyze",
    it: "Analizza",
    en: "Analyze",
    icon: <IconTool size={16} />,
  },
  {
    path: "/planner",
    it: "Planner",
    en: "Planner",
    icon: <IconListCheck size={16} />,
  },
  {
    path: "/theorycrafter",
    it: "Theorycrafter",
    en: "Theorycrafter",
    icon: <IconFlask size={16} />,
  },
];

export function App() {
  const navigate = useNavigate();
  const location = useLocation();
  const [plannerInput, setPlannerInput] = useState<string | undefined>(
    undefined,
  );
  const [donationOpen, donation] = useDisclosure(false);
  const [helpOpen, help] = useDisclosure(false);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const { lang, setLang } = useLang();
  const t = useT();

  // Prefetch the current league once per session so "Apri Trade"
  // buttons stay synchronous (popup blocker quiet) on first click.
  useEffect(() => {
    void prefetchLeague();
  }, []);

  const onSendToPlanner = (pobCode: string) => {
    setPlannerInput(pobCode);
    navigate("/planner");
  };

  // Finder → Analyze lift: stash the poe.ninja URL in the analyze slice
  // with the one-shot autorun flag; AnalyzePage runs it on mount.
  const setAnalyze = usePageStore((s) => s.setAnalyze);
  const onSendToAnalyze = (input: string) => {
    setAnalyze({ input, result: null, autorun: true });
    navigate("/analyze");
  };

  // Global keyboard shortcuts. `G` then F/A/P/N navigates; T/L toggle
  // theme/language; `?` opens the shortcuts card. Ignored while typing
  // in an input/textarea or with a modifier held.
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

  const isActive = (path: string) => location.pathname === path;

  return (
    <>
      {/* Cold-start overlay — covers the viewport while the free-tier
          backend wakes up. */}
      <WarmupOverlay />

      {/* ── Sticky top navbar ─────────────────────────────────────── */}
      <header className="v2-header">
        <div className="v2-header-inner">
          {/* Brand */}
          <Group
            gap={8}
            wrap="nowrap"
            style={{ cursor: "pointer", flexShrink: 0 }}
            onClick={() => navigate("/home")}
          >
            <IconSparkles
              size={22}
              color="var(--vs-ember-bright)"
              className="vs-logo-pulse"
            />
            <Text
              className="brand-serif"
              fw={700}
              size="lg"
              style={{ color: "var(--vs-ember-bright)", lineHeight: 1 }}
            >
              FOB
            </Text>
          </Group>

          {/* Tool tabs — horizontal, scrollable on narrow screens. */}
          <nav className="v2-nav" aria-label={t({ it: "Strumenti", en: "Tools" })}>
            {NAV_ITEMS.map((item) => (
              <button
                key={item.path}
                type="button"
                className="v2-nav-link"
                data-active={isActive(item.path) || undefined}
                onClick={() => navigate(item.path)}
              >
                {item.icon}
                <span>{t({ it: item.it, en: item.en })}</span>
              </button>
            ))}
          </nav>

          {/* Right controls */}
          <Group gap={6} wrap="nowrap" style={{ flexShrink: 0 }}>
            <Button
              size="xs"
              variant="subtle"
              color="ember"
              leftSection={<IconHeart size={14} />}
              onClick={donation.open}
              visibleFrom="md"
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
              visibleFrom="md"
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
        </div>
      </header>

      {/* ── Routed content ────────────────────────────────────────── */}
      <main className="v2-main">
        {/* Keyed on the path so each route change replays the
            lightweight CSS fade-in (`.vs-route`). */}
        <div className="vs-route" key={location.pathname}>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/home" element={<HomePage />} />
              <Route
                path="/finder"
                element={
                  <FinderPage
                    onSendToPlanner={onSendToPlanner}
                    onSendToAnalyze={onSendToAnalyze}
                  />
                }
              />
              <Route path="/analyze" element={<AnalyzePage />} />
              <Route
                path="/planner"
                element={<PlannerPage initialInput={plannerInput} />}
              />
              <Route path="/theorycrafter" element={<TheorycrafterPage />} />
              <Route path="/patch-notes" element={<PatchNotesPage />} />
              <Route path="/faq" element={<FaqPage />} />
              <Route path="/privacy" element={<PrivacyPage />} />
              {/* No welcome gate in v2 — everything else lands on Home. */}
              <Route path="*" element={<Navigate to="/home" replace />} />
            </Routes>
          </Suspense>
        </div>
      </main>

      {/* ── Footer — secondary links ──────────────────────────────── */}
      <footer className="v2-footer">
        <div className="v2-footer-inner">
          <Text size="xs" c="dimmed">
            FOB · Frusta Oracle Builder —{" "}
            {t({
              it: "progetto personale, open-source su GitHub",
              en: "a personal project, open-source on GitHub",
            })}
          </Text>
          <Group gap={4}>
            <Button
              size="compact-xs"
              variant="subtle"
              color="gray"
              leftSection={<IconHistory size={13} />}
              onClick={() => navigate("/patch-notes")}
            >
              {t({ it: "Note di rilascio", en: "Patch notes" })}
            </Button>
            <Button
              size="compact-xs"
              variant="subtle"
              color="gray"
              leftSection={<IconHelpCircle size={13} />}
              onClick={() => navigate("/faq")}
            >
              FAQ
            </Button>
            <Button
              size="compact-xs"
              variant="subtle"
              color="gray"
              leftSection={<IconShieldLock size={13} />}
              onClick={() => navigate("/privacy")}
            >
              Privacy
            </Button>
            <Button
              size="compact-xs"
              variant="subtle"
              color="ember"
              leftSection={<IconHeart size={13} />}
              onClick={donation.open}
            >
              {t({ it: "Supporta", en: "Support" })}
            </Button>
          </Group>
        </div>
      </footer>

      <DonationModal opened={donationOpen} onClose={donation.close} />
      <KeyboardShortcutsModal opened={helpOpen} onClose={help.close} />
    </>
  );
}
