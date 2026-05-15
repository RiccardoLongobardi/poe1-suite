/**
 * useServerWarmup — detect a Render free-tier cold start.
 *
 * The backend spins down after 15 min idle; the first request after a
 * cold period takes ~30 s. This hook fires a single `/health` probe on
 * mount and reports whether the user is sitting through a cold start so
 * the app can show a reassuring overlay instead of looking broken.
 *
 * Contract:
 *   - "probing": initial state, request in flight, < 3 s elapsed.
 *   - "cold":    request still pending after 3 s → backend is warming up.
 *   - "warm":    request settled (ok, error, or non-2xx) → dismiss the
 *                overlay. We never block the user on a failed probe.
 */

import { useEffect, useState } from "react";

// Same base resolution as the api/* clients: empty in dev (Vite proxy),
// VITE_API_BASE in production.
const BASE = (import.meta.env.VITE_API_BASE ?? "").replace(/\/+$/, "");

/** A probe still pending past this mark means the backend is cold. */
const COLD_THRESHOLD_MS = 3000;

export type WarmupState = "probing" | "cold" | "warm";

export function useServerWarmup(): WarmupState {
  const [state, setState] = useState<WarmupState>("probing");

  useEffect(() => {
    let settled = false;

    const coldTimer = window.setTimeout(() => {
      // Only escalate to "cold" if the probe hasn't already come back.
      if (!settled) setState("cold");
    }, COLD_THRESHOLD_MS);

    // A failed or non-ok probe must NOT trap the user behind the
    // overlay — `.catch` swallows the error and `.finally` always
    // dismisses.
    fetch(`${BASE}/health`, { method: "GET" })
      .catch(() => null)
      .finally(() => {
        settled = true;
        window.clearTimeout(coldTimer);
        setState("warm");
      });

    return () => {
      settled = true;
      window.clearTimeout(coldTimer);
    };
  }, []);

  return state;
}
