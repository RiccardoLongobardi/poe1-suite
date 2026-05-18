/**
 * ParticleCanvas — a subtle animated ember particle field behind the
 * whole app.
 *
 * A single full-viewport `position: fixed` canvas mounted once in
 * `App.tsx`. Vanilla Canvas2D — no Three.js, no library. Particles
 * drift slowly, link to nearby neighbours, and are gently pushed away
 * from the cursor.
 *
 * - Dark ("Void Stone"): ember-gold dots on void black.
 * - Light ("Parchment"): faint ink dots on cream.
 * - `prefers-reduced-motion`: nothing is drawn — the field stays blank.
 *
 * The colour scheme is re-read live via a `MutationObserver` on the
 * `<html>` `data-mantine-color-scheme` attribute.
 */

import { memo, useEffect, useRef } from "react";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

const COUNT = 72;
const LINK_DIST = 130;
const MOUSE_DIST = 80;

function isLightScheme(): boolean {
  return (
    document.documentElement.getAttribute("data-mantine-color-scheme") ===
    "light"
  );
}

export const ParticleCanvas = memo(function ParticleCanvas() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    // Reduced motion → render nothing at all.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let w = 0;
    let h = 0;
    let light = isLightScheme();
    let raf = 0;
    const particles: Particle[] = [];
    const mouse = { x: -9999, y: -9999 };

    const resize = (): void => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const seed = (): void => {
      particles.length = 0;
      for (let i = 0; i < COUNT; i += 1) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 0.15 + Math.random() * 0.15;
        particles.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
        });
      }
    };

    const frame = (): void => {
      const rgb = light ? "42, 31, 14" : "200, 147, 42";
      const dotAlpha = light ? 0.34 : 0.4;
      const lineAlpha = light ? 0.16 : 0.13;

      ctx.clearRect(0, 0, w, h);

      for (const p of particles) {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > w) p.vx *= -1;
        if (p.y < 0 || p.y > h) p.vy *= -1;
        // Gentle cursor repulsion.
        const dx = p.x - mouse.x;
        const dy = p.y - mouse.y;
        const d = Math.hypot(dx, dy);
        if (d > 0 && d < MOUSE_DIST) {
          const push = ((MOUSE_DIST - d) / MOUSE_DIST) * 1.5;
          p.x += (dx / d) * push;
          p.y += (dy / d) * push;
        }
      }

      // Connection lines — fade with distance.
      ctx.strokeStyle = `rgba(${rgb}, ${lineAlpha})`;
      ctx.lineWidth = 1;
      for (let i = 0; i < particles.length; i += 1) {
        for (let j = i + 1; j < particles.length; j += 1) {
          const a = particles[i];
          const b = particles[j];
          const dist = Math.hypot(a.x - b.x, a.y - b.y);
          if (dist < LINK_DIST) {
            ctx.globalAlpha = 1 - dist / LINK_DIST;
            ctx.beginPath();
            ctx.moveTo(a.x, a.y);
            ctx.lineTo(b.x, b.y);
            ctx.stroke();
          }
        }
      }
      ctx.globalAlpha = 1;

      // Dots.
      ctx.fillStyle = `rgba(${rgb}, ${dotAlpha})`;
      for (const p of particles) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.6, 0, Math.PI * 2);
        ctx.fill();
      }

      raf = requestAnimationFrame(frame);
    };

    const onMove = (e: MouseEvent): void => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
    };
    const onLeave = (): void => {
      mouse.x = -9999;
      mouse.y = -9999;
    };

    resize();
    seed();
    frame();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseout", onLeave);

    // Re-read the colour scheme without re-creating the canvas.
    const observer = new MutationObserver(() => {
      light = isLightScheme();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-mantine-color-scheme"],
    });

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseout", onLeave);
      observer.disconnect();
    };
  }, []);

  return (
    <canvas
      ref={ref}
      aria-hidden="true"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
      }}
    />
  );
});
