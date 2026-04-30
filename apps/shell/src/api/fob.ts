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
  PlanResponse,
  PricingProgress,
  RecommendResponse,
  TargetGoal,
  TradeModExtractResponse,
  TradeSearchRequest,
  TradeSearchResponse,
} from "./types";

const BASE = ""; // same origin; vite.config.ts proxies /fob → 8765

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

/** POST /fob/analyze-pob */
export async function analyzePob(input: string): Promise<AnalyzePobResponse> {
  return post<AnalyzePobResponse>("/fob/analyze-pob", { input });
}

/**
 * POST /fob/extract-trade-mods — turn raw mod text into dialog rows.
 *
 * Pure server-side pattern matching (no HTTP / no rate-limit). Used
 * by ``TradeSearchDialog`` to populate its mod-toggle list when the
 * caller has the original mod text but no pre-extracted rows.
 */
export async function extractTradeMods(
  mods: string[],
): Promise<TradeModExtractResponse> {
  return post<TradeModExtractResponse>("/fob/extract-trade-mods", { mods });
}

/**
 * POST /fob/trade-search — build a pre-filled GGG Trade share URL.
 *
 * Mirrors poe.ninja's character trade search: feed a focused mod
 * selection (plus optional name/type/links), get back the URL the user
 * can open on pathofexile.com to inspect / negotiate / buy.
 */
export async function tradeSearch(
  req: TradeSearchRequest,
): Promise<TradeSearchResponse> {
  return post<TradeSearchResponse>("/fob/trade-search", req);
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
  const res = await fetch(`${BASE}/fob/plan/stream`, {
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
