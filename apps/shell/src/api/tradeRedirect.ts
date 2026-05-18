/**
 * Client-side Trade redirect helper.
 *
 * `openTradeSearch` opens a **prefilled** GGG Trade search via GGG's
 * browser-navigation redirect endpoint:
 *
 *   GET /api/trade/search/<league>?redirect&source=<url-encoded JSON>
 *
 * Opened with `window.open` (a top-level navigation, NOT a `fetch`),
 * GGG runs the POST search on its own infrastructure and 302s the tab
 * to the fully prefilled `/trade/search/<league>/<id>` results page.
 * Because it is a navigation and not an XHR, CORS does not apply and
 * no FOB backend involvement is needed — this is how poe.ninja and
 * similar tools open prefilled searches.
 *
 * (A *server-side* POST to `/api/trade/search` is still blocked with
 * HTTP 403 from Render's datacenter IP range — so that route stays
 * dead. The `?redirect&source=` navigation sidesteps it entirely
 * because the request originates from the user's own browser.)
 *
 * Fallback: when the active league has not resolved yet (Render cold
 * start) the redirect can't be built, so `openTradeSearch` degrades
 * to the bare league search page + a clipboard copy of the search
 * term, and shows a toast. The league name (e.g. "Mirage") is
 * prefetched from `/health` on app mount so this fallback is rare.
 */

import { notifications } from "@mantine/notifications";

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

/**
 * Returns the resolved league synchronously, or `null` when the
 * `/health` probe hasn't settled yet.
 *
 * Unlike :func:`getLeague` this does NOT substitute a fallback —
 * callers that need a *correct* league (the prefilled Trade redirect)
 * must not point the user at the wrong league's trade site.
 */
export function getResolvedLeague(): string | null {
  return cachedLeague;
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

/** The UI language picked by the i18n `LangProvider`. Read straight
 * from `localStorage` because this module is not a React component. */
function uiLang(): "it" | "en" {
  try {
    return localStorage.getItem("fob_lang") === "en" ? "en" : "it";
  } catch {
    return "it";
  }
}

/** A GGG Trade JSON query payload. */
interface TradeQueryPayload {
  query: Record<string, unknown>;
  sort: Record<string, unknown>;
}

/**
 * Build the GGG Trade JSON query for an item.
 *
 * * Unique → `name` (the unique's name) + `type` (its base type, when
 *   known) for the tightest match.
 * * Rare / magic / normal → `type` only. A rare's roll-generated name
 *   returns nothing on Trade; the base type is the searchable handle.
 *
 * `stats` is always present as a single empty `and` group — Trade
 * accepts an empty filter array.
 */
function buildTradeQuery(item: TradeRedirectItem): TradeQueryPayload {
  const isUnique = (item.rarity ?? "").toLowerCase() === "unique";
  const base = item.base_type?.trim();
  const name = item.name?.trim();
  const query: Record<string, unknown> = {
    status: { option: "online" },
    stats: [{ type: "and", filters: [] }],
  };
  if (isUnique) {
    if (name) query.name = name;
    if (base) query.type = base;
  } else if (base) {
    query.type = base;
  }
  return { query, sort: { price: "asc" } };
}

/**
 * Fallback path: open the bare league search page and pre-copy the
 * search term to the clipboard. Used when the active league hasn't
 * resolved yet or the item carries nothing searchable.
 */
function openTradeFallback(item: TradeRedirectItem): void {
  try {
    void navigator.clipboard.writeText(tradeClipboardText(item));
  } catch {
    // Insecure context or denied — skip; the user can still type the
    // term manually on Trade.
  }
  const url = `https://www.pathofexile.com/trade/search/${encodeURIComponent(getLeague())}`;
  window.open(url, "_blank", "noopener,noreferrer");
}

/**
 * Open a **prefilled** GGG Trade search for an item in a new tab.
 *
 * Uses GGG's browser-navigation redirect endpoint:
 *
 *   GET /api/trade/search/<league>?redirect&source=<url-encoded JSON>
 *
 * Opened via `window.open` — NOT `fetch`. The redirect only works as a
 * top-level browser navigation: GGG runs the POST search server-side
 * and issues a 302 to the prefilled `/trade/search/<league>/<id>`
 * results page. A `fetch` would be blocked by CORS; a navigation is
 * not. This is how poe.ninja and other tools open prefilled searches.
 *
 * Synchronous so it stays inside the user-gesture window (popup
 * blockers stay quiet).
 *
 * Degrades to :func:`openTradeFallback` (bare page + clipboard) when
 * the active league hasn't resolved yet (Render cold start) or the
 * item has no searchable name/base — and shows a toast in the
 * league-missing case so the user knows to retry.
 */
export function openTradeSearch(item: TradeRedirectItem): void {
  const league = getResolvedLeague();
  const built = buildTradeQuery(item);
  const hasFilter = !!built.query.name || !!built.query.type;

  if (!league || !hasFilter) {
    openTradeFallback(item);
    if (!league) {
      const l = uiLang();
      notifications.show({
        color: "yellow",
        title: l === "en" ? "League not ready" : "Lega non ancora pronta",
        message:
          l === "en"
            ? "Opened a generic Trade search — the active league is still loading. Try again in a moment for a prefilled search."
            : "Aperta una ricerca Trade generica — la lega attiva si sta ancora caricando. Riprova tra un istante per una ricerca pre-compilata.",
      });
    }
    return;
  }

  const encoded = encodeURIComponent(JSON.stringify(built));
  const url = `https://www.pathofexile.com/api/trade/search/${encodeURIComponent(
    league,
  )}?redirect&source=${encoded}`;
  window.open(url, "_blank", "noopener,noreferrer");
}
