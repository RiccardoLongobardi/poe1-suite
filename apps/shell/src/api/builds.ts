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

/**
 * One gem in a skill group, as exposed by `/builds/detail`.
 *
 * The /character endpoint speaks camelCase; we keep the alias here so
 * the React shell doesn't have to remap fields.
 */
export interface GemRef {
  name: string;
  level: number;
  quality: number;
  isBuiltInSupport?: boolean;
}

export interface SkillGroup {
  itemSlot: number;
  allGems: GemRef[];
}

interface BuildDetailResponse {
  league: string;
  queried_at: string;
  build: {
    pathOfBuildingExport: string;
    skills?: SkillGroup[];
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

/**
 * Full detail variant — also returns the skill groups so the BuildCard
 * can render the main skill + its support gems.
 *
 * Backed by the same /builds/detail endpoint as :func:`getDetail`; the
 * extra payload was already in the response, we just weren't reading
 * it. Cached at the call site.
 */
export async function getDetailFull(
  account: string,
  name: string,
): Promise<{ pobCode: string; skills: SkillGroup[] }> {
  const params = new URLSearchParams({ account, name });
  const data = await get<BuildDetailResponse>(
    `/builds/detail?${params.toString()}`,
  );
  return {
    pobCode: data.build.pathOfBuildingExport,
    skills: data.build.skills ?? [],
  };
}
