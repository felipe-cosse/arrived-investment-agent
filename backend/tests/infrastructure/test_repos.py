"""Behavioral tests for the DuckDB adapters (spec §12).

Covers: upsert idempotency (seed twice, same counts — R8), the offering→metro
alias join (R11), UTC timestamp persistence (R10), plans save/list/get/delete,
and saved-snapshot immutability (R16: a later enrichment refresh must not
change a stored plan).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from domain.models import MetricRow, PlanRecord
from infrastructure.duckdb.connection import DuckDBConn
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.duckdb.plans_repo import PlansRepo
from infrastructure.seed import seed_all


def _record(plan_id: str, created_at: datetime, name: str | None = None) -> PlanRecord:
    """A minimal but realistic snapshot record for CRUD tests."""
    return PlanRecord(
        id=plan_id,
        name=name,
        created_at=created_at,
        inputs={"amount": 2000, "risk_profile": "balanced", "horizon_years": 5},
        output={
            "feasible": True,
            "positions": [{"offering_id": "sfr-meridian", "amount_usd": 500}],
        },
        data_as_of=created_at,
    )


# -- upsert idempotency (R8) --------------------------------------------------


def test_seed_twice_same_counts(repo: OfferingsRepo) -> None:
    """Re-running the seeder over a seeded database changes no row counts."""
    first = repo.stats()
    counts = seed_all(repo)  # second run; conftest fixture already seeded once
    second = repo.stats()
    assert counts["offerings"] == 11
    for table in ("offerings", "historical_returns", "market_metrics"):
        assert second[table]["rows"] == first[table]["rows"]


def test_upsert_updates_in_place(repo: OfferingsRepo) -> None:
    """Upserting an existing id updates the row instead of duplicating it."""
    before = repo.get_offering("sfr-meridian")
    assert before is not None
    updated = before.model_copy(update={"projected_dividend_yield": 0.099})
    assert repo.upsert_offerings([updated]) == 1
    after = repo.get_offering("sfr-meridian")
    assert after is not None
    assert after.projected_dividend_yield == 0.099
    assert len(repo.list_offerings()) == 11  # still exactly one row per id


def test_upsert_alias_idempotent(repo: OfferingsRepo) -> None:
    """Re-upserting an existing alias neither errors nor breaks resolution."""
    assert repo.upsert_market_aliases([("Nashville, TN", "nashville-tn")]) == 1
    assert repo.get_metro_for_market("Nashville, TN") == "nashville-tn"


# -- alias join (R11) ----------------------------------------------------------


def test_alias_join_resolves_every_non_fund_market(repo: OfferingsRepo) -> None:
    """Every non-fund offering market resolves to a metro that has seeded metrics."""
    offerings = repo.list_offerings()
    assert len(offerings) == 11
    for offering in offerings:
        if offering.property_type == "fund":
            continue
        metro = repo.get_metro_for_market(offering.market)
        assert metro is not None, f"no alias for {offering.market}"
        metrics = repo.get_market_metrics(metro, 24)
        assert metrics, f"no enrichment rows for {offering.market} -> {metro}"
        assert {m.metric for m in metrics} >= {"home_value_index", "rent_index"}


def test_alias_unknown_market_resolves_to_none(repo: OfferingsRepo) -> None:
    """An unmapped raw market yields None rather than an inline string match."""
    assert repo.get_metro_for_market("Metropolis, KS") is None


# -- UTC timestamps (R10) --------------------------------------------------------


def test_connection_pins_utc_session_timezone(conn: DuckDBConn) -> None:
    """The session TimeZone is UTC so TIMESTAMPTZ→TIMESTAMP casts never use host time."""
    row = conn.cursor().execute("SELECT current_setting('TimeZone')").fetchone()
    assert row == ("UTC",)


def test_tz_aware_timestamp_round_trips_as_utc(plans: PlansRepo) -> None:
    """A tz-aware created_at is stored and read back as its exact UTC instant."""
    eastern = datetime(2026, 7, 9, 13, 3, 9, tzinfo=timezone(timedelta(hours=-5)))
    plans.save(_record("plan-utc", eastern))
    got = plans.get_plan("plan-utc")
    assert got is not None
    assert got.created_at == datetime(2026, 7, 9, 18, 3, 9, tzinfo=UTC)  # re-tagged UTC on read
    assert got.data_as_of == datetime(2026, 7, 9, 18, 3, 9, tzinfo=UTC)


def test_read_timestamps_serialize_with_utc_offset(repo: OfferingsRepo,
                                                   plans: PlansRepo) -> None:
    """Every read-path timestamp carries an explicit UTC offset (R10 read path).

    Offset-less ISO strings parse as *local* time in JS Date, which would skew
    the frontend StalenessBadge; +00:00 must survive serialization.
    """
    plans.save(_record("plan-tz", datetime(2026, 4, 1, tzinfo=UTC)))
    summary = plans.list_plans()[0]
    assert summary["created_at"].endswith("+00:00")
    assert summary["data_as_of"].endswith("+00:00")
    stats = repo.stats()
    for table in ("offerings", "market_metrics"):
        latest = stats[table]["latest_as_of"]
        assert latest.utcoffset() == timedelta(0), table
    offering = repo.get_offering("sfr-meridian")
    assert offering is not None
    assert offering.as_of.utcoffset() == timedelta(0)
    assert all(o.as_of.utcoffset() == timedelta(0) for o in repo.list_offerings())
    metrics = repo.get_market_metrics("nashville-tn", 24)
    assert metrics
    assert all(m.as_of.utcoffset() == timedelta(0) for m in metrics)


# -- plans CRUD ----------------------------------------------------------------


def test_plans_save_and_get_roundtrip(plans: PlansRepo) -> None:
    """Save returns the id and get_plan round-trips inputs/output JSON intact."""
    record = _record("plan-1", datetime(2026, 1, 15, 12, 0, tzinfo=UTC), name="First")
    assert plans.save(record) == "plan-1"
    got = plans.get_plan("plan-1")
    assert got is not None
    assert got.id == "plan-1"
    assert got.name == "First"
    assert got.inputs == record.inputs
    assert got.output == record.output


def test_plans_list_newest_first_summaries(plans: PlansRepo) -> None:
    """list_plans returns newest-first summaries without the full output blob."""
    plans.save(_record("plan-old", datetime(2026, 1, 1, tzinfo=UTC)))
    plans.save(_record("plan-new", datetime(2026, 2, 1, tzinfo=UTC), name="Newer"))
    listed = plans.list_plans()
    assert [p["id"] for p in listed] == ["plan-new", "plan-old"]
    assert all("output" not in p for p in listed)
    assert listed[0]["name"] == "Newer"
    assert listed[0]["inputs"]["amount"] == 2000


def test_plans_delete(plans: PlansRepo) -> None:
    """delete_plan removes the row once and reports False afterwards."""
    plans.save(_record("plan-del", datetime(2026, 3, 1, tzinfo=UTC)))
    assert plans.delete_plan("plan-del") is True
    assert plans.get_plan("plan-del") is None
    assert plans.delete_plan("plan-del") is False


def test_plans_stats_counts_rows(plans: PlansRepo) -> None:
    """stats reports the plans row count for /api/meta."""
    assert plans.stats() == {"rows": 0}
    plans.save(_record("plan-a", datetime(2026, 1, 1, tzinfo=UTC)))
    assert plans.stats() == {"rows": 1}


def test_get_unknown_plan_is_none(plans: PlansRepo) -> None:
    """get_plan returns None for an id that was never saved."""
    assert plans.get_plan("no-such-plan") is None


# -- snapshot immutability (R16) -------------------------------------------------


def test_snapshot_unchanged_by_metric_refresh(repo: OfferingsRepo, plans: PlansRepo) -> None:
    """A market-metrics refresh after saving must not alter the stored snapshot."""
    plans.save(_record("plan-frozen", datetime(2026, 1, 1, tzinfo=UTC), name="Frozen"))
    before = plans.get_plan("plan-frozen")
    assert before is not None
    refreshed = MetricRow(
        metro="nashville-tn",
        month="2026-06",
        source="zillow_zhvi",
        metric="home_value_index",
        value=131.5,
        as_of=datetime.now(UTC),
    )
    assert repo.upsert_market_metrics([refreshed]) == 1
    after = plans.get_plan("plan-frozen")
    assert after == before
    assert after is not None
    assert after.output == before.output
    assert after.data_as_of == before.data_as_of
