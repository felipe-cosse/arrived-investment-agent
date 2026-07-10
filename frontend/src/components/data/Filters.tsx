/** Explorer filter row (§9 query params): market, property type, and minimum
 * dividend yield. Fully controlled — emits a new `OfferingFilters` upward.
 */

import type { ReactElement } from "react";
import type { OfferingFilters } from "../../api/client";
import { humanize } from "../../lib/format";

const PROPERTY_TYPES = ["single_family", "vacation_rental", "fund"] as const;

const FIELD_CLASS =
  "rounded-md border border-secondary/20 bg-surface px-sm py-sm text-body text-primary focus:border-accent focus:outline-none";

interface FiltersProps {
  filters: OfferingFilters;
  markets: string[];
  onChange: (filters: OfferingFilters) => void;
}

function Field({ label, children }: { label: string; children: ReactElement }): ReactElement {
  return (
    <label className="flex flex-col gap-sm text-label text-secondary">
      {label}
      {children}
    </label>
  );
}

export default function Filters({ filters, markets, onChange }: FiltersProps): ReactElement {
  return (
    <div className="flex flex-wrap items-end gap-md">
      <Field label="Market">
        <select
          value={filters.market ?? ""}
          onChange={(e) => onChange({ ...filters, market: e.target.value || undefined })}
          className={FIELD_CLASS}
        >
          <option value="">All markets</option>
          {markets.map((market) => (
            <option key={market} value={market}>
              {market}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Property type">
        <select
          value={filters.property_type ?? ""}
          onChange={(e) => onChange({ ...filters, property_type: e.target.value || undefined })}
          className={FIELD_CLASS}
        >
          <option value="">All types</option>
          {PROPERTY_TYPES.map((type) => (
            <option key={type} value={type}>
              {humanize(type)}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Min yield (%)">
        <input
          type="number"
          min={0}
          step={0.5}
          value={filters.min_dividend_yield === undefined ? "" : filters.min_dividend_yield * 100}
          onChange={(e) => {
            const raw = e.target.value;
            onChange({
              ...filters,
              min_dividend_yield: raw === "" ? undefined : Number(raw) / 100,
            });
          }}
          className={`${FIELD_CLASS} w-24`}
        />
      </Field>
    </div>
  );
}
