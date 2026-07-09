"""Behavioral tests for the enrichment adapters (§10, R11, R20, R25).

Every adapter runs against an `httpx.MockTransport` or its skipped-by-key path;
the network is never touched. The refresh_all integration test uses the real
adapters over the seeded tmp DuckDB from conftest.
"""

from __future__ import annotations

import json
import re

import httpx
import pytest

from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.enrichment.census import CensusSource
from infrastructure.enrichment.fred import FredSource
from infrastructure.enrichment.refresh import MissingApiKeyError, build_sources, refresh_all
from infrastructure.enrichment.zillow import (
    MONTHS_KEPT,
    ZHVI_DEFAULT_URL,
    ZORI_DEFAULT_URL,
    ZillowSource,
)

ZHVI_URL = "https://zillow.test/zhvi.csv"


def _zillow_csv(dates: list[str], regions: dict[str, list[str]]) -> str:
    """A minimal wide-format Zillow research CSV with quoted RegionName values."""
    lines = [",".join(["RegionID", "SizeRank", "RegionName", "RegionType", "StateName", *dates])]
    for i, (region, values) in enumerate(regions.items()):
        lines.append(",".join([str(i), str(i), f'"{region}"', "msa", "ST", *values]))
    return "\n".join(lines)


def _csv_transport(body: str) -> httpx.MockTransport:
    return httpx.MockTransport(lambda request: httpx.Response(200, text=body))


# -- zillow ---------------------------------------------------------------------


def test_zillow_maps_filters_and_skips_blank_cells() -> None:
    body = _zillow_csv(
        ["2026-04-30", "2026-05-31", "2026-06-30"],
        {
            "Nashville, TN": ["101.5", "", "103.25"],   # mapped + requested; one blank month
            "Chattanooga, TN": ["90.0", "91.0", "92.0"],  # mapped but NOT requested
            "Nowhere, ST": ["1.0", "2.0", "3.0"],         # not in the region map
        },
    )
    source = ZillowSource("zillow_zhvi", ZHVI_URL, "home_value_index",
                          transport=_csv_transport(body))
    rows = source.fetch(["nashville-tn"])
    assert [(r.month, r.value) for r in rows] == [("2026-04", 101.5), ("2026-06", 103.25)]
    assert all(r.metro == "nashville-tn" for r in rows)
    assert all(r.source == "zillow_zhvi" and r.metric == "home_value_index" for r in rows)
    assert all(r.as_of.tzinfo is not None for r in rows)


def test_zillow_zori_tags_rent_index() -> None:
    body = _zillow_csv(["2026-06-30"], {"Tucson, AZ": ["1850.0"]})
    source = ZillowSource("zillow_zori", ZHVI_URL, "rent_index",
                          transport=_csv_transport(body))
    rows = source.fetch(["tucson-az"])
    assert [(r.source, r.metric, r.value) for r in rows] == [("zillow_zori", "rent_index", 1850.0)]


def test_zillow_keeps_only_recent_months() -> None:
    dates = [f"{2020 + i // 12:04d}-{i % 12 + 1:02d}-28" for i in range(MONTHS_KEPT + 5)]
    body = _zillow_csv(dates, {"Boise City, ID": ["100.0"] * len(dates)})
    source = ZillowSource("zillow_zhvi", ZHVI_URL, "home_value_index",
                          transport=_csv_transport(body))
    rows = source.fetch(["boise-id"])
    assert len(rows) == MONTHS_KEPT
    assert {r.month for r in rows} == {d[:7] for d in dates[-MONTHS_KEPT:]}


def test_zillow_http_error_propagates() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    source = ZillowSource("zillow_zhvi", ZHVI_URL, "home_value_index", transport=transport)
    with pytest.raises(httpx.HTTPStatusError):
        source.fetch(["nashville-tn"])


# -- fred -----------------------------------------------------------------------


def test_fred_without_key_raises_missing_key() -> None:
    with pytest.raises(MissingApiKeyError):
        FredSource(None).fetch(["nashville-tn"])


