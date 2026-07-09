"""GET /api/health and /api/meta: liveness and data-staleness snapshots (§9)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.dependencies import PlanStoreDep, ReaderDep

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the Docker HEALTHCHECK and compose readiness (§11)."""
    return {"status": "ok"}


@router.get("/meta")
def meta(reader: ReaderDep, plans: PlanStoreDep) -> dict[str, Any]:
    """Row counts and freshness per table; powers the StalenessBadge (§9)."""
    return {**reader.stats(), "plans": plans.stats()}
