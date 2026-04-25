/**
 * Typed API functions for the /builds endpoints.
 */

import type { ApiError } from "./types";

const BASE = ""; // same origin; vite.config.ts proxies /builds → 8765

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

interface BuildDetailResponse {
  league: string;
  queried_at: string;
  build: {
    pathOfBuildingExport: string;
    [key: string]: unknown;
  };
}

/**
 * GET /builds/detail?account=...&name=...
 * Returns only the pathOfBuildingExport string (the raw PoB code).
 */
export async function getDetail(
  account: string,
  name: string,
): Promise<string> {
  const params = new URLSearchParams({ account, name });
  const data = await get<BuildDetailResponse>(
    `/builds/detail?${params.toString()}`,
  );
  return data.build.pathOfBuildingExport;
}
