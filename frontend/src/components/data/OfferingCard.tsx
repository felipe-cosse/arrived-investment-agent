/** Property card for one offering: DESIGN.md `card` token values (surface,
 * rounded-lg, spacing-lg padding, subtle shadow), a token-gradient image
 * placeholder, and key financial metrics with positive yields in `success`.
 */

import type { ReactElement } from "react";
import { humanize, pct, usd } from "../../lib/format";
import type { Offering } from "../../types/domain";

interface OfferingCardProps {
  offering: Offering;
  onSelect?: (id: string) => void;
}

function Metric({ label, value, positive = false }: {
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

function CardBody({ offering }: { offering: Offering }): ReactElement {
  return (
    <>
      <div className="flex h-16 items-center justify-center rounded-md bg-gradient-to-br from-accent/15 to-accent/5">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-8 w-8 text-accent" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 11.5 12 4l9 7.5M5.5 9.5V20h13V9.5M9.5 20v-6h5v6" />
        </svg>
      </div>
      <div className="mt-md flex items-start justify-between gap-sm">
        <div>
          <h3 className="text-body font-semibold text-primary">{offering.name}</h3>
          <p className="text-label text-secondary">{offering.market}</p>
        </div>
        <span className="rounded-sm bg-accent/10 px-sm py-sm text-label text-accent">
          {humanize(offering.property_type)}
        </span>
      </div>
      <dl className="mt-md grid grid-cols-2 gap-md">
        <Metric label="Dividend yield" value={pct(offering.projected_dividend_yield)} positive />
        <Metric label="Appreciation" value={pct(offering.projected_appreciation)} positive />
        <Metric label="Share price" value={usd(offering.share_price_usd, 2)} />
        <Metric label="Min investment" value={usd(offering.min_investment_usd)} />
      </dl>
      <div className="mt-md flex justify-between text-label text-secondary">
        <span>{humanize(offering.status)}</span>
        <span>
          {offering.funded_pct !== null
            ? `${pct(offering.funded_pct, 0)} funded`
            : offering.leverage_pct !== null
              ? `${pct(offering.leverage_pct, 0)} leverage`
              : ""}
        </span>
      </div>
      {offering.funded_pct !== null && (
        <div className="mt-sm h-1 rounded-sm bg-background">
          <div
            className="h-1 rounded-sm bg-accent"
            style={{ width: `${Math.min(100, offering.funded_pct * 100)}%` }}
          />
        </div>
      )}
    </>
  );
}

export default function OfferingCard({ offering, onSelect }: OfferingCardProps): ReactElement {
  if (onSelect === undefined) {
    return (
      <article className="rounded-lg bg-surface p-lg shadow-sm">
        <CardBody offering={offering} />
      </article>
    );
  }
  return (
    <button
      type="button"
      onClick={() => onSelect(offering.id)}
      className="rounded-lg bg-surface p-lg text-left shadow-sm transition-shadow hover:shadow-md"
    >
      <CardBody offering={offering} />
    </button>
  );
}
