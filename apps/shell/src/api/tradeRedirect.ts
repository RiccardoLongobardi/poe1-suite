/**
 * Client-side Trade redirect helper.
 *
 * The previous "let FOB call GGG Trade for you" architecture (POST
 * /fob/trade-search → returns search_id → frontend opens
 * pathofexile.com/trade/search/<league>/<id>) had two problems:
 *
 * 1. GGG enforces a strict ~5-searches-per-minute-per-IP rate limit on
 *    the trade API. Every casual user click consumed one slot. Light
 *    testing kept tripping 429s and producing "white tab" UX.
 * 2. The user gains nothing from FOB doing the search — the destination
 *    page is the same GGG trade UI either way.
 *
 * New model: the click handler just opens the bare trade page (no
 * search id, no server roundtrip) and copies the item identifier to
 * the clipboard so the user pastes-and-searches in one move. Zero
 * server load, zero rate-limit risk, and no white-tab UX.
 *
 * The league name (e.g. "Mirage") is part of the trade URL path. We
 * prefetch it from /health on app mount and cache it in module scope —
 * one network call per session, no flicker on click.
 */

const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

/** Default league used until /health resolves (or if it fails). */
const FALLBACK_LEAGUE = "Standard";

let cachedLeague: string | null = null;
let inflight: Promise<string> | null = null;

/**
 * Prefetch the current league from /health. Idempotent and safe to
 * call at app mount — subsequent callers reuse the cache (or the
 * in-flight promise) instead of issuing another request.
 *
 * Returns the league string the helper will use for redirects.
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
 * prefetch hasn't completed yet. The fallback is fine for the first
 * click after mount — Trade still loads on the wrong league page,
 * and the user can switch from there in two clicks.
 */
export function getLeague(): string {
  return cachedLeague ?? FALLBACK_LEAGUE;
}

/**
 * Open the GGG Trade search page in a new tab and copy ``itemName``
 * to the clipboard so the user can paste-and-search.
 *
 * Synchronous so it stays inside the user-gesture window (popup
 * blockers stay quiet). The clipboard write is best-effort: it can
 * fail silently on insecure contexts or when the user denied
 * permission, but the redirect still happens.
 */
export function openTradeForItem(itemName: string): void {
  try {
    void navigator.clipboard.writeText(itemName);
  } catch {
    // Non-secure context or denied — silently skip the clipboard
    // write. The user can still type the name manually on Trade.
  }
  const league = getLeague();
  const url = `https://www.pathofexile.com/trade/search/${encodeURIComponent(league)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}
