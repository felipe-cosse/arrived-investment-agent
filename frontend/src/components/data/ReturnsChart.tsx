/** Monthly return history for one offering as two stacked small multiples
 * sharing the month axis — share value (accent line) and dividend per share
 * (success bars). Two units means two panels, never a dual-axis chart.
 */

import type { ReactElement } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ACCENT, GRID, SUCCESS, TICK_STYLE, TOOLTIP_STYLE, moneyTip } from "../../lib/chartTheme";
import { monthLabel } from "../../lib/format";
import type { ReturnRecord } from "../../types/domain";

interface ReturnsChartProps {
  returns: ReturnRecord[];
  title?: string;
}

function Panel({ heading, children }: { heading: string; children: ReactElement }): ReactElement {
  return (
    <div>
      <h4 className="text-label text-secondary">{heading}</h4>
      <div className="mt-sm h-40">
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default function ReturnsChart({ returns, title }: ReturnsChartProps): ReactElement {
  if (returns.length === 0) {
    return (
      <div className="rounded-lg bg-surface p-lg shadow-sm">
        <p className="text-body text-secondary">No return history available.</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-lg rounded-lg bg-surface p-lg shadow-sm">
      {title !== undefined && (
        <h3 className="text-body font-semibold text-primary">{title}</h3>
      )}
      <Panel heading="Share value (USD)">
        <LineChart data={returns} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="month" tickFormatter={monthLabel} tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} width={56} domain={["auto", "auto"]} tickFormatter={moneyTip} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={moneyTip} />
          <Line type="monotone" dataKey="share_value_usd" name="Share value" stroke={ACCENT} strokeWidth={2} dot={false} />
        </LineChart>
      </Panel>
      <Panel heading="Dividend per share (USD)">
        <BarChart data={returns} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke={GRID} vertical={false} />
          <XAxis dataKey="month" tickFormatter={monthLabel} tick={TICK_STYLE} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={24} />
          <YAxis tick={TICK_STYLE} tickLine={false} axisLine={false} width={56} tickFormatter={moneyTip} />
          <Tooltip contentStyle={TOOLTIP_STYLE} formatter={moneyTip} cursor={{ fill: GRID }} />
          <Bar dataKey="dividend_per_share" name="Dividend" fill={SUCCESS} radius={[4, 4, 0, 0]} />
        </BarChart>
      </Panel>
    </div>
  );
}
