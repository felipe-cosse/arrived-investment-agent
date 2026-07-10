"""Tests for seed purging: SEED_OFFERING_IDS and OfferingsRepo.purge_seed_data.

Seed demo data is an offline test fixture (amended R21): the runtime never
displays it. Boot (default settings) and the live catalogue refresh both call
`purge_seed_data`, which DELETEs the seed offerings, their return history, and
every `source='seed'` metric row — keeping `market_aliases`, whose raw-market
to metro mappings are factual and shared with real listings.
"""

from __future__ import annotations

from datetime import UTC, datetime

from domain.models import MetricRow, Offering, ReturnRecord
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.seed import SEED_OFFERING_IDS


def test_seed_offering_ids_match_seeded_rows(repo: OfferingsRepo) -> None:
    """The exported tuple names exactly the 11 rows the seeder writes, in §10 order."""
    assert len(SEED_OFFERING_IDS) == 11
    assert set(SEED_OFFERING_IDS) == {o.id for o in repo.list_offerings()}
    assert SEED_OFFERING_IDS[0] == "sfr-meridian"
    assert SEED_OFFERING_IDS[-1] == "fund-credit"


def test_purge_deletes_offerings_returns_and_seed_metrics(repo: OfferingsRepo) -> None:
    """Seed rows are gone from every table except market_aliases, which survives."""
    assert repo.purge_seed_data(SEED_OFFERING_IDS) == 11
    assert repo.list_offerings() == []
    assert all(repo.get_returns(oid, 60) == [] for oid in SEED_OFFERING_IDS)
    stats = repo.stats()
    assert stats["offerings"]["rows"] == 0
    assert stats["historical_returns"]["rows"] == 0
    assert stats["market_metrics"]["rows"] == 0  # seeded metrics are all source='seed'
    # Aliases are factual raw-market -> metro mappings; live listings reuse them (R11).
    assert repo.get_metro_for_market("Nashville, TN") == "nashville-tn"
    assert repo.get_metro_for_market("Fayetteville, AR") == "fayetteville-ar"


def test_purge_is_idempotent(repo: OfferingsRepo) -> None:
    """A second purge finds nothing to delete and reports zero offerings removed."""
    assert repo.purge_seed_data(SEED_OFFERING_IDS) == 11
    assert repo.purge_seed_data(SEED_OFFERING_IDS) == 0
    assert repo.list_offerings() == []


def test_purge_keeps_live_rows(repo: OfferingsRepo) -> None:
    """Only the named seed ids and source='seed' metrics go; live data survives."""
    now = datetime.now(UTC)
    repo.upsert_offerings([Offering(
        id="arrived-maple", name="The Maple", market="Nashville, TN",
        property_type="single_family", status="available", share_price_usd=10.0,
        min_investment_usd=100.0, projected_dividend_yield=0.05,
        projected_appreciation=0.03, as_of=now)])
    repo.upsert_returns([ReturnRecord(offering_id="arrived-maple", month="2026-05",
                                      dividend_per_share=0.04, share_value_usd=10.1)])
    repo.upsert_market_metrics([MetricRow(metro="nashville-tn", month="2026-05",
                                          source="fred", metric="unemployment_rate",
                                          value=3.4, as_of=now)])
    assert repo.purge_seed_data(SEED_OFFERING_IDS) == 11
    assert [o.id for o in repo.list_offerings()] == ["arrived-maple"]
    assert len(repo.get_returns("arrived-maple", 60)) == 1
    live_metrics = repo.get_market_metrics("nashville-tn", 60)
    assert {m.source for m in live_metrics} == {"fred"}


def test_purge_empty_ids_still_clears_seed_metrics(repo: OfferingsRepo) -> None:
    """No ids means no offerings deleted, but stale source='seed' metrics still go."""
    assert repo.purge_seed_data([]) == 0
    assert repo.stats()["market_metrics"]["rows"] == 0
    assert len(repo.list_offerings()) == 11  # offerings untouched without ids
