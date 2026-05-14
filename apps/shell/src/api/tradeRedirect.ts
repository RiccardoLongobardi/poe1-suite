/**
 * Client-side Trade redirect helper.
 *
 * Two flow variants:
 *
 * 1. ``openTradeForItem`` (the common one) — asks the server via
 *    ``POST /fob/trade-url`` for a pre-filled GGG Trade search URL,
 *    then opens it. The server caches the URL by query hash (TTL ~8
 *    min) so common items (Mageblood, Kaom's Heart, ...) usually
 *    return in under 100 ms — fast enough that the browser keeps the
 *    user-gesture window open and the popup blocker stays quiet.
 *
 * 2. Fallback — if the server is rate-limited by GGG (429), or the
 *    network call fails, we open the bare ``/trade/search/<league>``
 *    page and rely on the clipboard-copied item name so the user can
 *    paste-and-search manually in one move.
 *
 * The league name (e.g. "Mirage") is prefetched from ``/health`` on
 * app mount so the redirect stays synchronous on first click.
 */

import { notifications } from "@mantine/notifications";
import { fetchTradeUrl } from "./fob";

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
  /** "unique", "rare", "magic", "normal" — drives name-vs-type routing. */
  rarity?: string | null;
  base_type?: string | null;
  mods?: string[];
}

/**
 * Open a pre-filled GGG Trade search for ``item`` in a new tab.
 *
 * Best-effort flow:
 * 1. Copy the item name to the clipboard (paste-and-search fallback).
 * 2. Ask /fob/trade-url for a pre-filled URL with the right query.
 * 3. Open it. If the popup blocker rejects (rare on cache hit), surface
 *    a Mantine notification with a clickable "Apri" link instead of
 *    silently doing nothing.
 * 4. On server error or rate-limit, fall back to the bare trade page.
 */
export async function openTradeForItem(item: TradeRedirectItem): Promise<void> {
  // 1. Clipboard fallback — done synchronously, no await needed for the
  //    immediate effect. The promise is fire-and-forget.
  try {
    void navigator.clipboard.writeText(item.name);
  } catch {
    // Non-secure context or denied permission. Ignore.
  }

  // 2. Build the request payload. Uniques → search by name; everything
  //    else → search by base type + extracted mods.
  const isUnique = (item.rarity ?? "").toLowerCase() === "unique";
  const payload = {
    item_name: isUnique ? item.name : null,
    item_type: isUnique ? null : (item.base_type ?? null),
    mod_lines: item.mods ?? [],
  };

  let url: string | null = null;
  try {
    const resp = await fetchTradeUrl(payload);
    if (resp.url) {
      url = resp.url;
    }
  } catch {
    // Network error or 5xx — fall through to bare URL.
  }

  // 3. Fallback URL when /fob/trade-url didn't yield one.
  const league = getLeague();
  const bareUrl = `https://www.pathofexile.com/trade/search/${encodeURIComponent(league)}`;
  const target = url ?? bareUrl;

  // 4. Try to open. Within the user-gesture window (transient
  //    activation, ~3-5 s in modern browsers), this should succeed
  //    even after the await. If GGG was slow and the activation
  //    expired, fall back to a notification with a clickable link.
  const tab = window.open(target, "_blank", "noopener,noreferrer");
  if (!tab) {
    notifications.show({
      title: "Apri ricerca Trade",
      message: url
        ? "Il browser ha bloccato l'apertura automatica. Clicca per aprire la ricerca pre-filtrata."
        : "Apri pathofexile.com/trade — il nome è già copiato negli appunti.",
      color: "astral",
      autoClose: 8000,
      withCloseButton: true,
      onClick: () => {
        window.open(target, "_blank", "noopener,noreferrer");
      },
      styles: { root: { cursor: "pointer" } },
    });
  }
}
