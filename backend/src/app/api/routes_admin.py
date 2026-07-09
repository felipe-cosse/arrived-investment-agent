"""POST /api/admin/refresh-market-data: run enabled enrichment sources (§9).

Runs inside the API process — the sole DuckDB writer (R6) — and reports one
status per source. No auth by design; §16 defers it.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencies import RefreshRunnerDep

router = APIRouter(prefix="/api", tags=["admin"])


@router.post("/admin/refresh-market-data")
def refresh_market_data(refresh: RefreshRunnerDep) -> dict[str, Any]:
    """Refresh market metrics; per-source `{status, rows}`, failures isolated (R20)."""
    return refresh()
