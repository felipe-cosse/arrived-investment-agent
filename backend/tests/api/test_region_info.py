"""API contract for offering public-region information."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from domain.models import MetricRow


def test_region_info_endpoint_is_source_backed_and_offline(tmp_path: Path) -> None:
    app = create_app(Settings(anthropic_api_key=None, db_path=tmp_path / "api.duckdb",
                              seed_demo_data=True))
    with TestClient(app) as client:
        app.state.arrived.offerings.upsert_market_metrics([
            MetricRow(metro="nashville-tn", month="2024-12", source="census_acs",
                      metric="median_income", value=78_500,
                      as_of=datetime(2026, 7, 1, tzinfo=UTC)),
        ])
        response = client.get("/api/offerings/sfr-meridian/region-info")
        missing = client.get("/api/offerings/not-real/region-info")

    assert response.status_code == 200
    body = response.json()
    assert body["offering_id"] == "sfr-meridian" and body["market"] == "Nashville, TN"
    assert body["metrics"] == [{
        "metric": "median_income",
        "label": "Median household income",
        "value": 78_500.0,
        "unit": "usd_per_year",
        "observation_month": "2024-12",
        "retrieved_at": "2026-07-01T00:00:00+00:00",
        "source": {
            "id": "census_acs",
            "name": "U.S. Census Bureau ACS 5-year",
            "url": "https://api.census.gov/data/2024/acs/acs5/groups/B19013.html",
        },
    }]
    assert missing.status_code == 404
