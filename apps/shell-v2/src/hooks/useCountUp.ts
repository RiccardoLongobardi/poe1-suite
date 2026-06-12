/**
 * useCountUp — animate a number from its previous value up to `target`.
 *
 * Used for the Analyze key-stat tiles so Life / DPS / EHP / … count up
 * when the dashboard first renders. `requestAnimationFrame`-driven,
 * linear easing.
 *
 * - Animates on mount (0 → target) and again whenever `target` changes
 *   (current → new target) — but not on plain re-renders.
 * - `prefers-reduced-motion`: returns `target` immediately, no anim.
 */

import { useEffect, useRef, useState } from "react";

export function useCountUp(target: number, duration = 800): number {
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const [value, setValue] = useState(reduced ? target : 0);
  // Latest displayed value, read without re-triggering the effect.
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (reduced) {
      setValue(target);
      return;
    }
    const from = valueRef.current;
    const start = performance.now();
    let raf = 0;
    const tick = (now: number): void => {
      const t = Math.min(1, (now - start) / duration);
      setValue(Math.round(from + (target - from) * t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration, reduced]);

  return value;
}
