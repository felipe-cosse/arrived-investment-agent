/** Detailed Arrived facts grouped without conflating fees, reserves, or gross rent. */

import type { ReactElement, ReactNode } from "react";
import { compact, humanize, pct, shortDate, usd } from "../../lib/format";
import type { Offering } from "../../types/domain";

function Fact({ label, children }: { label: string; children: ReactNode }): ReactElement {
  return (
    <div>
      <dt className="text-label text-secondary">{label}</dt>
      <dd className="mt-sm text-body font-semibold text-primary">{children}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }): ReactElement {
  return (
    <section className="rounded-lg bg-surface p-lg shadow-sm">
      <h3 className="text-body font-semibold text-primary">{title}</h3>
      <dl className="mt-md grid grid-cols-2 gap-lg sm:grid-cols-3">{children}</dl>
    </section>
  );
}

function money(value: number | null): string {
  return value === null ? "—" : usd(value);
}

function holdPeriod(offering: Offering): string {
  const low = offering.hold_period_min_years;
  const high = offering.hold_period_max_years;
  if (low === null && high === null) return "—";
  if (low === high || high === null) return `${low ?? high} years`;
  if (low === null) return `Up to ${high} years`;
  return `${low}–${high} years`;
}

function address(offering: Offering): string {
  const parts = [offering.street_address, offering.market];
  if (offering.postal_code !== null) parts.push(offering.postal_code);
  return parts.filter((part): part is string => part !== null && part !== "").join(", ");
}

export default function OfferingFacts({ offering }: { offering: Offering }): ReactElement {
  const hasRental = offering.monthly_rent_usd !== null || offering.lease_status !== null;
  const hasProperty = offering.bedrooms !== null || offering.square_feet !== null ||
    offering.street_address !== null;
  return (
    <div className="flex flex-col gap-lg">
      {offering.description !== null ? (
        <p className="rounded-lg bg-surface p-lg text-body text-secondary shadow-sm">
          {offering.description}
        </p>
      ) : null}
      <Section title="Investment facts">
        <Fact label="Share price">{usd(offering.share_price_usd, 2)}</Fact>
        <Fact label="Minimum investment">{usd(offering.min_investment_usd)}</Fact>
        <Fact label="Purchase price">{money(offering.purchase_price_usd)}</Fact>
        <Fact label="Investors">
          {offering.investor_count === null ? "—" : compact(offering.investor_count)}
        </Fact>
        <Fact label="Projected dividend yield">{pct(offering.projected_dividend_yield)}</Fact>
        <Fact label="Projected appreciation">{pct(offering.projected_appreciation)}</Fact>
        <Fact label="Annual AUM fee">{money(offering.annual_platform_fee_usd)}</Fact>
        <Fact label="Closing & holding costs">
          {money(offering.closing_offering_holding_costs_usd)}
        </Fact>
        <Fact label="Improvements & reserves">
          {money(offering.property_improvements_reserves_usd)}
        </Fact>
        <Fact label="Debt amount">{money(offering.debt_amount_usd)}</Fact>
        <Fact label="Debt interest">
          {offering.debt_interest_pct === null
            ? "—"
            : `${offering.debt_interest_pct.toFixed(2)}%`}
        </Fact>
        <Fact label="Target hold period">{holdPeriod(offering)}</Fact>
      </Section>
      {hasRental ? (
        <Section title="Rental facts">
          <Fact label="Rent / month">{money(offering.monthly_rent_usd)}</Fact>
          <Fact label="Annual gross rent">{money(offering.annual_rent_usd)}</Fact>
          <Fact label="Lease status">
            {offering.lease_status === null
              ? "—"
              : humanize(offering.lease_status.toLowerCase())}
          </Fact>
          <Fact label="Lease through">
            {offering.lease_end_date === null ? "—" : shortDate(offering.lease_end_date)}
          </Fact>
        </Section>
      ) : null}
      {hasProperty ? (
        <Section title="Property facts">
          <Fact label="Bedrooms">{offering.bedrooms ?? "—"}</Fact>
          <Fact label="Bathrooms">{offering.bathrooms ?? "—"}</Fact>
          <Fact label="Square feet">
            {offering.square_feet === null ? "—" : offering.square_feet.toLocaleString("en-US")}
          </Fact>
          <Fact label="Year built">{offering.year_built ?? "—"}</Fact>
          <Fact label="Address">{address(offering) || "—"}</Fact>
        </Section>
      ) : null}
      <p className="text-label text-secondary">
        Gross rent is monthly rent × 12. AUM fees and one-time costs are shown separately;
        Arrived's catalogue does not provide a total annual operating-expense figure.
      </p>
    </div>
  );
}
