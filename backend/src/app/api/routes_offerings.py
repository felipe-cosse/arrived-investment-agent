"""GET /api/offerings and /api/offerings/{id}: parse filters, call the read port (R4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.dependencies import ReaderDep

router = APIRouter(prefix="/api", tags=["offerings"])

_DETAIL_HISTORY_MONTHS = 12


@router.get("/offerings")
def list_offerings(
    reader: ReaderDep,
    market: str | None = None,
    property_type: str | None = None,
    min_dividend_yield: float | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Filtered offering list (§9)."""
    rows = reader.list_offerings(market=market, property_type=property_type,
                                 min_dividend_yield=min_dividend_yield, limit=limit)
    return {"count": len(rows), "offerings": [r.model_dump(mode="json") for r in rows]}


@router.get("/offerings/{offering_id}")
def get_offering(offering_id: str, reader: ReaderDep) -> dict[str, Any]:
    """One offering plus its recent monthly history; 404 when unknown (§9)."""
    offering = reader.get_offering(offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail=f"unknown offering: {offering_id}")
    history = reader.get_returns(offering_id, _DETAIL_HISTORY_MONTHS)
    return {"offering": offering.model_dump(mode="json"),
            "history": [r.model_dump(mode="json") for r in history]}