def test_fred_fetches_mapped_series_and_skips_missing_values() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        observations = [{"date": "2026-05-01", "value": "3.4"},
                        {"date": "2026-06-01", "value": "."}]  # "." = FRED missing
        return httpx.Response(200, json={"observations": observations})

    source = FredSource("test-key", transport=httpx.MockTransport(handler))
    rows = source.fetch(["nashville-tn", "not-a-mapped-metro"])
    assert len(seen) == 1  # unmapped metros never hit the API
    assert seen[0].params["api_key"] == "test-key"
    assert seen[0].params["series_id"]
    assert [(r.metro, r.month, r.value) for r in rows] == [("nashville-tn", "2026-05", 3.4)]
    assert rows[0].source == "fred" and rows[0].metric == "unemployment_rate"


# -- census -----------------------------------------------------------------------


def test_census_without_key_raises_missing_key() -> None:
    with pytest.raises(MissingApiKeyError):
        CensusSource(None).fetch(["nashville-tn"])


def test_census_parses_population_and_income_skipping_sentinels() -> None:
    matrix = [
        ["NAME", "B01003_001E", "B19013_001E",
         "metropolitan statistical area/micropolitan statistical area"],
        ["Nashville-Davidson--Murfreesboro--Franklin, TN", "2100000", "75000", "34980"],
        ["Tucson, AZ", "-666666666", "58000", "46060"],  # suppressed population sentinel
    ]
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=json.dumps(matrix)))
    source = CensusSource("test-key", transport=transport)
    rows = source.fetch(["nashville-tn", "tucson-az", "not-a-mapped-metro"])
    got = {(r.metro, r.metric): r.value for r in rows}
    assert got == {("nashville-tn", "population"): 2100000.0,
                   ("nashville-tn", "median_income"): 75000.0,
                   ("tucson-az", "median_income"): 58000.0}
    assert all(r.source == "census_acs" for r in rows)
    assert all(re.fullmatch(r"\d{4}-\d{2}", r.month) for r in rows)


# -- refresh integration (R20) ------------------------------------------------------


def test_refresh_all_with_real_adapters_isolates_failures(repo: OfferingsRepo) -> None:
    """One upserting source, one keyless, one erroring — statuses stay per-source."""
    body = _zillow_csv(["2026-06-30"], {"Nashville, TN": ["112.5"]})
    zhvi = ZillowSource("zillow_zhvi", ZHVI_URL, "home_value_index",
                        transport=_csv_transport(body))
    fred = FredSource(None)  # no key -> skipped_no_key
    census = CensusSource("test-key",
                          transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    results = refresh_all([zhvi, fred, census], reader=repo, writer=repo)
    assert results == {
        "zillow_zhvi": {"status": "upserted", "rows": 1},
        "fred": {"status": "skipped_no_key", "rows": 0},
        "census_acs": {"status": "error", "rows": 0},
    }
    stored = repo.get_market_metrics("nashville-tn", 25)
    assert any(m.source == "zillow_zhvi" and m.value == 112.5 for m in stored)


def test_build_sources_wires_all_four_providers() -> None:
    sources = build_sources(zhvi_url="https://z.test/zhvi.csv", zori_url="https://z.test/zori.csv",
                            fred_api_key=None, census_api_key=None)
    assert [s.name for s in sources] == ["zillow_zhvi", "zillow_zori", "fred", "census_acs"]


def test_build_sources_defaults_zillow_urls_when_unset() -> None:
    """None URLs (the Settings defaults, R3) fall back to the adapter's canonical CSVs."""
    sources = build_sources(zhvi_url=None, zori_url=None, fred_api_key=None, census_api_key=None)
    zhvi, zori = sources[0], sources[1]
    assert isinstance(zhvi, ZillowSource) and isinstance(zori, ZillowSource)
    assert zhvi._url == ZHVI_DEFAULT_URL
    assert zori._url == ZORI_DEFAULT_URL
