"""Live catalogue refresh: fetch buyable Arrived offerings and upsert them (§10).

The runner maps the entire catalogue BEFORE any write, so a fetch or mapping
failure reports `{"status": "error", "detail": ...}` with the database
untouched — including the zero-buyable case, which never retires seeds. One
offering's share-price fetch failing only costs that offering its direct
appreciation (the mapper's median fallback covers it; R20 spirit). Once at
least one live offering is upserted, the seed catalog retires (status →
'closed') — the spec's sanctioned R8 exception. The `python -m` CLI below is
for use only while the API is stopped: DuckDB has a single writer (R6).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from infrastructure.arrived.fetcher import ArrivedCatalogue
from infrastructure.arrived.mapper import BUYABLE_STATUSES, map_offerings
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.seed import SEED_OFFERING_IDS

logger = logging.getLogger(__name__)

DEFAULT_API_URL = "https://abacus.arrivedhomes.com"


def _share_prices(catalogue: ArrivedCatalogue,
                  buyable: list[dict[str, Any]],
                  ) -> tuple[dict[str, list[dict[str, Any]]], int]:
    """Histories keyed by shortName, plus the failed-fetch count (R28 visibility).

    A failed fetch logs, counts, and leaves the key absent, so that offering
    takes the mapper's median-appreciation fallback.
    """
    histories: dict[str, list[dict[str, Any]]] = {}
    failures = 0
    for item in buyable:
        short_name = str(item["shortName"])
        try:
            histories[short_name] = catalogue.fetch_share_prices(short_name)
        except Exception:
            failures += 1
            logger.exception("share_prices_failed short_name=%s", short_name)
    return histories, failures


def refresh_offerings(catalogue: ArrivedCatalogue, *, repo: OfferingsRepo) -> dict[str, Any]:
    """Fetch, map, then upsert the buyable catalogue; retire seeds on success.

    Report: `{"status": "upserted", "offerings", "returns", "aliases",
    "seeds_retired", "share_price_failures"}` on success (the failure count
    keeps degraded runs visible, R28); `{"status": "error", "detail"}` on any
    failure, with nothing written (design doc's error contract).
    """
    try:
        raw = catalogue.fetch_catalogue()
        buyable = [item for item in raw if item.get("status") in BUYABLE_STATUSES]
        histories, price_failures = _share_prices(catalogue, buyable)
        mapped = map_offerings(raw, histories, datetime.now(UTC))
        if not mapped.offerings:
            logger.warning("offerings_refresh_empty raw_items=%d", len(raw))
            return {"status": "error", "detail": "no buyable offerings found"}
        report: dict[str, Any] = {
            "status": "upserted",
            "offerings": repo.upsert_offerings(mapped.offerings),
            "returns": repo.upsert_returns(mapped.returns),
            "aliases": repo.upsert_market_aliases(mapped.aliases),
        }
        report["seeds_retired"] = (repo.close_offerings(SEED_OFFERING_IDS)
                                   if report["offerings"] else 0)
        report["share_price_failures"] = price_failures
    except Exception as exc:
        logger.exception("offerings_refresh_failed")
        return {"status": "error", "detail": str(exc)}
    logger.info("offerings_refreshed offerings=%d returns=%d aliases=%d seeds_retired=%d "
                "share_price_failures=%d",
                report["offerings"], report["returns"], report["aliases"],
                report["seeds_retired"], report["share_price_failures"])
    return report


def main() -> None:
    """CLI refresh for use only while the API is stopped — DuckDB has one writer (R6)."""
    # CLI-only composition straight from the environment (§13): infrastructure
    # never imports app — dependencies point inward only (§3). The running app
    # wires the same runner from Settings in app/dependencies.py (R3).
    from infrastructure.duckdb.connection import DuckDBConn

    logging.basicConfig(level=logging.INFO)
    catalogue = ArrivedCatalogue(os.environ.get("ARRIVED_API_URL", DEFAULT_API_URL))
    conn = DuckDBConn(Path(os.environ.get("DB_PATH", "data/arrived.duckdb")))
    try:
        report = refresh_offerings(catalogue, repo=OfferingsRepo(conn))
    finally:
        conn.close()
    logger.info("refresh_result %s", " ".join(f"{k}={v}" for k, v in report.items()))


if __name__ == "__main__":
    main()
