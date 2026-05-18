/**
 * Trade redirect helper.
 *
 * `openTradeUrl` opens a **prefilled** GGG Trade search in a new tab
 * from a `TradeUrlRequest` (built by the Trade-search dialog).
 *
 * The prefill needs a `search_id` minted by a POST to GGG's
 * `/api/trade/search/<league>`. The browser cannot do that POST
 * (CORS), and navigating straight to GGG's `/api/` endpoint is
 * Cloudflare-blocked. So our backend does the POST (`POST
 * /fob/trade-url`, rate-limited + ~8 min cached) and returns the
 * finished `/trade/search/<league>/<id>` URL.
 *
 * To keep the new tab inside the click's user-gesture window (popup
 * blocker quiet) we open a blank tab synchronously, then navigate it
 * once the backend round-trip completes. On backend error / GGG 429
 * the tab falls back to the bare league search page.
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

/** Returns the cached league, or the fallback when /health is pending. */
export function getLeague(): string {
  return cachedLeague ?? FALLBACK_LEAGUE;
}

/**
 * Open a **prefilled** GGG Trade search for `req` in a new tab.
 *
 * Opens a blank tab synchronously (popup-blocker-safe), asks the
 * backend for the prefilled URL, then navigates the tab to it. Falls
 * back to the bare league search page on backend error or GGG 429.
 *
 * MUST be called from inside a user-gesture handler (click).
 */
export function openTradeUrl(req: TradeUrlRequest): void {
  // Open the tab now, inside the gesture. NOT `noopener` — that makes
  // window.open return null; we null the opener manually instead.
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

  void (async () => {
    try {
      const { url } = await fetchTradeUrl(req);
      navigate(url ?? bareUrl);
    } catch {
      navigate(bareUrl);
    }
  })();
}
