"""Refresh-runner tests over a tmp DuckDB and httpx.MockTransport (R25).

The MockTransport serves the Task-1 fixtures as the catalogue API; no test
touches the network. Covers the design doc's contract: success report counts +
seed retirement + idempotency, per-offering share-price failure isolation,
catalogue failure leaving the table untouched, the zero-buyable error, and
catalogue pagination.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from infrastructure.arrived.fetcher import ArrivedCatalogue
from infrastructure.arrived.refresh import refresh_offerings
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from tests.infrastructure.arrived_fixtures import (
    CATALOGUE,
    COMING_SOON_OFFERING,
    FUNDED_OFFERING,
    SHARE_PRICES,
)

BASE = "https://arrived.test"
LIVE_IDS = {"arrived-maple", "arrived-birch", "arrived-dune", "arrived-haven-fund"}
SUCCESS_REPORT = {"status": "upserted", "offerings": 4, "returns": 8,
                  "aliases": 3, "seeds_retired": 11, "share_price_failures": 0}


def _api_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/offerings/search":
        return httpx.Response(200, json={
            "pagination": {"totalResults": len(CATALOGUE)}, "data": CATALOGUE})
    if path.startswith("/offerings/") and path.endswith("/share-prices"):
        return httpx.Response(200, json=SHARE_PRICES.get(path.split("/")[2], []))
    return httpx.Response(404)


def _catalogue(handler: Callable[[httpx.Request], httpx.Response] = _api_handler,
               ) -> ArrivedCatalogue:
    return ArrivedCatalogue(BASE, transport=httpx.MockTransport(handler))


def test_refresh_upserts_buyable_and_retires_seeds(repo: OfferingsRepo) -> None:
    assert refresh_offerings(_catalogue(), repo=repo) == SUCCESS_REPORT
    statuses = {o.id: o.status for o in repo.list_offerings()}
    assert {oid for oid in statuses if oid.startswith("arrived-")} == LIVE_IDS
    assert all(statuses[oid] == "available" for oid in LIVE_IDS)
    assert all(status == "closed" for oid, status in statuses.items() if oid not in LIVE_IDS)


def test_refresh_is_idempotent_on_a_second_run(repo: OfferingsRepo) -> None:
    assert refresh_offerings(_catalogue(), repo=repo) == SUCCESS_REPORT
    assert refresh_offerings(_catalogue(), repo=repo) == SUCCESS_REPORT
    assert len(repo.list_offerings()) == 15  # 11 closed seeds + 4 live rows, no dupes


def test_share_price_failure_falls_back_and_run_continues(repo: OfferingsRepo) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/offerings/maple/share-prices":
            return httpx.Response(500)
        return _api_handler(request)

    report = refresh_offerings(_catalogue(handler), repo=repo)
    assert report["status"] == "upserted" and report["offerings"] == 4
    maple = repo.get_offering("arrived-maple")
    assert maple is not None and maple.status == "available"
    # No offering has a usable history left -> the mapper's final 0.0 fallback.
    assert maple.projected_appreciation == 0.0
    assert report["seeds_retired"] == 11
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
