/** "Data as of …" badge powered by GET /api/meta (§9): shows the freshest
 * timestamp across offerings and market metrics plus the offering count, so
 * data staleness is always visible in the header.
 */

import { useEffect } from "react";
import type { ReactElement } from "react";
import { shortDate } from "../../lib/format";
import { useMetaStore } from "../../state/metaStore";
import type { Meta } from "../../types/domain";

/** Freshest of the offerings / market-metrics timestamps; null when unseeded. */
function latestAsOf(meta: Meta): string | null {
  const stamps = [meta.offerings.latest_as_of, meta.market_metrics.latest_as_of].filter(
    (stamp): stamp is string => stamp !== null,
  );
  return stamps.length === 0 ? null : stamps.reduce((a, b) => (a > b ? a : b));
}

export default function StalenessBadge(): ReactElement {
  const meta = useMetaStore((s) => s.meta);
  const isLoading = useMetaStore((s) => s.isLoading);
  const failed = useMetaStore((s) => s.failed);
  const loadMeta = useMetaStore((s) => s.loadMeta);

  useEffect(() => {
    void loadMeta();
  }, [loadMeta]);

  const latest = meta === null ? null : latestAsOf(meta);
  const label = failed && meta === null
    ? "Data status unavailable"
    : meta === null || isLoading
      ? "Checking data freshness…"
      : `Data as of ${latest === null ? "—" : shortDate(latest)} · ${meta.offerings.rows} offerings`;

  return (
    <span className="rounded-sm border border-secondary/20 bg-surface px-sm py-sm text-label text-secondary shadow-sm">
      {label}
    </span>
  );
}
