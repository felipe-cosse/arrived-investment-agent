/** Locale-stable display formatting shared by every component: USD amounts,
 * decimal percentages, compact counts, ISO timestamps, and 'YYYY-MM' months.
 * Pure functions only — no React, no state.
 */

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const;

/** Format a dollar amount, e.g. `usd(1234.5)` → "$1,235". */
export function usd(value: number, digits = 0): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

/** Format an annual-decimal rate, e.g. `pct(0.045)` → "4.5%". */
export function pct(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

/** Compact large counts, e.g. `compact(1_240_000)` → "1.2M". */
export function compact(value: number): string {
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

/** Short date from an ISO timestamp, e.g. "Jun 12, 2026"; echoes bad input. */
export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

/** Axis-sized label for a 'YYYY-MM' month, e.g. "2026-05" → "May 26". */
export function monthLabel(month: string): string {
  const [year, m] = month.split("-").map(Number);
  const name = Number.isInteger(m) ? MONTHS[m - 1] : undefined;
  if (year === undefined || name === undefined) return month;
  return `${name} ${String(year).slice(2)}`;
}

/** Human-readable form of a snake_case identifier ("get_offerings" → "get offerings"). */
export function humanize(value: string): string {
  return value.replace(/_/g, " ");
}
