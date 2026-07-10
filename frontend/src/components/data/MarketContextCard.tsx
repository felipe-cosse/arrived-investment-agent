/** Enrichment view of one market (§7): momentum meter plus home-value/rent
 * YoY, unemployment, population, and median income. Positive growth renders in
 * `success`; missing enrichment values render as an em dash, never hidden.
 */

import type { ReactElement } from "react";
import { compact, pct, usd } from "../../lib/format";
import type { MarketContext } from "../../types/domain";

interface MarketContextCardProps {
  market: string;
  context: MarketContext;
}

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

/** YoY rates in success when positive; em dash when the source has no data. */
function growth(value: number | null): { value: string; positive: boolean } {
  if (value === null) return { value: "—", positive: false };
  return { value: pct(value), positive: value > 0 };
}

export default function MarketContextCard({ market, context }: MarketContextCardProps): ReactElement {
  const hv = growth(context.home_value_yoy);
  const rent = growth(context.rent_yoy);
  return (
    <div className="rounded-lg bg-surface p-lg shadow-sm">
      <div className="flex items-start justify-between gap-sm">
        <div>
          <h3 className="text-body font-semibold text-primary">{market}</h3>
          <p className="text-label text-secondary">{context.metro}</p>
        </div>
        <span className="rounded-sm bg-accent/10 px-sm py-sm text-label text-accent">
          Momentum {context.momentum.toFixed(2)}
        </span>
      </div>
      <div className="mt-md h-1 rounded-sm bg-background" aria-hidden="true">
        <div
          className="h-1 rounded-sm bg-accent"
          style={{ width: `${Math.min(100, Math.max(0, context.momentum * 100))}%` }}
        />
      </div>
      <dl className="mt-lg grid grid-cols-2 gap-md sm:grid-cols-3">
        <Stat label="Home value YoY" value={hv.value} positive={hv.positive} />
        <Stat label="Rent YoY" value={rent.value} positive={rent.positive} />
        <Stat
          label="Unemployment"
          value={context.unemployment_rate === null ? "—" : pct(context.unemployment_rate / 100, 1)}
        />
        <Stat
          label="Population"
          value={context.population === null ? "—" : compact(context.population)}
        />
        <Stat
          label="Median income"
          value={context.median_income === null ? "—" : usd(context.median_income)}
        />
      </dl>
    </div>
  );
}
