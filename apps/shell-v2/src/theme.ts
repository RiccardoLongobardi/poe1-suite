/**
 * "Obsidian Pro" — FOB v2 design system (UI PRO MAX initiative).
 *
 * Evolution of v1's "Void Stone & Ember": the ember-gold identity stays
 * (it's the brand, and it reads PoE), but the warm brown/parchment base
 * is replaced by a cool, near-black obsidian slate — the look of a
 * modern professional tool (poe.ninja / Maxroll class) rather than a
 * themed page. Chrome moves from a side rail to a sticky top navbar.
 *
 * Colour ramps (10 shades, Mantine convention):
 * - ember: primary accent, unchanged hue from v1. Shade 6 = actions.
 * - blood: secondary accent — errors, rare-tier.
 * - dark:  the obsidian surface/text ramp (cool slate, not warm brown).
 *          Overriding Mantine's built-in `dark` tuple auto-themes most
 *          components without per-component CSS.
 *
 * Typography:
 * - Headings / UI emphasis: Space Grotesk.
 * - Body: Inter.
 * - Brand wordmark only: Cinzel (heritage from v1 — nowhere else).
 * - Stat values / numbers: Geist Mono.
 *
 * Interactive states (hover glow, focus ring, card borders) live in
 * `index.css` — Mantine v7's `styles` prop takes flat CSS properties
 * only, no nested selectors.
 */

import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Ember gold — primary action colour. Shade 6 is `color="ember"`.
const ember: MantineColorsTuple = [
  "#fdf6e7", // 0
  "#f9e9c5", // 1
  "#f2d391", // 2
  "#ecbc5d", // 3
  "#e6a832", // 4
  "#dd9a22", // 5
  "#cf8f1f", // 6 ← primary action
  "#ad7619", // 7
  "#8c5e13", // 8
  "#6b470d", // 9
];

// Blood — errors, warnings, rare-tier accents.
const blood: MantineColorsTuple = [
  "#fde9e9", // 0
  "#f6c9c9", // 1
  "#ea9a9a", // 2
  "#dd6a6a", // 3
  "#d04242", // 4
  "#b62b2b", // 5
  "#9a1e1e", // 6 ← secondary accent
  "#7d1616", // 7
  "#611010", // 8
  "#470b0b", // 9
];

// Obsidian surface / text ramp — cool slate. Index 0 = lightest
// (primary text), 9 = darkest. Mantine maps: text 0-2, borders ~4,
// surfaces 5-6, body 7.
const dark: MantineColorsTuple = [
  "#e8ecf2", // 0 ← primary text (cool white)
  "#c2c9d4", // 1
  "#8e98a8", // 2 ← dimmed text
  "#5a6372", // 3 ← faint text
  "#262c36", // 4 ← borders
  "#181c23", // 5 ← elevated surface
  "#12151a", // 6 ← card / input surface
  "#0b0d10", // 7 ← body background
  "#08090c", // 8
  "#060708", // 9
];

export const fobTheme = createTheme({
  primaryColor: "ember",
  primaryShade: { light: 6, dark: 6 },
  colors: { ember, blood, dark },
  defaultRadius: "md",

  // Ember gold is a light-ish accent — let Mantine pick dark text on
  // filled ember surfaces and light text on the obsidian surfaces.
  autoContrast: true,
  luminanceThreshold: 0.3,

  black: "#0b0d10",
  white: "#e8ecf2",

  fontFamily:
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontFamilyMonospace: "'Geist Mono', 'Fira Code', 'Cascadia Code', monospace",
  headings: {
    fontFamily: "'Space Grotesk', 'Inter', -apple-system, sans-serif",
    fontWeight: "600",
  },

  components: {
    Card: {
      defaultProps: {
        withBorder: true,
        radius: "md",
      },
    },
    Button: {
      defaultProps: {
        radius: "md",
      },
    },
  },
});

/** PayPal donation link — surfaced in the modal triggered from HomePage. */
export const PAYPAL_URL = "https://paypal.me/riclong";
