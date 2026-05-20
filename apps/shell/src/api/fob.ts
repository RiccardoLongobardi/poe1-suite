/**
 * Typed API functions for the FOB endpoints.
 *
 * All functions throw an `Error` with a human-readable message on non-2xx
 * responses so callers (TanStack Query mutations) can handle them uniformly.
 */

import type {
  AnalyzePobResponse,
  ApiError,
  BuildIntent,
  BuildSkeleton,
  GearProgression,
  GemProgression,
  PlanResponse,
  PricingProgress,
  RecommendResponse,
  SkillsResponse,
  StageExportRequest,
  StageExportResponse,
  TargetGoal,
  TheoryIntent,
  TradeModExtractResponse,
  TradeUrlRequest,
  TradeUrlResponse,
  TreeProgression,
} from "./types";

// In dev: empty string → same origin; vite.config.ts proxies /fob → 8765.
// In production: VITE_API_BASE points at the deployed backend
// (e.g. https://fob-api.fly.dev). The trailing slash is stripped to keep
// path concatenation predictable.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err: ApiError = (await res.json().catch(() => ({
      detail: res.statusText,
    }))) as ApiError;
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const err: ApiError = (await res.json().catch(() => ({
      detail: res.statusText,
    }))) as ApiError;
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/** POST /fob/extract-intent */
export async function extractIntent(query: string): Promise<BuildIntent> {
  return post<BuildIntent>("/fob/extract-intent", { query });
}

/** POST /fob/recommend */
export async function recommend(
  intent: BuildIntent,
  topN = 10,
): Promise<RecommendResponse> {
  return post<RecommendResponse>("/fob/recommend", {
    intent,
    top_n: topN,
  });
}

/**
 * POST /fob/theory/generate — Theorycrafter Build Generator v2.
 *
 * Form-driven. The server synthesises a `BuildSkeleton` from a
 * structured `TheoryIntent` using vendored 3.28 data (passive tree,
 * gem tags, item bases) — no ladder, no LLM.
 */
export async function generateBuild(
  intent: TheoryIntent,
): Promise<BuildSkeleton> {
  return post<BuildSkeleton>("/fob/theory/generate", { intent });
}

/** GET /fob/theory/skills — active-skill catalogue for the form. */
export async function getTheorySkills(): Promise<SkillsResponse> {
  return get<SkillsResponse>("/fob/theory/skills");
}

/** POST /fob/analyze-pob */
export async function analyzePob(input: string): Promise<AnalyzePobResponse> {
  return post<AnalyzePobResponse>("/fob/analyze-pob", { input });
}

/**
 * POST /fob/trade-url — return a pre-filled GGG Trade search URL.
 *
 * Server caches the URL by query hash (TTL ~8 min) so common items
 * like Mageblood / Kaom's Heart usually return in <100 ms without
 * hitting GGG. On 429 the response carries source='rate_limited'
 * and url=null — the caller should fall back to opening the bare
 * trade search page.
 */
export async function fetchTradeUrl(
  req: TradeUrlRequest,
): Promise<TradeUrlResponse> {
  return post<TradeUrlResponse>("/fob/trade-url", req);
}

/**
 * POST /fob/extract-trade-mods — resolve an item's mod text to GGG
 * Trade stat ids. Explicit and implicit lines are sent separately so
 * an implicit (incl. corrupted implicit) resolves to the implicit-
 * domain stat, not the same-text explicit one. Stateless + offline.
 */
export async function extractTradeMods(
  explicits: string[],
  implicits: string[] = [],
): Promise<TradeModExtractResponse> {
  return post<TradeModExtractResponse>("/fob/extract-trade-mods", {
    mods: explicits,
    implicit_mods: implicits,
  });
}

/** POST /fob/plan */
export async function planBuild(
  input: string,
  targetGoal: TargetGoal = "mapping_and_boss",
): Promise<PlanResponse> {
  return post<PlanResponse>("/fob/plan", {
    input,
    target_goal: targetGoal,
  });
}

/**
 * POST /fob/plan/reverse — reverse-progression mode (Step 13.C).
 *
 * Same input/output shape as `planBuild`, but the server runs each
 * KeyItem through the reverse-progression engine: every endgame item
 * generates an upgrade ladder of progressively cheaper predecessors,
 * and each rung's rationale is appended to the corresponding stage's
 * `gem_changes` list, prefixed with `[item_name]` so the UI can group.
 */
export async function planBuildReverse(
  input: string,
  targetGoal: TargetGoal = "mapping_and_boss",
): Promise<PlanResponse> {
  return post<PlanResponse>("/fob/plan/reverse", {
    input,
    target_goal: targetGoal,
  });
}

