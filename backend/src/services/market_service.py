"""MarketService: turns stored enrichment metrics into MarketContext views (§7).

Depends only on the OfferingReader port (R2). Momentum stays a bounded tilt and
never a gate (R14): markets without an alias or without data are simply omitted
from the tilt map, which the engine treats as neutral 0.5.
"""

from __future__ import annotations

from collections.abc import Iterable

from domain.market import SEED_SOURCE, MarketContext, momentum, yoy
from domain.models import MetricRow
from domain.ports import OfferingReader

# Latest month plus the same month a year earlier must both be in the window.
_YOY_WINDOW_MONTHS = 25


def _latest(rows: list[MetricRow]) -> float | None:
    """Latest-month value for one metric, preferring live sources over seed (§7)."""
    live = {r.month: r.value for r in rows if r.source != SEED_SOURCE}
    seeded = {r.month: r.value for r in rows if r.source == SEED_SOURCE}
    merged = {**seeded, **live}
    if not merged:
        return None
    return merged[max(merged)]


class MarketService:
    """Builds MarketContext snapshots and per-market momentum tilts from metrics."""

    def __init__(self, reader: OfferingReader) -> None:
        """Read metrics and aliases through the OfferingReader port only (R2)."""
        self._reader = reader

    def context_for_market(self, raw_market: str) -> MarketContext | None:
        """Context for a raw offering market, or None when no alias maps it (R11)."""
        metro = self._reader.get_metro_for_market(raw_market)
        if metro is None:
            return None
        return self._context(metro)

    def momentum_by_market(self, markets: Iterable[str]) -> dict[str, float]:
        """Momentum tilt per raw market; unmapped markets are omitted (neutral, R14)."""
        tilts: dict[str, float] = {}
        for market in sorted(set(markets)):
            metro = self._reader.get_metro_for_market(market)
            if metro is None:
                continue
            tilts[market] = self._context(metro).momentum
        return tilts

    def _context(self, metro: str) -> MarketContext:
        """Assemble YoY signals, point-in-time stats, and momentum for one metro."""
        by_metric: dict[str, list[MetricRow]] = {}
        for row in self._reader.get_market_metrics(metro, _YOY_WINDOW_MONTHS):
            by_metric.setdefault(row.metric, []).append(row)
        hv_yoy = yoy(by_metric.get("home_value_index", []))
        rent_yoy = yoy(by_metric.get("rent_index", []))
        return MarketContext(
            metro=metro,
            home_value_yoy=hv_yoy,
            rent_yoy=rent_yoy,
            unemployment_rate=_latest(by_metric.get("unemployment_rate", [])),
            population=_latest(by_metric.get("population", [])),
            median_income=_latest(by_metric.get("median_income", [])),
            momentum=momentum(hv_yoy, rent_yoy),
        )
