/**
 * useViewTransition — a thin, safe wrapper around the browser's
 * View Transitions API.
 *
 * `withViewTransition(cb)` runs `cb` (a DOM-mutating update — usually a
 * React Router navigation or a `setState`) inside
 * `document.startViewTransition`, so the browser cross-fades the old
 * and new visual states.
 *
 * Progressive enhancement — the call is a no-op wrapper when:
 *  - the API is unavailable (Firefox < 130, Safari < 18), or
 *  - the user has `prefers-reduced-motion: reduce` set.
 * In both cases `cb` runs immediately and the existing CSS `.vs-route`
 * fade (Step 34) still covers route changes.
 *
 * The always-animating `<ParticleCanvas>` is excluded from the root
 * snapshot by giving it its own `view-transition-name` (set in the
 * component) — `index.css` then suppresses animation on that group so
 * it never produces the stuttering frozen frame the Step 34 attempt hit.
 */

import { flushSync } from "react-dom";

interface ViewTransition {
  finished: Promise<void>;
  ready: Promise<void>;
  updateCallbackDone: Promise<void>;
  skipTransition: () => void;
}

type DocumentWithViewTransition = Document & {
  startViewTransition?: (callback: () => void | Promise<void>) => ViewTransition;
};

/** True when the browser exposes the View Transitions API. */
export function supportsViewTransitions(): boolean {
  return (
    typeof document !== "undefined" &&
    typeof (document as DocumentWithViewTransition).startViewTransition ===
      "function"
  );
}

function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Run `cb` inside a view transition when possible; otherwise run it
 * directly. `cb` is wrapped in `flushSync` so the React update it
 * triggers is committed synchronously and captured by the transition
 * snapshot.
 */
export function withViewTransition(cb: () => void): void {
  if (!supportsViewTransitions() || prefersReducedMotion()) {
    cb();
    return;
  }
  const doc = document as DocumentWithViewTransition;
  doc.startViewTransition?.(() => {
    flushSync(cb);
  });
}
