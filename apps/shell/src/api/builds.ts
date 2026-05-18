/**
 * Typed API functions for the /builds endpoints.
 */

import type { ApiError, PopulationStats } from "./types";

// Dev: empty → same origin via Vite proxy. Production: VITE_API_BASE
// points at the deployed Fly.io backend. Trailing slashes are stripped
// to keep path concat predictable.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

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


/**
 * Parse a poe.ninja character-profile URL into its account + character
 * pair. Returns null for any URL that is not a
 * `.../character/<account>/<character>` profile link (e.g. a generic
 * build-list page, which can't be resolved to a single build).
 *
 * Live poe.ninja format (post-PoE2 migration):
 *   https://poe.ninja/builds/<league-slug>/character/<account>/<character>
 */
export function parsePoeNinjaCharacterUrl(
  url: string,
): { account: string; character: string } | null {
  const m = url.match(
    /poe\.ninja\/builds\/[^/]+\/character\/([^/?#]+)\/([^/?#]+)/i,
  );
  if (!m) return null;
  const safeDecode = (s: string): string => {
    try {
      return decodeURIComponent(s);
    } catch {
      return s;
    }
  };
  return { account: safeDecode(m[1]), character: safeDecode(m[2]) };
}

/**
 * GET /builds/population-stats?ascendancy=<name>
 *
 * Aggregated poe.ninja ladder stats (top skills + percentile
 * distributions) for the league, optionally restricted to one
 * ascendancy. Backend caches the underlying ladder fetch for 15 min
 * via the existing HttpClient diskcache layer.
 */
export async function getPopulationStats(
  ascendancy?: string | null,
): Promise<PopulationStats> {
  const params = new URLSearchParams();
  if (ascendancy) params.set("ascendancy", ascendancy);
  return get<PopulationStats>(
    `/builds/population-stats${params.toString() ? "?" + params.toString() : ""}`,
  );
}
