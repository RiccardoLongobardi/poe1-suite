/**
 * Astral PoE-themed Mantine theme for FOB.
 *
 * The palette evokes the Atlas of Worlds passive tree: deep purples,
 * astral violet glow, gold accents for loot/priority highlights. The
 * star-field gradient lives in the body background (set in index.css);
 * components stay readable against the dark base.
 *
 * Custom colour ramps (10 shades each, Mantine convention):
 * - astral: the primary purple. shade 6 is the action colour.
 * - gold:   accent for priority numbers, "buy first" badges, donation CTA.
 *
 * Typography:
 * - Body: Inter (system fallback) — readable at small sizes.
 * - Titles: optional Cinzel (only loaded if user-installed); falls
 *   back to a serif stack so we don't hard-depend on web-fonts.
 */

import { createTheme, type MantineColorsTuple } from "@mantine/core";

// Astral violet — primary brand colour. Shade 6 is the default
// `color="astral"` used by buttons / active nav / focus rings.
const astral: MantineColorsTuple = [
  "#f3eeff", // 0
  "#e3d6ff", // 1
  "#c5aaff", // 2
  "#a37bff", // 3
  "#8753ff", // 4
  "#7536ff", // 5
  "#6e26ff", // 6 ← primary
  "#5d18e3", // 7
  "#5212cc", // 8
  "#4509b3", // 9
];

// Gold — used for priority badges and the donation CTA.
const gold: MantineColorsTuple = [
  "#fff8e1",
  "#ffefb5",
  "#ffe585",
  "#ffdb55",
  "#ffd232",
  "#ffca1d",
  "#ffc40f",
  "#e3ac00",
  "#ca9700",
  "#ad7f00",
];

export const fobTheme = createTheme({
  primaryColor: "astral",
  primaryShade: { light: 6, dark: 5 },
  colors: { astral, gold },
  defaultRadius: "md",
  fontFamily:
    "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  headings: {
    fontFamily:
      "'Cinzel', 'Marcellus', 'Cormorant Garamond', Georgia, serif",
    fontWeight: "600",
  },
  components: {
    Card: {
      defaultProps: {
        withBorder: true,
        radius: "md",
        shadow: "sm",
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
