"""Enrichment refresh orchestration: run enabled sources, upsert their rows (§10).

Each source is isolated (R20): a missing API key reports `skipped_no_key`, any
other failure reports `error`, and neither stops the remaining sources or the
app. The provider adapters (zillow/fred/census) and the `python -m` CLI arrive
with build-order step 5 (§15); this module owns the shared runner used by both
the CLI and the admin route.
"""

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
