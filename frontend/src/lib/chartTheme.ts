/** Recharts theme constants derived from the DESIGN.md color tokens.
 *
 * SVG chart props need literal color strings — Tailwind classes cannot reach
 * them — so the token hexes live here (matching `tailwind.config.ts`) and every
 * derived value is computed from them. Charts use `accent` + `success` per
 * DESIGN.md; the donut's accent-tint ramp was validated with the dataviz
 * palette checker (lightness band, chroma floor, CVD separation) and ships
 * with a legend, surface gaps, and a table view as contrast relief.
 */

import { usd } from "./format";

export const ACCENT = "#2563EB";
export const SUCCESS = "#10B981";
export const PRIMARY = "#111827";
export const SECONDARY = "#4B5563";
export const SURFACE = "#FFFFFF";

/** Mix a token toward the white surface — `strength` 1 is the token itself. */
export function tint(hex: string, strength: number): string {
  const packed = parseInt(hex.slice(1), 16);
  const channels = [(packed >> 16) & 255, (packed >> 8) & 255, packed & 255];
  return `#${channels
    .map((c) => Math.round(strength * c + (1 - strength) * 255))
    .map((c) => c.toString(16).padStart(2, "0"))
    .join("")}`;
}

/** Donut slice ramp: four validated accent tints, darkest = largest position. */
export const ACCENT_RAMP: readonly string[] = [
  ACCENT,
  tint(ACCENT, 0.85),
  tint(ACCENT, 0.7),
  tint(ACCENT, 0.55),
];

/** Deliberately neutral fill for the folded "Other" donut slice. */
export const NEUTRAL = SECONDARY;

/** Recessive gridline/border color: secondary token faded into the surface. */
export const GRID = tint(SECONDARY, 0.15);

/** Shared tooltip chrome: surface card, md rounding, label-size text tokens. */
export const TOOLTIP_STYLE = {
  backgroundColor: SURFACE,
  border: `1px solid ${GRID}`,
  borderRadius: 8,
  color: PRIMARY,
  fontSize: 14,
} as const;

/** Shared axis tick style: secondary ink at the label token size. */
export const TICK_STYLE = { fill: SECONDARY, fontSize: 14 } as const;

/** Recharts `Tooltip formatter` for USD values (recharts may pass arrays);
 * cents show below $100 (per-share figures), whole dollars above.
 */
export function moneyTip(value: number | string | Array<number | string>): string {
  if (typeof value !== "number") return String(value);
  return usd(value, Math.abs(value) < 100 ? 2 : 0);
}
