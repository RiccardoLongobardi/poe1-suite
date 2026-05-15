/**
 * "Void Stone & Ember" — FOB design system (Step 22a).
 *
 * Replaces the old Atlas-violet theme. The palette references Path of
 * Exile 1's own UI: a warm near-black void, ember-gold currency-orb
 * accent, aged-parchment text, dark-blood rare accent.
 *
 * Colour ramps (10 shades, Mantine convention):
 * - ember: primary accent. Shade 6 (#c8932a) is the action colour.
 * - blood: secondary accent — rare-tier items, warnings, errors.
 * - dark:  the void/surface/text ramp. Overriding Mantine's built-in
 *          `dark` tuple auto-themes most components (body, cards,
 *          inputs, borders, text) without per-component CSS.
 *
 * Interactive states (hover/focus glow, ember card borders, the
 * parchment-noise body texture) live in `index.css` — Mantine v7's
 * `styles` prop takes flat CSS properties only, no nested selectors.
 *
 * Typography:
 * - Body / UI: Cabinet Grotesk.
 * - Headings H1/H2: Cinzel (forced via index.css; h3-h6 stay Grotesk).
 * - Stat values / numbers: Geist Mono.
 */

import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Ember gold — primary action colour. Shade 6 is `color="ember"`.
const ember: MantineColorsTuple = [
  "#fdf5e6", // 0
  "#f8e8c4", // 1
  "#f0d090", // 2
  "#e8b85c", // 3
  "#dfa030", // 4
  "#d49020", // 5
  "#c8932a", // 6 ← primary action
  "#a87820", // 7
  "#8a6018", // 8
  "#6a4810", // 9
];

// Blood — rare-tier accent, warnings, errors.
const blood: MantineColorsTuple = [
  "#fce8e8", // 0
  "#f5c8c8", // 1
  "#e89898", // 2
  "#d86868", // 3
  "#c84040", // 4
  "#a82828", // 5
  "#8b1a1a", // 6 ← secondary accent
  "#721212", // 7
  "#5a0c0c", // 8
  "#420808", // 9
];

// Void / surface / text ramp. Overriding `dark` makes Mantine's dark
// scheme paint the void background, parchment text and warm surfaces
// automatically. Index 0 = lightest (primary text), 9 = darkest.
const dark: MantineColorsTuple = [
  "#e2d5b8", // 0 ← primary text (aged parchment)
  "#c7b896", // 1
  "#9a8a6e", // 2 ← dimmed text (faded inscription)
  "#5c5040", // 3 ← faint text (stone carving)
  "#2a241c", // 4 ← borders
  "#231e17", // 5 ← elevated surface
  "#111009", // 6 ← card / input surface
  "#080604", // 7 ← body / void background
  "#070503", // 8
  "#050403", // 9
];

export const fobTheme = createTheme({
  primaryColor: "ember",
  primaryShade: { light: 6, dark: 6 },
  colors: { ember, blood, dark },
  defaultRadius: "md",

  // Ember gold is a light-ish accent — let Mantine pick dark text on
  // filled ember surfaces (buttons, badges) and light text on the dark
  // void surfaces, so contrast stays readable everywhere.
  autoContrast: true,
  luminanceThreshold: 0.3,

  black: "#080604",
  white: "#e2d5b8",

  fontFamily:
    "'Cabinet Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontFamilyMonospace: "'Geist Mono', 'Fira Code', 'Cascadia Code', monospace",
  headings: {
    // Cabinet Grotesk for h3-h6; index.css forces Cinzel on h1/h2.
    fontFamily: "'Cabinet Grotesk', -apple-system, sans-serif",
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
