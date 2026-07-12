"""Coverage-map regressions for markets in the current buyable Arrived catalogue."""

from __future__ import annotations

import httpx

from infrastructure.enrichment.census import GEO_MAP, CensusSource
from infrastructure.enrichment.fred import SERIES_MAP, FredSource
from infrastructure.enrichment.zillow import REGION_MAP, ZORI_DEFAULT_URL, ZillowSource

CURRENT_ZILLOW_REGIONS: dict[str, str] = {
    "albuquerque-nm": "Albuquerque, NM",
    "fort-smith-ar": "Fort Smith, AR",
    "goshen-oh": "Cincinnati, OH",
    "knoxville-tn": "Knoxville, TN",
    "louisville-ky": "Louisville, KY",
    "lynnwood-wa": "Seattle, WA",
    "nesbit-ms": "Memphis, TN",
    "ooltewah-tn": "Chattanooga, TN",
    "southaven-ms": "Memphis, TN",
}
CURRENT_CENSUS_CBSAS: dict[str, str] = {
    "albuquerque-nm": "10740",
    "fort-smith-ar": "22900",
    "goshen-oh": "17140",
    "knoxville-tn": "28940",
    "louisville-ky": "31140",
    "lynnwood-wa": "42660",
    "nesbit-ms": "32820",
    "ooltewah-tn": "16860",
    "southaven-ms": "32820",
}
CURRENT_FRED_SERIES: dict[str, str] = {
    "albuquerque-nm": "LAUMT351074000000003",
    "fort-smith-ar": "LAUMT052290000000003",
    "goshen-oh": "LAUMT391714000000003",
    "knoxville-tn": "LAUMT472894000000003",
    "louisville-ky": "LAUMT213114000000003",
    "lynnwood-wa": "LAUMT534266000000003",
    "nesbit-ms": "LAUMT473282000000003",
    "ooltewah-tn": "LAUMT471686000000003",
    "southaven-ms": "LAUMT473282000000003",
}


def test_current_buyable_markets_have_verified_provider_identifiers() -> None:
    """Every current market maps to the exact Zillow, Census, and FRED identifier."""
    assert {slug: REGION_MAP[slug] for slug in CURRENT_ZILLOW_REGIONS} == CURRENT_ZILLOW_REGIONS
    assert {slug: GEO_MAP[slug] for slug in CURRENT_CENSUS_CBSAS} == CURRENT_CENSUS_CBSAS
    assert {slug: SERIES_MAP[slug] for slug in CURRENT_FRED_SERIES} == CURRENT_FRED_SERIES


def test_zori_default_uses_current_all_homes_plus_multifamily_download() -> None:
    assert ZORI_DEFAULT_URL.endswith("/Metro_zori_uc_sfrcondomfr_sm_sa_month.csv")


def test_zillow_fans_shared_memphis_row_out_to_both_market_slugs() -> None:
    body = (
        "RegionID,SizeRank,RegionName,RegionType,StateName,2026-06-30\n"
        '1,1,"Memphis, TN",msa,TN,1510.0\n'
    )
    source = ZillowSource(
        "zillow_zori",
        "https://zillow.test/zori.csv",
        "rent_index",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text=body)),
    )
    rows = source.fetch(["nesbit-ms", "southaven-ms"])
    assert {(row.metro, row.value) for row in rows} == {
        ("nesbit-ms", 1510.0),
        ("southaven-ms", 1510.0),
    }


def test_census_fans_shared_memphis_row_out_to_both_market_slugs() -> None:
    matrix = [
        ["NAME", "B01003_001E", "B19013_001E",
         "metropolitan statistical area/micropolitan statistical area"],
        ["Memphis, TN-MS-AR", "1337000", "68000", "32820"],
    ]
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=matrix)

    source = CensusSource("test-key", transport=httpx.MockTransport(handler))
    rows = source.fetch(["nesbit-ms", "southaven-ms"])
    assert len(seen) == 1
    assert seen[0].url.params["for"].endswith(":32820")
    assert {(row.metro, row.metric) for row in rows} == {
        ("nesbit-ms", "population"),
        ("nesbit-ms", "median_income"),
        ("southaven-ms", "population"),
        ("southaven-ms", "median_income"),
    }


def test_fred_fetches_shared_memphis_series_once_and_fans_out() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={
            "observations": [{"date": "2026-06-01", "value": "4.2"}],
        })

    source = FredSource("test-key", transport=httpx.MockTransport(handler))
    rows = source.fetch(["nesbit-ms", "southaven-ms"])
    assert len(seen) == 1
    assert seen[0].url.params["series_id"] == "LAUMT473282000000003"
    assert {(row.metro, row.value) for row in rows} == {
        ("nesbit-ms", 4.2),
        ("southaven-ms", 4.2),
    }
