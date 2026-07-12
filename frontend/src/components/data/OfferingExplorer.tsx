/** Data-explorer view: filterable offering grid backed by GET /api/offerings,
 * with a drill-in detail view (card + 12-month returns) per offering and a
 * manual "Refresh live data" trigger for the Arrived public-catalogue JSON refresh.
 */

import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { errorMessage, fetchOffering, fetchOfferings, refreshOfferings } from "../../api/client";
import type { OfferingDetails, OfferingFilters } from "../../api/client";
import { useMetaStore } from "../../state/metaStore";
import type { Offering } from "../../types/domain";
import Filters from "./Filters";
import OfferingCard from "./OfferingCard";
import OfferingDetail from "./OfferingDetail";

const REFRESH_BUTTON_CLASS =
  "rounded-md bg-accent px-md py-sm text-body font-medium text-surface shadow-sm transition-opacity disabled:opacity-50";

/** Outcome of the last refresh run, rendered inline beside the filters. */
interface RefreshStatus {
  kind: "success" | "error";
  text: string;
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
  const reloadMeta = useMetaStore((s) => s.loadMeta);

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
        const purged =
          report.seeds_purged > 0 ? ` · ${report.seeds_purged} demo rows removed` : "";
        const degraded =
          report.share_price_failures > 0
            ? ` · ${report.share_price_failures} price histories unavailable`
            : "";
        const missingDetails =
          report.detail_failures > 0
            ? ` · ${report.detail_failures} detail records unavailable`
            : "";
        setRefreshStatus({
          kind: "success",
          text: `${report.offerings} live offerings loaded${purged}${degraded}${missingDetails}`,
        });
        setReloadKey((key) => key + 1);
        void reloadMeta();
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
    return <OfferingDetail details={details} onBack={() => setDetails(null)} />;
  }
  const hasFilters = Object.values(filters).some((value) => value !== undefined);
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
        <p className="text-body text-secondary">
          {hasFilters
            ? "No offerings match these filters."
            : "No offerings loaded yet — refresh to load Arrived's live catalogue."}
        </p>
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