/**
 * POST /fob/plan/stream — SSE-streamed planning.
 *
 * Yields one PricingProgress event per server-side step. The final event
 * (kind === 'done') carries the assembled BuildPlan in its final_plan field.
 *
 * EventSource only supports GET, so we use fetch + ReadableStream and
 * parse the SSE frames manually. The signal lets the caller cancel
 * mid-stream (e.g. component unmount).
 */
export async function* planBuildStream(
  input: string,
  targetGoal: TargetGoal = "mapping_and_boss",
  signal?: AbortSignal,
): AsyncGenerator<PricingProgress, void, void> {
  yield* streamPlanEndpoint("/fob/plan/stream", input, targetGoal, signal);
}

/**
 * POST /fob/plan/reverse/stream — SSE-streamed reverse-progression planning.
 *
 * Identical event lifecycle to planBuildStream, but the final 'done'
 * event's BuildPlan carries per-item ladder rationales tagged
 * [target_name] in the appropriate stages' gem_changes (Step 13.C).
 */
export async function* planBuildReverseStream(
  input: string,
  targetGoal: TargetGoal = "mapping_and_boss",
  signal?: AbortSignal,
): AsyncGenerator<PricingProgress, void, void> {
  yield* streamPlanEndpoint(
    "/fob/plan/reverse/stream",
    input,
    targetGoal,
    signal,
  );
}

// ---------------------------------------------------------------------------
// Step 14 — per-stage progressions (Pohx-style stage builds)
// ---------------------------------------------------------------------------

/** GET /fob/tree-progression/{template_name} — null when no progression exists. */
export async function fetchTreeProgression(
  templateName: string,
): Promise<TreeProgression | null> {
  return get<TreeProgression | null>(
    `/fob/tree-progression/${encodeURIComponent(templateName)}`,
  );
}

/** GET /fob/gear-progression/{template_name} — null when no progression exists. */
export async function fetchGearProgression(
  templateName: string,
): Promise<GearProgression | null> {
  return get<GearProgression | null>(
    `/fob/gear-progression/${encodeURIComponent(templateName)}`,
  );
}

/** GET /fob/gem-progression/{template_name} — null when no progression exists. */
export async function fetchGemProgression(
  templateName: string,
): Promise<GemProgression | null> {
  return get<GemProgression | null>(
    `/fob/gem-progression/${encodeURIComponent(templateName)}`,
  );
}

/**
 * POST /fob/stage-export — PoB-importable code for one stage.
 *
 * Use this variant when you can supply the user's original PoB code:
 * the server preserves the user's actual tree when the matched template
 * has no curated TreeProgression registered (47 of 49 templates as of
 * Step 14 T5). Always returns a non-null ``code``.
 */
export async function fetchStageExport(
  templateName: string,
  stageKey: string,
  characterClass: string,
  ascendancy: string | null,
  userPobCode: string | null,
  level = 90,
): Promise<StageExportResponse> {
  const body: StageExportRequest = {
    template_name: templateName,
    stage_key: stageKey,
    character_class: characterClass,
    ascendancy,
    level,
    user_pob_code: userPobCode,
  };
  return post<StageExportResponse>("/fob/stage-export", body);
}

/**
 * Shared SSE consumer for /fob/plan/stream and /fob/plan/reverse/stream.
 *
 * fetch + ReadableStream because EventSource only supports GET. The
 * signal lets the caller cancel mid-stream (e.g. component unmount).
 */
async function* streamPlanEndpoint(
  path: string,
  input: string,
  targetGoal: TargetGoal,
  signal?: AbortSignal,
): AsyncGenerator<PricingProgress, void, void> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ input, target_goal: targetGoal }),
    signal,
  });
  if (!res.ok) {
    const err: ApiError = (await res.json().catch(() => ({
      detail: res.statusText,
    }))) as ApiError;
    throw new Error(err.detail ?? `HTTP ${res.status}`);
  }
  if (!res.body) {
    throw new Error("response has no body");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE frames are separated by a blank line ("\n\n"). Each frame may
    // contain multiple "data: ..." lines that the spec says to join with
    // "\n", but our server emits one "data:" per event so we only need
    // to handle the simple case.
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const dataLines = frame
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trimStart());
      if (dataLines.length === 0) continue;
      const payload = dataLines.join("\n");
      try {
        yield JSON.parse(payload) as PricingProgress;
      } catch {
        // Drop malformed frames silently — the next 'done' event still arrives.
      }
    }
  }
}
