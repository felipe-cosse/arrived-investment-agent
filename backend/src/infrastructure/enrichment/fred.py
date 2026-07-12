"""FRED metro-unemployment adapter (§10): requires FRED_API_KEY.

Fetches the monthly unemployment rate for each mapped metro from the FRED
`series/observations` endpoint. A missing key raises `MissingApiKeyError`, which
the refresh runner reports as `skipped_no_key` (§9/§13). The adapter owns its
slug → series-id map per R11.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from domain.models import MetricRow
from infrastructure.enrichment.refresh import MissingApiKeyError

logger = logging.getLogger(__name__)

API_URL = "https://api.stlouisfed.org/fred/series/observations"
MONTHS_KEPT = 25  # same recent window as zillow.py; enough for display + freshness
_TIMEOUT_S = 30.0
_MISSING_VALUE = "."  # FRED's placeholder for an absent observation

# Canonical metro slug -> FRED series id (R11). These are the BLS LAUS metro
# unemployment-rate series FRED mirrors: LAUMT + state FIPS + CBSA + "000000" + "03"
# (measure 03 = unemployment rate, not seasonally adjusted). Markets without
# their own CBSA use the covering metro, mirroring zillow.py's REGION_MAP.
SERIES_MAP: dict[str, str] = {
    "albuquerque-nm": "LAUMT351074000000003",     # Albuquerque 10740
    "fort-smith-ar": "LAUMT052290000000003",      # Fort Smith 22900
    "goshen-oh": "LAUMT391714000000003",          # Cincinnati 17140
    "knoxville-tn": "LAUMT472894000000003",       # Knoxville 28940
    "louisville-ky": "LAUMT213114000000003",      # Louisville 31140
    "lynnwood-wa": "LAUMT534266000000003",        # Seattle 42660
    "nesbit-ms": "LAUMT473282000000003",          # Memphis 32820
    "ooltewah-tn": "LAUMT471686000000003",        # Chattanooga 16860
    "southaven-ms": "LAUMT473282000000003",       # Memphis 32820
    "nashville-tn": "LAUMT473498000000003",       # Nashville-Davidson--Murfreesboro 34980
    "chattanooga-tn": "LAUMT471686000000003",     # Chattanooga 16860
    "tucson-az": "LAUMT044606000000003",          # Tucson 46060
    "fayetteville-ar": "LAUMT052222000000003",    # Fayetteville-Springdale-Rogers 22220
    "colorado-springs-co": "LAUMT081782000000003",  # Colorado Springs 17820
    "boise-id": "LAUMT161426000000003",           # Boise City 14260
    "joshua-tree-ca": "LAUMT064014000000003",     # Riverside-San Bernardino 40140
    "gatlinburg-tn": "LAUMT474294000000003",      # Sevierville 42940
    "gulf-shores-al": "LAUMT011930000000003",     # Daphne-Fairhope-Foley 19300
}


class FredSource:
    """FRED unemployment-rate observations behind the MarketDataSource port."""

    name = "fred"

    def __init__(self, api_key: str | None,
                 transport: httpx.BaseTransport | None = None) -> None:
        """Hold the (possibly absent) key; `transport` lets tests mock the API (R25)."""
        self._api_key = api_key
        self._transport = transport

    def fetch(self, metros: list[str]) -> list[MetricRow]:
        """Recent unemployment-rate rows per mapped metro; raises when the key is unset."""
        if not self._api_key:
            raise MissingApiKeyError("FRED_API_KEY unset")
        as_of = datetime.now(UTC)
        rows: list[MetricRow] = []
        series_to_metros: dict[str, list[str]] = {}
        for metro in metros:
            series_id = SERIES_MAP.get(metro)
            if series_id is not None:
                series_to_metros.setdefault(series_id, []).append(metro)
        with httpx.Client(transport=self._transport, timeout=_TIMEOUT_S) as client:
            for series_id, mapped_metros in series_to_metros.items():
                rows.extend(self._series(client, mapped_metros, series_id, as_of))
        logger.info("fred_fetched metros=%d rows=%d", len({r.metro for r in rows}), len(rows))
        return rows

    def _series(self, client: httpx.Client, metros: list[str], series_id: str,
                as_of: datetime) -> list[MetricRow]:
        """Fetch one series and keep its most recent non-missing observations."""
        response = client.get(API_URL, params={
            "series_id": series_id, "api_key": self._api_key or "",
            "file_type": "json", "sort_order": "asc",
        })
        response.raise_for_status()
        observations = response.json()["observations"][-MONTHS_KEPT:]
        return [MetricRow(metro=metro, month=str(obs["date"])[:7], source=self.name,
                          metric="unemployment_rate", value=float(obs["value"]), as_of=as_of)
                for obs in observations if obs["value"] != _MISSING_VALUE for metro in metros]
