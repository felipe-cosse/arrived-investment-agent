/** Data-explorer view: filterable offering grid backed by GET /api/offerings,
 * with a drill-in detail view (card + 12-month returns) per offering and a
 * manual "Refresh live data" trigger for the Arrived catalogue scrape.
 */

import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { errorMessage, fetchOffering, fetchOfferings, refreshOfferings } from "../../api/client";
import type { OfferingDetails, OfferingFilters } from "../../api/client";
import { shortDate } from "../../lib/format";
import type { Offering } from "../../types/domain";
import Filters from "./Filters";
import OfferingCard from "./OfferingCard";
import ReturnsChart from "./ReturnsChart";

const REFRESH_BUTTON_CLASS =
  "rounded-md bg-accent px-md py-sm text-body font-medium text-surface shadow-sm transition-opacity disabled:opacity-50";

/** Outcome of the last refresh run, rendered inline beside the filters. */
interface RefreshStatus {
  kind: "success" | "error";
  text: string;
}

function Detail({ details, onBack }: {
  details: OfferingDetails;
  onBack: () => void;
}): ReactElement {
  return (
    <div className="flex flex-col gap-lg">
      <div>
        <button
          type="button"
          onClick={onBack}
          className="rounded-md px-sm py-sm text-label font-medium text-accent hover:bg-accent/10"
        >
          ← All offerings
        </button>
      </div>
      <div className="grid gap-lg lg:grid-cols-2">
        <OfferingCard offering={details.offering} />
        <ReturnsChart returns={details.history} title="Last 12 months" />
      </div>
      <p className="text-label text-secondary">
        Offering data as of {shortDate(details.offering.as_of)} (demo-seeded or Arrived catalogue data).
      </p>
    </div>
  );
}

export default function OfferingExplorer(): ReactElement {
  const [filters, setFilters] = useState<OfferingFilters>({});
  const [offerings, setOfferings] = useState<Offering[]>([]);
  const [markets, setMarkets] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [details, setDetails] = useState<OfferingDetails | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<RefreshStatus | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetchOfferings(filters)
      .then(({ offerings: rows }) => {
        if (cancelled) return;
        setOfferings(rows);
        setIsLoading(false);
        // Grow the market dropdown from every result seen, so narrowing a
        // filter never removes the other options.
        setMarkets((prev) =>
          Array.from(new Set([...prev, ...rows.map((o) => o.market)])).sort(),
        );
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(errorMessage(err));
        setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, reloadKey]);

  const refresh = (): void => {
    setIsRefreshing(true);
    setRefreshStatus(null);
    refreshOfferings()
      .then((report) => {
        setIsRefreshing(false);
        if (report.status === "error") {
          setRefreshStatus({ kind: "error", text: report.detail });
          return;
        }
        setRefreshStatus({
          kind: "success",
          text: `${report.offerings} live offerings loaded · ${report.seeds_retired} demo offerings retired`,
        });
        setReloadKey((key) => key + 1);
      })
      .catch((err: unknown) => {
        setIsRefreshing(false);
        setRefreshStatus({ kind: "error", text: errorMessage(err) });
      });
  };

  const select = (id: string): void => {
    setError(null);
    fetchOffering(id)
      .then(setDetails)
      .catch((err: unknown) => setError(errorMessage(err)));
  };

  if (details !== null) {
    return <Detail details={details} onBack={() => setDetails(null)} />;
  }
  return (
    <div className="flex flex-col gap-lg">
      <div className="flex flex-wrap items-end justify-between gap-md">
        <Filters filters={filters} markets={markets} onChange={setFilters} />
        <button
          type="button"
          onClick={refresh}
          disabled={isRefreshing}
          className={REFRESH_BUTTON_CLASS}
        >
          {isRefreshing ? "Refreshing…" : "Refresh live data"}
        </button>
      </div>
      {refreshStatus !== null &&
        (refreshStatus.kind === "success" ? (
          <p className="text-label text-success">{refreshStatus.text}</p>
        ) : (
          <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
            {refreshStatus.text}
          </p>
        ))}
      {error !== null && (
        <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
          {error}
        </p>
      )}
      {isLoading ? (
        <p className="text-body text-secondary">Loading offerings…</p>
      ) : offerings.length === 0 ? (
        <p className="text-body text-secondary">No offerings match these filters.</p>
      ) : (
        <div className="grid gap-md sm:grid-cols-2 xl:grid-cols-3">
          {offerings.map((offering) => (
            <OfferingCard key={offering.id} offering={offering} onSelect={select} />
          ))}
        </div>
      )}
    </div>
  );
}
