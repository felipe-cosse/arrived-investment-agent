/** "Data as of …" badge powered by GET /api/meta (§9): shows the freshest
 * timestamp across offerings and market metrics plus the offering count, so
 * data staleness is always visible in the header.
 */

import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { fetchMeta } from "../../api/client";
import { shortDate } from "../../lib/format";
import type { Meta } from "../../types/domain";

/** Freshest of the offerings / market-metrics timestamps; null when unseeded. */
function latestAsOf(meta: Meta): string | null {
  const stamps = [meta.offerings.latest_as_of, meta.market_metrics.latest_as_of].filter(
    (stamp): stamp is string => stamp !== null,
  );
  return stamps.length === 0 ? null : stamps.reduce((a, b) => (a > b ? a : b));
}

export default function StalenessBadge(): ReactElement {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchMeta()
      .then((result) => {
        if (!cancelled) setMeta(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const latest = meta === null ? null : latestAsOf(meta);
  const label = failed
    ? "Data status unavailable"
    : meta === null
      ? "Checking data freshness…"
      : `Data as of ${latest === null ? "—" : shortDate(latest)} · ${meta.offerings.rows} offerings`;

  return (
    <span className="rounded-sm border border-secondary/20 bg-surface px-sm py-sm text-label text-secondary shadow-sm">
      {label}
    </span>
  );
}
