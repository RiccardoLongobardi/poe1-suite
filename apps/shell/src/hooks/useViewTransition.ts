/**
 * useViewTransition — route navigation wrapped in the View Transitions
 * API for a cinematic cross-fade between pages.
 *
 * `document.startViewTransition` is supported in all evergreen browsers
 * (Chrome 111+, Firefox 130+, Safari 18.2+). Used as progressive
 * enhancement: when the API is unavailable the navigation is an instant
 * swap. The transition animation itself lives in `index.css`
 * (`::view-transition-*`), so `prefers-reduced-motion` suppression
 * costs zero JS.
 */

import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

type DocWithVT = Document & {
  startViewTransition?: (callback: () => void) => unknown;
};

export function useViewTransition(): (to: string) => void {
  const navigate = useNavigate();
  return useCallback(
    (to: string) => {
      const doc = document as DocWithVT;
      if (typeof doc.startViewTransition === "function") {
        doc.startViewTransition(() => navigate(to));
      } else {
        navigate(to);
      }
    },
    [navigate],
  );
}
