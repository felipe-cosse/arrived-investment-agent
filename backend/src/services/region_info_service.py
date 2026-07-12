"""Source-backed public market information for an offering's metro area.

The service reads only observations already persisted by the enrichment refresh.
It never calls a public provider while serving a request, and it deliberately
excludes the deterministic ``seed`` fixture from user-facing research results.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.models import MetricRow
from domain.ports import OfferingReader

_MONTHS = 25


@dataclass(frozen=True)
class _MetricDefinition:
    label: str
    unit: str
    source_name: str
    source_url: str


_METRICS: dict[tuple[str, str], _MetricDefinition] = {
    ("zillow_zhvi", "home_value_index"): _MetricDefinition(
        "Zillow Home Value Index", "usd", "Zillow Research",
        "https://www.zillow.com/research/data/"),
    ("zillow_zori", "rent_index"): _MetricDefinition(
        "Zillow Observed Rent Index", "usd_per_month", "Zillow Research",
        "https://www.zillow.com/research/data/"),
    ("fred", "unemployment_rate"): _MetricDefinition(
        "Unemployment rate", "percent", "Federal Reserve Bank of St. Louis (FRED)",
        "https://fred.stlouisfed.org/categories/32444"),
    ("census_acs", "population"): _MetricDefinition(
        "Population", "people", "U.S. Census Bureau ACS 5-year",
        "https://api.census.gov/data/2024/acs/acs5/groups/B01003.html"),
    ("census_acs", "median_income"): _MetricDefinition(
        "Median household income", "usd_per_year", "U.S. Census Bureau ACS 5-year",
        "https://api.census.gov/data/2024/acs/acs5/groups/B19013.html"),
}


def _latest_supported(rows: list[MetricRow]) -> list[MetricRow]:
    """Latest observation for each supported source/metric pair."""
    latest: dict[tuple[str, str], MetricRow] = {}
    for row in rows:
        key = (row.source, row.metric)
        if key not in _METRICS:
            continue
        current = latest.get(key)
        if current is None or (row.month, row.as_of) > (current.month, current.as_of):
            latest[key] = row
    return sorted(latest.values(), key=lambda row: (row.metric, row.source))


class RegionInfoService:
    """Build public-data views for offering cards from stored enrichment rows."""

    def __init__(self, reader: OfferingReader) -> None:
        self._reader = reader

    def for_offering(self, offering_id: str) -> dict[str, Any] | None:
        """Return metro information, or ``None`` when the offering is unknown."""
        offering = self._reader.get_offering(offering_id)
        if offering is None:
            return None
        metro = self._reader.get_metro_for_market(offering.market)
        rows = [] if metro is None else self._reader.get_market_metrics(metro, _MONTHS)
        metrics = [self._serialize(row) for row in _latest_supported(rows)]
        return {
            "offering_id": offering.id,
            "market": offering.market,
            "metro": metro,
            "scope": "metro_area" if metro is not None else None,
            "available": bool(metrics),
            "metrics": metrics,
            "disclaimer": (
                "Public metrics describe the mapped metro area, not the individual property "
                "or its immediate neighborhood. Verify local conditions before investing."
            ),
        }

    @staticmethod
    def _serialize(row: MetricRow) -> dict[str, Any]:
        definition = _METRICS[(row.source, row.metric)]
        return {
            "metric": row.metric,
            "label": definition.label,
            "value": row.value,
            "unit": definition.unit,
            "observation_month": row.month,
            "retrieved_at": row.as_of.isoformat(),
            "source": {
                "id": row.source,
                "name": definition.source_name,
                "url": definition.source_url,
            },
        }
