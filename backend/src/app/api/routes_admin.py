"""Admin refresh routes: market enrichment and the live offerings catalogue (§9).

Both run inside the API process — the sole DuckDB writer (R6) — and return the
runner's status report. They have no route-level auth, so the supported Compose
deployment binds the API to loopback; §16 defers authenticated remote access.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencies import OfferingsRefreshRunnerDep, RefreshRunnerDep

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/admin/refresh-market-data")
def refresh_market_data(refresh: RefreshRunnerDep) -> dict[str, Any]:
    """Refresh market metrics; per-source `{status, rows}`, failures isolated (R20)."""
    return refresh()


@router.post("/admin/refresh-offerings")
def refresh_offerings(refresh: OfferingsRefreshRunnerDep) -> dict[str, Any]:
    """Refresh offerings from Arrived's public catalogue; upsert-or-error report (§10)."""
    return refresh()
