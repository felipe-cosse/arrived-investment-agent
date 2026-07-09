/** Full rendering of an engine Plan (§6): headline stats, allocation donut and
 * horizon projection, the positions table with per-position score breakdowns
 * (R13), assumptions, and the not-financial-advice disclaimer. Infeasible
 * plans render their reason (R12).
 */

import type { ReactElement } from "react";
import { humanize, pct, usd } from "../../lib/format";
import type { Plan, Position } from "../../types/domain";
import AllocationDonut from "./AllocationDonut";
import CashflowChart from "./CashflowChart";

function Stat({ label, value, positive = false }: {
  label: string;
  value: string;
  positive?: boolean;
}): ReactElement {
  return (
    <div>
      <dt className="text-label text-secondary">{label}</dt>
      <dd className={`text-body font-semibold ${positive ? "text-success" : "text-primary"}`}>
        {value}
      </dd>
    </div>
  );
}

/** R13: the score breakdown is the sanctioned explanation for rankings. */
function breakdownTitle(position: Position): string {
  const b = position.score_breakdown;
  return `yield ${b.yield} · appreciation ${b.appreciation} · momentum ${b.momentum} · leverage ${b.leverage}`;
}

function PositionsTable({ positions }: { positions: Position[] }): ReactElement {
  return (
    <div className="overflow-x-auto rounded-lg bg-surface p-lg shadow-sm">
      <h3 className="text-body font-semibold text-primary">Positions (new money)</h3>
      <table className="mt-md w-full text-label">
        <thead>
          <tr className="text-left text-secondary">
            <th className="py-sm pr-md font-medium">Offering</th>
            <th className="py-sm pr-md font-medium">Type</th>
            <th className="py-sm pr-md text-right font-medium">Amount</th>
            <th className="py-sm pr-md text-right font-medium">Weight</th>
            <th className="py-sm pr-md text-right font-medium">Yield</th>
            <th className="py-sm pr-md text-right font-medium">Appreciation</th>
            <th className="py-sm pr-md text-right font-medium">Div/yr</th>
            <th className="py-sm text-right font-medium">Score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-secondary/10">
          {positions.map((p) => (
            <tr key={p.offering_id}>
              <td className="py-sm pr-md">
                <div className="font-medium text-primary">{p.name}</div>
                <div className="text-secondary">{p.market}</div>
              </td>
              <td className="py-sm pr-md text-secondary">{humanize(p.property_type)}</td>
              <td className="py-sm pr-md text-right font-medium text-primary">{usd(p.amount_usd)}</td>
              <td className="py-sm pr-md text-right text-primary">{p.weight_pct.toFixed(1)}%</td>
              <td className="py-sm pr-md text-right font-medium text-success">{pct(p.projected_dividend_yield)}</td>
              <td className="py-sm pr-md text-right font-medium text-success">{pct(p.projected_appreciation)}</td>
              <td className="py-sm pr-md text-right text-primary">{usd(p.est_annual_dividend_usd)}</td>
              <td className="py-sm text-right text-primary">
                <span title={breakdownTitle(p)} className="cursor-help underline decoration-secondary/20 decoration-dotted underline-offset-2">
                  {p.score_breakdown.total.toFixed(4)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PlanSummary({ plan }: { plan: Plan }): ReactElement {
  if (!plan.feasible) {
    return (
      <div className="rounded-lg bg-surface p-lg shadow-sm">
        <h3 className="text-body font-semibold text-primary">Plan not feasible</h3>
        <p className="mt-sm text-body text-secondary">{plan.reason}</p>
      </div>
    );
  }
  const s = plan.summary;
  return (
    <div className="flex flex-col gap-lg">
      <div className="rounded-lg bg-surface p-lg shadow-sm">
        <div className="flex flex-wrap items-baseline justify-between gap-sm">
          <h3 className="text-h2 font-semibold text-primary">{usd(s.requested_usd)} plan</h3>
          <span className="rounded-sm bg-accent/10 px-sm py-sm text-label text-accent">
            {plan.risk_profile} · {plan.horizon_years}y horizon
          </span>
        </div>
        <dl className="mt-lg grid grid-cols-2 gap-md sm:grid-cols-4">
          <Stat label="Invested" value={usd(s.total_invested_usd)} />
          <Stat label="Unallocated cash" value={usd(s.unallocated_cash_usd)} />
          <Stat label="Positions" value={String(s.position_count)} />
          <Stat label="Blended yield" value={pct(s.blended_dividend_yield)} positive />
          <Stat label="Dividends / yr" value={usd(s.projected_annual_dividends_usd)} positive />
          <Stat label="Value at horizon" value={usd(s.projected_value_at_horizon_usd)} />
          <Stat label="Dividends at horizon" value={usd(s.projected_cumulative_dividends_usd)} positive />
          <Stat label="Total at horizon" value={usd(s.projected_total_at_horizon_usd)} positive />
        </dl>
        {s.existing_portfolio_usd > 0 && (
          <p className="mt-md text-label text-secondary">
            Existing holdings of {usd(s.existing_portfolio_usd)} were considered; portfolio total{" "}
            {usd(s.portfolio_total_usd)}.
          </p>
        )}
      </div>
      <div className="grid gap-lg xl:grid-cols-2">
        <AllocationDonut positions={plan.positions} />
        <CashflowChart plan={plan} />
      </div>
      <PositionsTable positions={plan.positions} />
      <div className="rounded-lg bg-surface p-lg shadow-sm">
        <h3 className="text-body font-semibold text-primary">Assumptions</h3>
        <ul className="mt-sm list-disc space-y-sm pl-lg text-label text-secondary">
          {plan.assumptions.map((assumption) => (
            <li key={assumption}>{assumption}</li>
          ))}
        </ul>
        <p className="mt-md text-label italic text-secondary">{plan.disclaimer}</p>
      </div>
    </div>
  );
}
