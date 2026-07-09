"""Census ACS 5-year adapter (§10): metro population and median household income.

One request fetches both variables for every mapped metro. The key is optional
per §13: when absent the source raises `MissingApiKeyError` and the refresh
runner reports `skipped_no_key`; any failed request surfaces as a per-source
`error` (R20). The adapter owns its slug → CBSA-code map per R11.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from domain.models import MetricRow
from infrastructure.enrichment.refresh import MissingApiKeyError

logger = logging.getLogger(__name__)

VINTAGE = 2023  # latest published ACS 5-year vintage at build time
API_URL = f"https://api.census.gov/data/{VINTAGE}/acs/acs5"
_TIMEOUT_S = 30.0
_GEO = "metropolitan statistical area/micropolitan statistical area"
_VARIABLES: dict[str, str] = {  # ACS variable -> market_metrics metric name
    "B01003_001E": "population",
    "B19013_001E": "median_income",
}

# Canonical metro slug -> CBSA code (R11). Markets without their own CBSA use
# the covering metro, mirroring zillow.py's REGION_MAP.
GEO_MAP: dict[str, str] = {
    "nashville-tn": "34980",
    "chattanooga-tn": "16860",
    "tucson-az": "46060",
    "fayetteville-ar": "22220",
    "colorado-springs-co": "17820",
    "boise-id": "14260",
    "joshua-tree-ca": "40140",   # Riverside-San Bernardino-Ontario
    "gatlinburg-tn": "42940",    # Sevierville
    "gulf-shores-al": "19300",   # Daphne-Fairhope-Foley
}


def _latest_complete_month(now: datetime) -> str:
    """'YYYY-MM' of the month before `now` — ACS is annual, so rows are stamped
    with the latest complete month to stay inside the repo's recent-months window."""
    year, month = (now.year, now.month - 1) if now.month > 1 else (now.year - 1, 12)
    return f"{year:04d}-{month:02d}"


class CensusSource:
    """ACS 5-year population and median-income behind the MarketDataSource port."""

    name = "census_acs"

    def __init__(self, api_key: str | None,
                 transport: httpx.BaseTransport | None = None) -> None:
        """Hold the (possibly absent) key; `transport` lets tests mock the API (R25)."""
        self._api_key = api_key
        self._transport = transport

    def fetch(self, metros: list[str]) -> list[MetricRow]:
        """Population and median-income rows per mapped metro from one ACS request."""
        if not self._api_key:
            raise MissingApiKeyError("CENSUS_API_KEY unset")
        cbsa_to_metro = {GEO_MAP[m]: m for m in metros if m in GEO_MAP}
        if not cbsa_to_metro:
            return []
        with httpx.Client(transport=self._transport, timeout=_TIMEOUT_S) as client:
            response = client.get(API_URL, params={
                "get": "NAME," + ",".join(_VARIABLES),
                "for": f"{_GEO}:{','.join(sorted(cbsa_to_metro))}",
                "key": self._api_key,
            })
            response.raise_for_status()
        rows = self._parse(response.json(), cbsa_to_metro)
        logger.info("census_fetched metros=%d rows=%d", len(cbsa_to_metro), len(rows))
        return rows

    def _parse(self, matrix: list[list[str | None]],
               cbsa_to_metro: dict[str, str]) -> list[MetricRow]:
        """Turn the Census header+rows matrix into MetricRows, dropping sentinels."""
        as_of = datetime.now(UTC)
        month = _latest_complete_month(as_of)
        header, *records = matrix
        index = {column: header.index(column) for column in (*_VARIABLES, _GEO)}
        rows: list[MetricRow] = []
        for record in records:
            metro = cbsa_to_metro.get(str(record[index[_GEO]]))
            if metro is None:
                continue
            for variable, metric in _VARIABLES.items():
                raw = record[index[variable]]
                if raw is None or float(raw) < 0:
                    continue  # Census encodes suppressed values as null or negative sentinels
                rows.append(MetricRow(metro=metro, month=month, source=self.name,
                                      metric=metric, value=float(raw), as_of=as_of))
        return rows
