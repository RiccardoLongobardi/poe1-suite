/**
 * WarmupOverlay — full-viewport cold-start overlay (Step 21).
 *
 * Shown only when the backend is cold (Render free-tier ~30 s spin-up,
 * detected by `useServerWarmup`). The loading indicator is a
 * hand-authored inline SVG of a Path of Exile 1 Divine Orb — a golden
 * sphere with a classical female face in bas-relief. No external image,
 * no animation library: pure CSS keyframes (see index.css), all of
 * which are disabled under `prefers-reduced-motion`.
 */

import { useEffect, useState } from "react";
import { useServerWarmup } from "../hooks/useServerWarmup";
import { useT } from "../i18n";

/** The Divine Orb itself — self-contained inline SVG, crisp at 120px. */
function DivineOrb() {
  // 14 ornamental studs evenly placed around the outer ring.
  const studs = Array.from({ length: 14 }, (_, i) => {
    const angle = (i / 14) * Math.PI * 2 - Math.PI / 2;
    const r = 54;
    return {
      cx: 60 + r * Math.cos(angle),
      cy: 60 + r * Math.sin(angle),
    };
  });

  return (
    <svg
      className="warmup-orb"
      width={120}
      height={120}
      viewBox="0 0 120 120"
      role="img"
      aria-label="Divine Orb"
    >
      <defs>
        <radialGradient id="orbBody" cx="38%" cy="34%" r="72%">
          <stop offset="0%" stopColor="#f4d36a" />
          <stop offset="42%" stopColor="#d4a520" />
          <stop offset="78%" stopColor="#a06e16" />
          <stop offset="100%" stopColor="#7a4e10" />
        </radialGradient>
        <radialGradient id="orbFace" cx="42%" cy="32%" r="80%">
          <stop offset="0%" stopColor="#f0c860" />
          <stop offset="100%" stopColor="#9c6e1c" />
        </radialGradient>
      </defs>

      {/* Outer ring — near-black bronze. */}
      <circle cx={60} cy={60} r={58} fill="#1a1008" stroke="#3a2608" strokeWidth={2} />

      {/* Ornamental studs around the circumference. */}
      {studs.map((s, i) => (
        <circle key={i} cx={s.cx} cy={s.cy} r={2.6} fill="#c89a32" opacity={0.85} />
      ))}

      {/* Main sphere. */}
      <circle cx={60} cy={60} r={48} fill="url(#orbBody)" />
      <circle
        cx={60}
        cy={60}
        r={48}
        fill="none"
        stroke="#5a3608"
        strokeWidth={1.5}
        opacity={0.6}
      />

      {/* Classical female face in bas-relief. */}
      <g>
        {/* Hair framing the face. */}
        <path
          d="M40 44 q-6 18 2 36 q-10 -6 -11 -24 q-1 -16 9 -12 Z"
          fill="#7a4e10"
          opacity={0.55}
        />
        <path
          d="M80 44 q6 18 -2 36 q10 -6 11 -24 q1 -16 -9 -12 Z"
          fill="#7a4e10"
          opacity={0.55}
        />
        {/* Face oval. */}
        <ellipse cx={60} cy={63} rx={20} ry={26} fill="url(#orbFace)" />
        {/* Brow + cheekbone shadow. */}
        <path
          d="M46 54 q14 -9 28 0"
          fill="none"
          stroke="#5a3608"
          strokeWidth={1.4}
          opacity={0.5}
        />
        {/* Closed eyes — serene, downcast. */}
        <path
          d="M49 60 q5 4 10 0"
          fill="none"
          stroke="#4a2c06"
          strokeWidth={1.6}
          strokeLinecap="round"
        />
        <path
          d="M61 60 q5 4 10 0"
          fill="none"
          stroke="#4a2c06"
          strokeWidth={1.6}
          strokeLinecap="round"
        />
        {/* Nose bridge. */}
        <path
          d="M60 62 l-2 12 q2 3 4 0"
          fill="none"
          stroke="#5a3608"
          strokeWidth={1.3}
          opacity={0.65}
          strokeLinecap="round"
        />
        {/* Lips. */}
        <path
          d="M53 81 q7 5 14 0"
          fill="none"
          stroke="#4a2c06"
          strokeWidth={1.8}
          strokeLinecap="round"
        />
        {/* Cheek highlights. */}
        <ellipse cx={50} cy={70} rx={4} ry={6} fill="#f4d878" opacity={0.25} />
        <ellipse cx={70} cy={70} rx={4} ry={6} fill="#f4d878" opacity={0.25} />
      </g>

      {/* Top-left specular highlight. */}
      <ellipse
        cx={44}
        cy={40}
        rx={14}
        ry={9}
        fill="rgba(255,230,120,0.35)"
        transform="rotate(-32 44 40)"
      />

      {/* Orbiting arc of light — rotates via CSS. */}
      <circle
        className="warmup-orb-ring"
        cx={60}
        cy={60}
        r={53}
        fill="none"
        stroke="#ffe27a"
        strokeWidth={2.4}
        strokeLinecap="round"
        strokeDasharray="40 293"
        opacity={0.8}
      />
    </svg>
  );
}

export function WarmupOverlay() {
  const t = useT();
  const state = useServerWarmup();
  // `render` keeps the overlay mounted through the fade-out; `fading`
  // triggers the opacity transition once the backend is warm.
  const [render, setRender] = useState(false);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (state === "cold") {
      setRender(true);
      setFading(false);
    } else if (state === "warm" && render) {
      setFading(true);
      const timer = window.setTimeout(() => setRender(false), 600);
      return () => window.clearTimeout(timer);
    }
  }, [state, render]);

  if (!render) return null;

  return (
    <div
      className={fading ? "warmup-overlay warmup-overlay--fading" : "warmup-overlay"}
      role="status"
      aria-live="polite"
    >
      <div className="warmup-orb-wrap">
        <DivineOrb />
      </div>
      <p className="warmup-title">{t({ it: "Il server si sta risvegliando...", en: "The server is waking up..." })}</p>
      <p className="warmup-subtitle">{t({ it: "Render free tier — attendi qualche secondo", en: "Render free tier — hold on a few seconds" })}</p>
    </div>
  );
}
