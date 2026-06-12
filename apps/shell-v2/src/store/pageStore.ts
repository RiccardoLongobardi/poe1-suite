/**
 * pageStore — cross-route UI state for the Finder / Analyze / Planner
 * pages.
 *
 * Those three feature pages are lazy-loaded (Step 26), so they unmount
 * on navigation and any local `useState` is lost. This Zustand store
 * lives outside the React tree, so each page's last query / results /
 * filters survive in-session navigation.
 *
 * Persistence: the store is mirrored into `sessionStorage` so state
 * also survives a page reload within the same browser session (but
 * not across sessions — that is the intended scope). If
 * `sessionStorage` is unavailable (sandboxed iframe, private mode,
 * quota) it transparently falls back to an in-memory Map — navigation
 * survival still works because the store itself is module-scoped;
 * only reload-survival is lost.
 *
 * Only *restorable* state lives here. Transient flags (in-flight
 * loading, SSE progress, errors) stay as local `useState` in the
 * pages — they must reset on navigation.
 */

import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type {
  AnalyzePobResponse,
  Build,
  BuildIntent,
  BuildPlan,
  BuildSkeleton,
  DamageType,
  DefenceArchetype,
  SkeletonBudget,
  TheoryContentFocus,
  RecommendResponse,
  SortKey,
  TargetGoal,
} from "../api/types";

// ---------------------------------------------------------------------------
// Finder slice
// ---------------------------------------------------------------------------

/** The Finder's structured search criteria — the primary input since the
 * structured-search rework (no more NL query / parsing confidence). */
export interface FinderFilters {
  /** Exact main-skill name from the catalogue-derived list (null = any). */
  skill: string | null;
  class_filter: string | null;
  /** Content-focus key (mapping / bossing / ubers / …); null = any. */
  focus: string | null;
  sort_by: SortKey;
  min_life: number | null;
  min_es: number | null;
  min_ehp: number | null;
  min_dps: number | null;
  min_level: number | null;
  max_level: number | null;
}

export function emptyFinderFilters(): FinderFilters {
  return {
    skill: null,
    class_filter: null,
    focus: null,
    sort_by: "score",
    min_life: null,
    min_es: null,
    min_ehp: null,
    min_dps: null,
    min_level: null,
    max_level: null,
  };
}

export interface FinderState {
  query: string;
  topN: number;
  intent: BuildIntent | null;
  overrides: FinderFilters;
  result: RecommendResponse | null;
  skillFilter: string | null;
  editing: boolean;
}

function emptyFinder(): FinderState {
  return {
    query: "",
    topN: 10,
    intent: null,
    overrides: emptyFinderFilters(),
    result: null,
    skillFilter: null,
    editing: true,
  };
}

// ---------------------------------------------------------------------------
// Analyze slice
// ---------------------------------------------------------------------------

export interface AnalyzeState {
  input: string;
  result: AnalyzePobResponse | null;
  editing: boolean;
  /** One-shot flag: when true, AnalyzePage runs the analysis on mount
   * (set by the Finder's "Analizza" lift) and resets it. */
  autorun: boolean;
}

function emptyAnalyze(): AnalyzeState {
  return { input: "", result: null, editing: true, autorun: false };
}

// ---------------------------------------------------------------------------
// Planner slice
// ---------------------------------------------------------------------------

/** What the Planner page renders once a plan has streamed in. */
export interface PlannerResult {
  build: Build;
  plan: BuildPlan;
  /** Identifier of the BuildTemplate the planner picked. */
  templateName: string | null;
}

export interface PlannerState {
  input: string;
  /** PoB code after resolving a poe.ninja URL — passed to stage export. */
  resolvedCode: string | null;
  target: TargetGoal;
  reverseMode: boolean;
  result: PlannerResult | null;
  editing: boolean;
  /** Index of the stage open in the desktop timeline. */
  activeStage: number;
}

function emptyPlanner(): PlannerState {
  return {
    input: "",
    resolvedCode: null,
    target: "mapping_and_boss",
    reverseMode: false,
    result: null,
    editing: true,
    activeStage: 0,
  };
}

// ---------------------------------------------------------------------------
// Theorycrafter slice (Step 40 — form-driven)
// ---------------------------------------------------------------------------

export interface TheoryFormState {
  character_class: string;
  ascendancy: string;
  primary_skill: string;
  damage_type: DamageType | "";
  defence_archetype: DefenceArchetype;
  budget: SkeletonBudget;
  focus: TheoryContentFocus;
}

export interface TheoryState {
  form: TheoryFormState;
  result: BuildSkeleton | null;
}

function emptyTheory(): TheoryState {
  return {
    form: {
      character_class: "",
      ascendancy: "",
      primary_skill: "",
      damage_type: "",
      defence_archetype: "life",
      budget: "mid",
      focus: "mapping",
    },
    result: null,
  };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface PageStore {
  finder: FinderState;
  setFinder: (patch: Partial<FinderState>) => void;
  resetFinder: () => void;

  analyze: AnalyzeState;
  setAnalyze: (patch: Partial<AnalyzeState>) => void;

  planner: PlannerState;
  setPlanner: (patch: Partial<PlannerState>) => void;

  theory: TheoryState;
  setTheory: (patch: Partial<TheoryState>) => void;
}

/**
 * `sessionStorage`-backed storage that degrades to an in-memory Map
 * when `sessionStorage` is unavailable or throws (private mode,
 * sandboxed iframe, quota exceeded).
 */
const memoryFallback = new Map<string, string>();

const resilientStorage: StateStorage = {
  getItem: (name) => {
    try {
      return sessionStorage.getItem(name);
    } catch {
      return memoryFallback.get(name) ?? null;
    }
  },
  setItem: (name, value) => {
    try {
      sessionStorage.setItem(name, value);
    } catch {
      memoryFallback.set(name, value);
    }
  },
  removeItem: (name) => {
    try {
      sessionStorage.removeItem(name);
    } catch {
      memoryFallback.delete(name);
    }
  },
};

export const usePageStore = create<PageStore>()(
  persist(
    (set) => ({
      finder: emptyFinder(),
      setFinder: (patch) => set((s) => ({ finder: { ...s.finder, ...patch } })),
      resetFinder: () => set({ finder: emptyFinder() }),

      analyze: emptyAnalyze(),
      setAnalyze: (patch) =>
        set((s) => ({ analyze: { ...s.analyze, ...patch } })),

      planner: emptyPlanner(),
      setPlanner: (patch) =>
        set((s) => ({ planner: { ...s.planner, ...patch } })),

      theory: emptyTheory(),
      setTheory: (patch) => set((s) => ({ theory: { ...s.theory, ...patch } })),
    }),
    {
      name: "fob-page-state",
      // v2: FinderFilters gained `skill` + `focus` (structured search) and
      // AnalyzeState gained `autorun` — a v1 payload would restore filter
      // objects missing those keys, so it's discarded (session-scoped state,
      // losing it on deploy is fine).
      version: 2,
      storage: createJSONStorage(() => resilientStorage),
    },
  ),
);
