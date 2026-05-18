/**
 * Client-side Trade redirect helper.
 *
 * Why we open the bare /trade/search/<league> page instead of a
 * pre-filtered search URL: GGG's ``/api/trade/search/<league>`` POST
 * (the API that returns a search_id we'd embed in the URL) is blocked
 * with HTTP 403 from cloud datacenter IPs — including Render's IP
 * range where the FOB backend runs. Confirmed empirically on
 * 2026-05-14: identical request from a home/residential IP returns
 * 200 + a valid search_id, from Render it always 403s.
 *
 * The server-side endpoint ``POST /fob/trade-url`` does exist (with
 * an in-memory cache) and works fine when FOB is run locally on a
 * machine whose IP isn't blocked. Production simply can't use it.
 *
 * So the prod flow is: open the bare search page synchronously (one
 * click, no popup blocker, no white-tab UX) and copy the item name
 * to the clipboard so the user pastes-and-searches in one move.
 *
 * The league name (e.g. "Mirage") is prefetched from ``/health`` on
 * app mount so the redirect stays synchronous on first click.
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
  /** "unique", "rare", ... — kept for future use (e.g. local-dev pre-filter). */
  rarity?: string | null;
  base_type?: string | null;
  mods?: string[];
}

/**
 * Pick the most useful string to drop on the clipboard for a Trade
 * search.
 *
 * For a **unique** the name *is* the search term — paste it into the
 * Trade "Name" field. For a **rare/magic/normal** item the name is a
 * randomly-rolled string that returns nothing on Trade; what the user
 * actually wants to search is the **base type** (e.g. "Stygian Vise",
 * "Two-Toned Boots"). So we prefer ``base_type`` for non-uniques and
 * fall back to the name when the base is unknown.
 */
export function tradeClipboardText(item: TradeRedirectItem): string {
  const rarity = (item.rarity ?? "").toLowerCase();
  const base = item.base_type?.trim();
  if (rarity !== "unique" && base) return base;
  return item.name;
}

/**
 * Open the GGG Trade search page in a new tab and copy the most useful
 * search term to the clipboard so the user can paste-and-search.
 *
 * Synchronous so it stays inside the user-gesture window (popup
 * blockers stay quiet). The clipboard write is best-effort: it can
 * fail silently on insecure contexts or denied permission, but the
 * redirect still happens.
 *
 * The clipboard term is the unique name for uniques, the base type for
 * rares/magics — see :func:`tradeClipboardText`.
 *
 * Pre-filling the search itself (name / base / mods → a search_id in
 * the URL) requires calling GGG's ``/api/trade/search`` endpoint. That
 * is blocked with HTTP 403 from Render's datacenter IP range, and a
 * direct browser ``fetch`` to it fails CORS — so a true prefilled
 * Trade URL is not reachable from the deployed SPA. We open the bare
 * league search page and pre-copy the term instead. See the module
 * docstring for the full diagnosis.
 */
export function openTradeForItem(item: TradeRedirectItem): void {
  try {
    void navigator.clipboard.writeText(tradeClipboardText(item));
  } catch {
    // Non-secure context or denied — silently skip the clipboard
    // write. The user can still type the term manually on Trade.
  }
  const league = getLeague();
  const url = `https://www.pathofexile.com/trade/search/${encodeURIComponent(league)}`;
  window.open(url, "_blank", "noopener,noreferrer");
}
