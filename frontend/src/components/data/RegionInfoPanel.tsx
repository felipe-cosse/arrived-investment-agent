/** Lazy, source-attributed metro observations for one offering. */

import { useEffect, useRef, useState } from "react";
import type { ReactElement } from "react";
import {
  errorMessage,
  fetchRegionInfo,
  refreshMarketData,
} from "../../api/client";
import { compact, monthLabel, shortDate, usd } from "../../lib/format";
import type { RegionInfo, RegionMetric } from "../../types/domain";

export function formatRegionValue(metric: RegionMetric): string {
  switch (metric.unit) {
    case "usd":
    case "usd_per_month":
    case "usd_per_year":
      return usd(metric.value);
    case "percent":
      return `${metric.value.toFixed(1)}%`;
    case "people":
      return compact(metric.value);
  }
}

function Metric({ metric }: { metric: RegionMetric }): ReactElement {
  return (
    <div className="rounded-md border border-secondary/20 p-md">
      <dt className="text-label text-secondary">{metric.label}</dt>
      <dd className="mt-sm text-body font-semibold text-primary">
        {formatRegionValue(metric)}
      </dd>
      <dd className="mt-sm text-label text-secondary">
        {monthLabel(metric.observation_month)} · retrieved {shortDate(metric.retrieved_at)}
      </dd>
      <dd className="mt-sm">
        <a
          href={metric.source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-label font-medium text-accent hover:underline"
        >
          {metric.source.name} ↗
        </a>
      </dd>
    </div>
  );
}

export default function RegionInfoPanel({ offeringId }: { offeringId: string }): ReactElement {
  const [info, setInfo] = useState<RegionInfo | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "refreshing">("idle");
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, [offeringId]);

  const load = async (refresh: boolean): Promise<void> => {
    setStatus(refresh ? "refreshing" : "loading");
    setError(null);
    try {
      if (refresh) await refreshMarketData();
      const result = await fetchRegionInfo(offeringId);
      if (mounted.current) setInfo(result);
    } catch (err: unknown) {
      if (mounted.current) setError(errorMessage(err));
    } finally {
      if (mounted.current) setStatus("idle");
    }
  };

  const panelId = `region-info-${offeringId}`;
  return (
    <section className="rounded-lg bg-surface p-lg shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-md">
        <div>
          <h3 className="text-body font-semibold text-primary">Public metro data</h3>
          <p className="mt-sm text-label text-secondary">
            Zillow, FRED, and U.S. Census observations stored by this app.
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load(false)}
          disabled={status !== "idle"}
          aria-expanded={info !== null}
          aria-controls={panelId}
          className="rounded-md bg-accent px-md py-sm text-label font-medium text-surface disabled:opacity-50"
        >
          {status === "loading" ? "Loading…" : "Load metro insights"}
        </button>
      </div>
      <div id={panelId} className="mt-md">
        {error !== null ? (
          <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
            {error}
          </p>
        ) : null}
        {info !== null && info.available ? (
          <>
            <p className="text-label text-secondary">
              Regional series mapped from {info.market}. These are metro indicators, not
              neighborhood or property measurements.
            </p>
            <dl className="mt-md grid gap-md sm:grid-cols-2 xl:grid-cols-3">
              {info.metrics.map((metric) => (
                <Metric key={`${metric.source.id}-${metric.metric}`} metric={metric} />
              ))}
            </dl>
            <p className="mt-md text-label text-secondary">{info.disclaimer}</p>
          </>
        ) : null}
        {info !== null && !info.available ? (
          <div className="rounded-md bg-background p-md">
            <p className="text-label text-secondary">
              {info.metro === null
                ? "This diversified offering has no single metro area."
                : "No stored public observations are available for this mapped metro yet."}
            </p>
            {info.metro !== null ? (
              <button
                type="button"
                onClick={() => void load(true)}
                disabled={status !== "idle"}
                className="mt-md rounded-md border border-accent px-md py-sm text-label font-medium text-accent disabled:opacity-50"
              >
                {status === "refreshing" ? "Refreshing public sources…" : "Refresh public data"}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </section>
  );
}
