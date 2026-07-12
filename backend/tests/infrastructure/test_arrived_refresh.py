"""Refresh-runner tests over a tmp DuckDB and httpx.MockTransport (R25).

The MockTransport serves the Task-1 fixtures as the catalogue API; no test
touches the network. Covers the design doc's contract: success report counts +
seed purge + idempotency, per-offering share-price failure isolation,
catalogue failure leaving the table untouched, the zero-buyable error, and
catalogue pagination.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from infrastructure.arrived.fetcher import ArrivedCatalogue
from infrastructure.arrived.refresh import refresh_offerings
from infrastructure.duckdb import catalogue_snapshot
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from tests.infrastructure.arrived_fixtures import (
    CATALOGUE,
    COMING_SOON_OFFERING,
    FUNDED_OFFERING,
    LTR_WITH_DIVIDEND,
    SHARE_PRICES,
)

BASE = "https://arrived.test"
LIVE_IDS = {"arrived-maple", "arrived-birch", "arrived-dune", "arrived-haven-fund"}
SUCCESS_REPORT = {"status": "upserted", "offerings": 4, "returns": 8,
                  "aliases": 3, "seeds_purged": 11, "share_price_failures": 0}
# The share-prices endpoint is addressed by numeric offering id, not shortName.
_SHORT_BY_ID = {str(item["id"]): str(item["shortName"]) for item in CATALOGUE}


def _api_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/offerings/search":
        return httpx.Response(200, json={
            "pagination": {"totalResults": len(CATALOGUE)}, "data": CATALOGUE})
    if path.startswith("/offerings/") and path.endswith("/share-prices"):
        short_name = _SHORT_BY_ID.get(path.split("/")[2])
        if short_name is None:
            return httpx.Response(400)  # the real API rejects non-numeric ids
        return httpx.Response(200, json={"data": SHARE_PRICES.get(short_name, [])})
    return httpx.Response(404)


def _catalogue(handler: Callable[[httpx.Request], httpx.Response] = _api_handler,
               ) -> ArrivedCatalogue:
    return ArrivedCatalogue(BASE, transport=httpx.MockTransport(handler))


def test_refresh_upserts_buyable_and_purges_seeds(repo: OfferingsRepo) -> None:
    assert refresh_offerings(_catalogue(), repo=repo) == SUCCESS_REPORT
    offerings = repo.list_offerings()
    assert {o.id for o in offerings} == LIVE_IDS  # seed rows are gone, not closed
    assert all(o.status == "available" for o in offerings)
    assert repo.get_returns("sfr-meridian", 60) == []  # seed history purged too
    assert repo.stats()["market_metrics"]["rows"] == 0  # source='seed' metrics gone
    assert repo.get_metro_for_market("Fayetteville, AR") == "fayetteville-ar"  # aliases kept


def test_refresh_is_idempotent_on_a_second_run(repo: OfferingsRepo) -> None:
    assert refresh_offerings(_catalogue(), repo=repo) == SUCCESS_REPORT
    second = refresh_offerings(_catalogue(), repo=repo)
    assert second == {**SUCCESS_REPORT, "seeds_purged": 0}  # nothing left to purge
    assert len(repo.list_offerings()) == 4  # live rows only, no dupes


def test_refresh_removes_live_offerings_absent_from_next_snapshot(repo: OfferingsRepo) -> None:
    assert refresh_offerings(_catalogue(), repo=repo)["status"] == "upserted"
    assert repo.get_returns("arrived-maple", 60)
    reduced = [item for item in CATALOGUE if item["shortName"] != "maple"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/offerings/search":
            return httpx.Response(200, json={
                "pagination": {"totalResults": len(reduced)}, "data": reduced})
        return _api_handler(request)

    report = refresh_offerings(_catalogue(handler), repo=repo)
    assert report["status"] == "upserted" and report["offerings"] == 3
    assert repo.get_offering("arrived-maple") is None
    assert repo.get_returns("arrived-maple", 60) == []


def test_refresh_rolls_back_every_write_on_mid_transaction_failure(
    repo: OfferingsRepo, monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert refresh_offerings(_catalogue(), repo=repo)["status"] == "upserted"
    baseline = repo.get_offering("arrived-maple")
    assert baseline is not None
    changed = [{**item, "name": "Changed Mid-Refresh"}
               if item["shortName"] == "maple" else item for item in CATALOGUE]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/offerings/search":
            return httpx.Response(200, json={
                "pagination": {"totalResults": len(changed)}, "data": changed})
        return _api_handler(request)

    original = catalogue_snapshot._upsert

    def fail_on_returns(*args: Any, **kwargs: Any) -> int:
        if args[1] == "historical_returns":
            raise RuntimeError("forced returns failure")
        return int(original(*args, **kwargs))

    monkeypatch.setattr(catalogue_snapshot, "_upsert", fail_on_returns)
    report = refresh_offerings(_catalogue(handler), repo=repo)
    assert report == {"status": "error", "detail": "forced returns failure"}
    current = repo.get_offering("arrived-maple")
    assert current is not None and current.name == baseline.name
    assert {offering.id for offering in repo.list_offerings()} == LIVE_IDS


def test_share_price_failure_falls_back_and_run_continues(repo: OfferingsRepo) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/offerings/{LTR_WITH_DIVIDEND['id']}/share-prices":
            return httpx.Response(500)
        return _api_handler(request)

    report = refresh_offerings(_catalogue(handler), repo=repo)
    assert report["status"] == "upserted" and report["offerings"] == 4
    maple = repo.get_offering("arrived-maple")
    assert maple is not None and maple.status == "available"
    # No offering has a usable history left -> the mapper's final 0.0 fallback.
    assert maple.projected_appreciation == 0.0
    assert report["seeds_purged"] == 11
    # R28: the degraded run is visible in the report, not just the logs.
    assert report["share_price_failures"] >= 1


def test_catalogue_failure_reports_error_and_writes_nothing(repo: OfferingsRepo) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    report = refresh_offerings(_catalogue(handler), repo=repo)
    assert report["status"] == "error" and "boom" in report["detail"]
    offerings = repo.list_offerings()
    assert len(offerings) == 11  # seeds only; nothing upserted
    assert all(o.status == "available" for o in offerings)


def test_zero_buyable_catalogue_reports_error_and_keeps_seeds(repo: OfferingsRepo) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/offerings/search":
            return httpx.Response(200, json={
                "pagination": {"totalResults": 2},
                "data": [FUNDED_OFFERING, COMING_SOON_OFFERING]})
        return httpx.Response(404)

    report = refresh_offerings(_catalogue(handler), repo=repo)
    assert report == {"status": "error", "detail": "no buyable offerings found"}
    assert all(o.status == "available" for o in repo.list_offerings())


def test_fetch_catalogue_follows_pagination_and_sends_polite_headers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/offerings/search"
        assert request.headers["accept"] == "application/json"
        assert "Mozilla" in request.headers["user-agent"]
        page = int(request.url.params["page"])
        pages = {1: CATALOGUE[:4], 2: CATALOGUE[4:]}
        return httpx.Response(200, json={
            "pagination": {"totalResults": len(CATALOGUE)}, "data": pages.get(page, [])})

    items = _catalogue(handler).fetch_catalogue()
    assert [item["shortName"] for item in items] == [item["shortName"] for item in CATALOGUE]
