/** Tailwind theme encoding the DESIGN.md tokens verbatim: colors, Inter type
 * scale, spacing (sm-xl), and rounding (sm/md/lg). All UI styling goes through
 * these tokens — never ad-hoc colors, fonts, or pixel values.
 */

import type { Config } from "tailwindcss";

import { ACCENT, BACKGROUND, PRIMARY, SECONDARY, SUCCESS, SURFACE } from "./src/lib/tokens";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: PRIMARY,
        secondary: SECONDARY,
        accent: ACCENT,
        success: SUCCESS,
        background: BACKGROUND,
        surface: SURFACE,
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      fontSize: {
        h1: "2.25rem",
        h2: "1.5rem",
        body: "1rem",
        label: "0.875rem",
      },
      spacing: {
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
        lg: "12px",
      },
    },
  },
  plugins: [],
} satisfies Config;
