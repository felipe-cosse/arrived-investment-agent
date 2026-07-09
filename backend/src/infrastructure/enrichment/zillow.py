"""Zillow Research public-CSV adapter: ZHVI home values and ZORI rents (§10).

One `ZillowSource` instance serves one CSV/metric pair, so the composition root
wires two instances (`zillow_zhvi` → home_value_index, `zillow_zori` →
rent_index). No API key is required; URLs are env-overridable (§13). The
adapter owns its slug → Zillow RegionName map per R11, and the UI footer
carries the required "Data: Zillow Research" attribution.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import UTC, datetime

import httpx

from domain.models import MetricRow

logger = logging.getLogger(__name__)

# Canonical research-CSV defaults (§13): applied by `build_sources` whenever no
# ZILLOW_*_URL override is configured — Settings and the stopped-API CLI both
# pass None through, so only infrastructure ever names these URLs (R3).
ZHVI_DEFAULT_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zhvi/"
    "Metro_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv"
)
ZORI_DEFAULT_URL = (
    "https://files.zillowstatic.com/research/public_csvs/zori/"
    "Metro_zori_uc_sfrcondo_sm_sa_month.csv"
)

# Latest month plus 12 back fits the YoY window (§7) with margin; keeping the
# emitted history bounded also keeps annual census rows inside the repo's
# recent-months read window.
MONTHS_KEPT = 25
_TIMEOUT_S = 60.0  # the ZHVI research CSV is tens of MB
_DATE_COLUMN = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Canonical metro slug -> Zillow metro RegionName (R11). Offering markets that
# are not themselves Zillow metros map to the metro that covers them:
# Joshua Tree sits in San Bernardino County (Riverside metro), Gatlinburg in
# Sevier County (Sevierville metro), Gulf Shores in Baldwin County (Daphne metro).
REGION_MAP: dict[str, str] = {
    "nashville-tn": "Nashville, TN",
    "chattanooga-tn": "Chattanooga, TN",
    "tucson-az": "Tucson, AZ",
    "fayetteville-ar": "Fayetteville, AR",
    "colorado-springs-co": "Colorado Springs, CO",
    "boise-id": "Boise City, ID",
    "joshua-tree-ca": "Riverside, CA",
    "gatlinburg-tn": "Sevierville, TN",
    "gulf-shores-al": "Daphne, AL",
}


class ZillowSource:
    """One Zillow research CSV (ZHVI or ZORI) behind the MarketDataSource port."""

    def __init__(self, name: str, url: str, metric: str,
                 transport: httpx.BaseTransport | None = None) -> None:
        """`name` doubles as the market_metrics source tag; `transport` lets tests mock (R25)."""
        self.name = name
        self._url = url
        self._metric = metric
        self._transport = transport

    def fetch(self, metros: list[str]) -> list[MetricRow]:
        """Download the CSV and emit recent monthly rows for the mapped, requested metros."""
        wanted = {REGION_MAP[m]: m for m in metros if m in REGION_MAP}
        with httpx.Client(transport=self._transport, timeout=_TIMEOUT_S,
                          follow_redirects=True) as client:
            response = client.get(self._url)
            response.raise_for_status()
        rows = self._parse(response.text, wanted)
        logger.info("zillow_fetched source=%s regions=%d rows=%d",
                    self.name, len(wanted), len(rows))
        return rows

    def _parse(self, text: str, wanted: dict[str, str]) -> list[MetricRow]:
        """Rows for wanted RegionNames over the MONTHS_KEPT most recent month columns."""
        as_of = datetime.now(UTC)
        reader = csv.DictReader(io.StringIO(text))
        date_columns = sorted(c for c in (reader.fieldnames or []) if _DATE_COLUMN.match(c))
        rows: list[MetricRow] = []
        for record in reader:
            metro = wanted.get(record.get("RegionName", ""))
            if metro is None:
                continue
            for column in date_columns[-MONTHS_KEPT:]:
                cell = (record.get(column) or "").strip()
                if not cell:
                    continue  # Zillow leaves months blank before a region's coverage starts
                rows.append(MetricRow(metro=metro, month=column[:7], source=self.name,
                                      metric=self._metric, value=float(cell), as_of=as_of))
        return rows
