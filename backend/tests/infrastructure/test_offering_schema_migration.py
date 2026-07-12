"""Regression coverage for upgrading a pre-detail offerings table in place."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb

from domain.models import Offering
from infrastructure.duckdb.connection import DuckDBConn
from infrastructure.duckdb.offerings_repo import OfferingsRepo

_LEGACY_SCHEMA = """
CREATE TABLE offerings (
    id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, market VARCHAR NOT NULL,
    property_type VARCHAR NOT NULL, status VARCHAR NOT NULL,
    share_price_usd DOUBLE NOT NULL, min_investment_usd DOUBLE NOT NULL,
    projected_dividend_yield DOUBLE NOT NULL, projected_appreciation DOUBLE NOT NULL,
    funded_pct DOUBLE, property_value_usd DOUBLE, leverage_pct DOUBLE,
    as_of TIMESTAMP NOT NULL
)
"""


def test_connection_adds_optional_detail_columns_to_legacy_database(tmp_path: Path) -> None:
    path = tmp_path / "legacy.duckdb"
    legacy = duckdb.connect(str(path))
    legacy.execute(_LEGACY_SCHEMA)
    legacy.close()

    conn = DuckDBConn(path)
    repo = OfferingsRepo(conn)
    offering = Offering(
        id="arrived-test", name="Test", market="Test, TX", property_type="single_family",
        share_price_usd=10, min_investment_usd=100, projected_dividend_yield=0.04,
        projected_appreciation=0.03, source_url="https://arrived.com/properties/test",
        monthly_rent_usd=2_000, investor_count=300, as_of=datetime.now(UTC),
    )
    assert repo.upsert_offerings([offering]) == 1
    stored = repo.get_offering("arrived-test")
    assert stored is not None
    assert stored.source_url == offering.source_url
    assert stored.monthly_rent_usd == 2_000
    assert stored.investor_count == 300
    conn.close()
