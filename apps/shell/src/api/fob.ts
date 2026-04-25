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
  RecommendResponse,
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
