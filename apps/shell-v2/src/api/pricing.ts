/**
 * Typed client for the /pricing endpoints (poe.ninja economy data).
 */

import type { ApiError } from "./types";

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

/** A normalised price point from `GET /pricing/quote`. */
export interface PriceQuote {
  name: string;
  base_type: string | null;
  chaos_value: number;
  divine_value: number | null;
  exalted_value: number | null;
  low_confidence: boolean;
}

/** Envelope of `GET /pricing/quote`. */
export interface QuoteResponse {
  league: string;
  queried_at: string;
  /** Null when poe.ninja has no price for the queried name. */
  quote: PriceQuote | null;
}

/**
 * GET /pricing/quote?name=... — look up a single item's poe.ninja
 * price by name. Resolves uniques + currency; a rare's rolled name
 * returns `quote: null` (poe.ninja doesn't price rolled rares).
 */
export async function getQuote(name: string): Promise<QuoteResponse> {
  return get<QuoteResponse>(`/pricing/quote?name=${encodeURIComponent(name)}`);
}
