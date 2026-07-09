/** Single source of truth for the DESIGN.md color tokens.
 *
 * DESIGN.md defines six hex values (primary, secondary, accent, success,
 * background, surface). They previously lived duplicated in both
 * `tailwind.config.ts` and `chartTheme.ts`; both now import them from here so
 * there is exactly one place to update if DESIGN.md's palette ever changes.
 */

export const PRIMARY = "#111827";
export const SECONDARY = "#4B5563";
export const ACCENT = "#2563EB";
export const SUCCESS = "#10B981";
export const BACKGROUND = "#F9FAFB";
export const SURFACE = "#FFFFFF";
