"""Source and freshness guarantees for public region information."""

from __future__ import annotations

from datetime import UTC, datetime

from domain.models import MetricRow
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from services.region_info_service import RegionInfoService


def _row(source: str, metric: str, month: str, value: float) -> MetricRow:
    return MetricRow(metro="nashville-tn", month=month, source=source,
                     metric=metric, value=value,
                     as_of=datetime(2026, 7, 1, tzinfo=UTC))


def test_region_info_returns_latest_public_rows_with_provenance(repo: OfferingsRepo) -> None:
    repo.upsert_market_metrics([
        _row("zillow_zhvi", "home_value_index", "2026-05", 350_000),
        _row("zillow_zhvi", "home_value_index", "2026-06", 355_000),
        _row("fred", "unemployment_rate", "2026-06", 3.2),
        _row("census_acs", "population", "2024-12", 2_100_000),
    ])

    result = RegionInfoService(repo).for_offering("sfr-meridian")

    assert result is not None and result["available"] is True
    assert result["metro"] == "nashville-tn" and result["scope"] == "metro_area"
    by_metric = {row["metric"]: row for row in result["metrics"]}
    assert by_metric["home_value_index"]["value"] == 355_000
    assert by_metric["home_value_index"]["observation_month"] == "2026-06"
    assert by_metric["home_value_index"]["source"]["url"].startswith("https://")
    assert by_metric["population"]["source"]["id"] == "census_acs"
    assert all(row["source"]["id"] != "seed" for row in result["metrics"])


def test_region_info_never_presents_seed_fixture_as_public_data(repo: OfferingsRepo) -> None:
    result = RegionInfoService(repo).for_offering("sfr-meridian")

    assert result is not None
    assert result["available"] is False and result["metrics"] == []
    assert "metro area" in result["disclaimer"]


def test_region_info_handles_unmapped_fund_and_unknown_offering(repo: OfferingsRepo) -> None:
    fund = RegionInfoService(repo).for_offering("fund-sfr")

    assert fund is not None and fund["metro"] is None and fund["available"] is False
    assert RegionInfoService(repo).for_offering("not-real") is None
