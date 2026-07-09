/** Allocation donut for a plan's new-money positions: top four positions on
 * the validated accent-tint ramp, the remainder folded into a neutral "Other"
 * slice, 2px surface gaps between slices, and a legend carrying identity so
 * color is never the only channel (the positions table is the table view).
 */

import type { ReactElement } from "react";
import { Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { ACCENT_RAMP, NEUTRAL, SURFACE, TOOLTIP_STYLE, moneyTip } from "../../lib/chartTheme";
import { pct, usd } from "../../lib/format";
import type { Position } from "../../types/domain";

const MAX_SLICES = ACCENT_RAMP.length;

interface Slice {
  name: string;
  value: number;
  fill: string;
}

/** Largest positions get the darkest tints; the tail folds into "Other". */
function toSlices(positions: Position[]): Slice[] {
  const ranked = [...positions].sort(
    (a, b) => b.amount_usd - a.amount_usd || a.offering_id.localeCompare(b.offering_id),
  );
  const named = ranked.slice(0, MAX_SLICES).map((p, i) => ({
    name: p.name,
    value: p.amount_usd,
    fill: ACCENT_RAMP[i],
  }));
  const rest = ranked.slice(MAX_SLICES);
  if (rest.length === 0) return named;
  return [
    ...named,
    {
      name: `Other (${rest.length})`,
      value: rest.reduce((sum, p) => sum + p.amount_usd, 0),
      fill: NEUTRAL,
    },
  ];
}

export default function AllocationDonut({ positions }: { positions: Position[] }): ReactElement {
  const slices = toSlices(positions);
  const total = slices.reduce((sum, s) => sum + s.value, 0);
  return (
    <div className="rounded-lg bg-surface p-lg shadow-sm">
      <h3 className="text-body font-semibold text-primary">Allocation</h3>
      <div className="mt-md flex flex-wrap items-center gap-lg">
        <div className="relative h-44 w-44 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Tooltip contentStyle={TOOLTIP_STYLE} formatter={moneyTip} />
              <Pie
                data={slices}
                dataKey="value"
                nameKey="name"
                innerRadius="62%"
                outerRadius="95%"
                stroke={SURFACE}
                strokeWidth={2}
                isAnimationActive={false}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-label text-secondary">New money</span>
            <span className="text-body font-semibold text-primary">{usd(total)}</span>
          </div>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-sm">
          {slices.map((slice) => (
            <li key={slice.name} className="flex items-center gap-sm text-label">
              <span
                aria-hidden="true"
                className="h-sm w-sm shrink-0 rounded-sm"
                style={{ backgroundColor: slice.fill }}
              />
              <span className="min-w-0 flex-1 truncate text-primary">{slice.name}</span>
              <span className="text-secondary">{usd(slice.value)}</span>
              <span className="w-12 text-right font-medium text-primary">
                {total > 0 ? pct(slice.value / total, 0) : "—"}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
