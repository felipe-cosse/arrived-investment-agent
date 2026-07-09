"""Enrichment refresh orchestration: run enabled sources, upsert their rows (§10).

Each source is isolated (R20): a missing API key reports `skipped_no_key`, any
other failure reports `error`, and neither stops the remaining sources or the
app. `build_sources` is the one definition of "enabled sources", shared by the
app's composition root (`app/dependencies.py`, R3) and by the `python -m`
entrypoint below, which is for use only while the API is stopped (R6)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from domain.ports import MarketDataSource, OfferingReader, OfferingWriter

logger = logging.getLogger(__name__)


class MissingApiKeyError(RuntimeError):
    """Raised by a source whose API key is absent; reported as `skipped_no_key`."""


def mapped_metros(reader: OfferingReader) -> list[str]:
    """Canonical metro slugs for every offering market with an alias row (R11)."""
    markets = {o.market for o in reader.list_offerings()}
    metros = (reader.get_metro_for_market(market) for market in sorted(markets))
    return sorted({metro for metro in metros if metro is not None})


def refresh_all(
    sources: Sequence[MarketDataSource],
    *,
    reader: OfferingReader,
    writer: OfferingWriter,
) -> dict[str, dict[str, Any]]:
    """Fetch and upsert each source's metrics; one §9 status entry per source (R20)."""
    metros = mapped_metros(reader)
    results: dict[str, dict[str, Any]] = {}
    for source in sources:
        try:
            rows = source.fetch(metros)
            count = writer.upsert_market_metrics(rows)
        except MissingApiKeyError:
            logger.info("enrichment_skipped source=%s reason=no_key", source.name)
            results[source.name] = {"status": "skipped_no_key", "rows": 0}
        except Exception:
            logger.exception("enrichment_failed source=%s", source.name)
            results[source.name] = {"status": "error", "rows": 0}
        else:
            logger.info("enrichment_upserted source=%s rows=%d", source.name, count)
            results[source.name] = {"status": "upserted", "rows": count}
    return results


def build_sources(
    *,
    zhvi_url: str,
    zori_url: str,
    fred_api_key: str | None,
    census_api_key: str | None,
) -> list[MarketDataSource]:
    """All four providers (§10); keyless ones stay listed so they report skipped_no_key (§9)."""
    # Imported here, not at module level: the adapters import MissingApiKeyError
    # from this module, so a top-level import would be circular.
    from infrastructure.enrichment.census import CensusSource
    from infrastructure.enrichment.fred import FredSource
    from infrastructure.enrichment.zillow import ZillowSource

    return [
        ZillowSource("zillow_zhvi", zhvi_url, "home_value_index"),
        ZillowSource("zillow_zori", zori_url, "rent_index"),
        FredSource(fred_api_key),
        CensusSource(census_api_key),
    ]


def main() -> None:
    """CLI refresh for use only while the API is stopped — DuckDB has one writer (R6)."""
    # CLI-only composition: the running app wires these in app/dependencies.py (R3).
    from app.config import Settings
    from infrastructure.duckdb.connection import DuckDBConn
    from infrastructure.duckdb.offerings_repo import OfferingsRepo

    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    sources = build_sources(
        zhvi_url=settings.zillow_zhvi_url, zori_url=settings.zillow_zori_url,
        fred_api_key=settings.fred_api_key, census_api_key=settings.census_api_key)
    conn = DuckDBConn(settings.db_path)
    try:
        repo = OfferingsRepo(conn)
        results = refresh_all(sources, reader=repo, writer=repo)
    finally:
        conn.close()
    for name, result in results.items():
        logger.info("refresh_result source=%s status=%s rows=%d",
                    name, result["status"], result["rows"])


if __name__ == "__main__":
    main()
