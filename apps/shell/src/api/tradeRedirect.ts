/**
 * Client-side Trade redirect helper.
 *
 * `openTradeSearch` opens a **prefilled** GGG Trade search for an item
 * in a new tab.
 *
 * How it works — the prefill genuinely requires a `search_id` minted
 * by a POST to GGG's `/api/trade/search/<league>`:
 *
 *  - The browser cannot do that POST itself (CORS — the trade API
 *    sends no `Access-Control-Allow-Origin`, and a JSON body triggers
 *    a preflight GGG never answers).
 *  - Navigating the browser straight to GGG's `/api/...?redirect`
 *    endpoint is rejected by Cloudflare with
 *    `{"error":{"code":6,"message":"Forbidden"}}` — that GET-prefill
 *    mechanism does not exist (tried + QA-failed in Steps 28/29).
 *  - So the POST is done by **our backend** (`POST /fob/trade-url`,
 *    re-verified working from Render against GGG on 2026-05-18 — the
 *    2026-05-14 "Render IP blocked" note is stale). The backend
 *    rate-limits + caches (~8 min TTL) and returns the finished
 *    `/trade/search/<league>/<id>` URL.
 *
 * To keep the new tab inside the click's user-gesture window (popup
 * blocker quiet) we open a blank tab synchronously, then navigate it
 * to the prefilled URL once the backend round-trip completes. If the
 * backend fails or GGG rate-limits, the blank tab is sent to the bare
 * league search page and the search term is copied to the clipboard.
 */

import { fetchTradeUrl } from "./fob";
import type { TradeUrlRequest } from "./types";

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

/** Default league used until /health resolves (or if it fails). */
const FALLBACK_LEAGUE = "Standard";

let cachedLeague: string | null = null;
let inflight: Promise<string> | null = null;

/**
 * Prefetch the current league from /health. Idempotent and safe to
 * call at app mount — subsequent callers reuse the cache (or the
 * in-flight promise) instead of issuing another request.
 */
export async function prefetchLeague(): Promise<string> {
  if (cachedLeague) return cachedLeague;
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const r = await fetch(`${BASE}/health`);
      const data = (await r.json()) as { league?: string };
      cachedLeague = data.league ?? FALLBACK_LEAGUE;
    } catch {
      cachedLeague = FALLBACK_LEAGUE;
    } finally {
      inflight = null;
    }
    return cachedLeague ?? FALLBACK_LEAGUE;
  })();
  return inflight;
}

/**
 * Returns the cached league synchronously, or the fallback when the
 * prefetch hasn't completed yet.
 */
export function getLeague(): string {
  return cachedLeague ?? FALLBACK_LEAGUE;
}

/** Subset of CoreItem fields the redirect helper needs. */
export interface TradeRedirectItem {
  name: string;
  /** "unique", "rare", ... — drives the name-vs-base-type choice. */
  rarity?: string | null;
  base_type?: string | null;
  mods?: string[];
}

/**
 * Pick the most useful string to drop on the clipboard for a Trade
 * search — used only on the fallback path (backend/GGG unavailable).
 *
 * Unique → the unique's name. Rare/magic/normal → the base type (a
 * rare's roll-generated name returns nothing on Trade).
 */
export function tradeClipboardText(item: TradeRedirectItem): string {
  const rarity = (item.rarity ?? "").toLowerCase();
  const base = item.base_type?.trim();
  if (rarity !== "unique" && base) return base;
  return item.name;
}

/** Best-effort clipboard write — silently skips on insecure context. */
function copyToClipboard(text: string): void {
  try {
    void navigator.clipboard.writeText(text);
  } catch {
    /* insecure context / denied — skip */
  }
}

/**
 * Open a **prefilled** GGG Trade search for an item in a new tab.
 *
 * Opens a blank tab synchronously (so the popup blocker stays quiet),
 * asks the backend for the prefilled URL, then navigates the tab to
 * it. Falls back to the bare league search page + a clipboard copy
 * when the backend errors or GGG rate-limits.
 */
export function openTradeSearch(item: TradeRedirectItem): void {
  // Open the tab now, inside the user gesture. NOT `noopener` — that
  // makes window.open return null and we'd lose the handle; we null
  // the opener manually instead.
  const tab = window.open("about:blank", "_blank");
  if (tab) {
    tab.opener = null;
    try {
      tab.document.title = "FOB → Trade";
      tab.document.body.style.cssText =
        "margin:0;height:100vh;display:flex;align-items:center;" +
        "justify-content:center;font-family:sans-serif;background:#0e0d09;color:#c8932a";
      tab.document.body.textContent =
        "Apertura della ricerca su pathofexile.com/trade…";
    } catch {
      /* about:blank document not writable in some browsers — ignore */
    }
  }

  const bareUrl = `https://www.pathofexile.com/trade/search/${encodeURIComponent(
    getLeague(),
  )}`;
  const navigate = (url: string): void => {
    if (tab && !tab.closed) tab.location.href = url;
    else window.open(url, "_blank", "noopener,noreferrer");
  };

  const isUnique = (item.rarity ?? "").toLowerCase() === "unique";
  const base = item.base_type?.trim() || undefined;
  const name = item.name?.trim() || undefined;
  // Unique → search by name (+ base type tightens it). Rare/magic →
  // search by base type only (the rolled name is useless).
  const req: TradeUrlRequest = isUnique
    ? { item_name: name, item_type: base }
    : { item_type: base };

  // Nothing searchable → bare page + clipboard.
  if (!req.item_name && !req.item_type) {
    copyToClipboard(tradeClipboardText(item));
    navigate(bareUrl);
    return;
  }

  void (async () => {
    try {
      const { url } = await fetchTradeUrl(req);
      if (url) {
        navigate(url);
      } else {
        // source === "rate_limited" — GGG 429. Bare page + clipboard.
        copyToClipboard(tradeClipboardText(item));
        navigate(bareUrl);
      }
    } catch {
      // Backend down / cold-start timeout — bare page + clipboard.
      copyToClipboard(tradeClipboardText(item));
      navigate(bareUrl);
    }
  })();
}
