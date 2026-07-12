/** Compact offering summary with real Arrived imagery, source link, and explicit actions. */

import type { ReactElement } from "react";
import { compact, humanize, pct, usd } from "../../lib/format";
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

function PropertyImage({ offering }: { offering: Offering }): ReactElement {
  if (offering.thumbnail_url !== null) {
    return (
      <img
        src={offering.thumbnail_url}
        alt={`Exterior of ${offering.name}`}
        loading="lazy"
        decoding="async"
        className="h-40 w-full object-cover"
      />
    );
  }
  return (
    <div className="flex h-40 items-center justify-center bg-gradient-to-br from-accent/15 to-accent/5">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-10 w-10 text-accent" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 11.5 12 4l9 7.5M5.5 9.5V20h13V9.5M9.5 20v-6h5v6" />
      </svg>
    </div>
  );
}

export default function OfferingCard({ offering, onSelect }: OfferingCardProps): ReactElement {
  const funded = offering.funded_pct === null ? null : Math.round(offering.funded_pct * 100);
  const purchasePrice = offering.purchase_price_usd ?? offering.property_value_usd;
  return (
    <article className="overflow-hidden rounded-lg bg-surface shadow-sm transition-shadow hover:shadow-md">
      <PropertyImage offering={offering} />
      <div className="p-lg">
        <div className="flex items-start justify-between gap-sm">
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
          {offering.monthly_rent_usd !== null ? (
            <Metric label="Rent / mo" value={usd(offering.monthly_rent_usd)} />
          ) : (
            <Metric label="Share price" value={usd(offering.share_price_usd, 2)} />
          )}
          {purchasePrice !== null ? (
            <Metric label="Purchase price" value={usd(purchasePrice)} />
          ) : (
            <Metric label="Min investment" value={usd(offering.min_investment_usd)} />
          )}
          <Metric
            label="Investors"
            value={offering.investor_count === null ? "—" : compact(offering.investor_count)}
          />
        </dl>
        <div className="mt-md flex justify-between text-label text-secondary">
          <span>{humanize(offering.status)}</span>
          <span>{funded === null ? "" : `${funded}% funded`}</span>
        </div>
        {funded !== null ? (
          <div
            className="mt-sm h-1 rounded-sm bg-background"
            role="progressbar"
            aria-label={`${offering.name} funding`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={funded}
          >
            <div className="h-1 rounded-sm bg-accent" style={{ width: `${funded}%` }} />
          </div>
        ) : null}
        {(onSelect !== undefined || offering.source_url !== null) ? (
          <div className="mt-lg flex flex-wrap items-center gap-sm border-t border-secondary/20 pt-md">
            {onSelect !== undefined ? (
              <button
                type="button"
                onClick={() => onSelect(offering.id)}
                className="rounded-md bg-accent px-md py-sm text-label font-medium text-surface focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                View details
              </button>
            ) : null}
            {offering.source_url !== null ? (
              <a
                href={offering.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md px-md py-sm text-label font-medium text-accent hover:bg-accent/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                View on Arrived ↗
              </a>
            ) : null}
          </div>
        ) : null}
      </div>
    </article>
  );
}
