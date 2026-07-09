/** Horizon projection for a feasible plan: projected portfolio value (accent)
 * and cumulative dividends (success) per year — two same-unit USD series on a
 * single axis, with a legend and hover tooltip.
 */

import type { ReactElement } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ACCENT, GRID, SUCCESS, TICK_STYLE, TOOLTIP_STYLE, moneyTip } from "../../lib/chartTheme";
import type { FeasiblePlan } from "../../types/domain";

interface CashflowPoint {
  year: number;
  value: number;
  dividends: number;
}

/** Yearly points from the plan's own per-position appreciation rates (§6). */
function project(plan: FeasiblePlan): CashflowPoint[] {
  const points: CashflowPoint[] = [];
  for (let year = 0; year <= plan.horizon_years; year += 1) {
    const value = plan.positions.reduce(
      (sum, p) => sum + p.amount_usd * (1 + p.projected_appreciation) ** year,
      0,
    );
    points.push({
      year,
      value: Math.round(value),
      dividends: Math.round(plan.summary.projected_annual_dividends_usd * year),
    });
  }
  return points;
}

function LegendRow(): ReactElement {
  const entries = [
    { label: "Projected value", color: ACCENT },
    { label: "Cumulative dividends", color: SUCCESS },
  ];
  return (
    <ul className="flex flex-wrap gap-md">
      {entries.map((entry) => (
        <li key={entry.label} className="flex items-center gap-sm text-label text-secondary">
          <span
            aria-hidden="true"
            className="h-sm w-sm rounded-sm"
            style={{ backgroundColor: entry.color }}
          />
          {entry.label}
        </li>
      ))}
    </ul>
  );
}

export default function CashflowChart({ plan }: { plan: FeasiblePlan }): ReactElement {
  return (
    <div className="flex flex-col gap-md rounded-lg bg-surface p-lg shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-sm">
        <h3 className="text-body font-semibold text-primary">
          {plan.horizon_years}-year projection
        </h3>
        <LegendRow />
      </div>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={project(plan)} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis
              dataKey="year"
              tick={TICK_STYLE}
              tickLine={false}
              axisLine={{ stroke: GRID }}
              tickFormatter={(year: number) => `Y${year}`}
            />
            <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} width={64} tickFormatter={moneyTip} />
            <Tooltip
              contentStyle={TOOLTIP_STYLE}
              formatter={moneyTip}
              labelFormatter={(year: number | string) => `Year ${String(year)}`}
            />
            <Line type="monotone" dataKey="value" name="Projected value" stroke={ACCENT} strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="dividends" name="Cumulative dividends" stroke={SUCCESS} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-label italic text-secondary">{plan.disclaimer}</p>
    </div>
  );
}
