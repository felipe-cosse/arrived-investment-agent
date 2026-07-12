"""GET public metro information for an offering card."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.dependencies import RegionInfoDep

router = APIRouter(prefix="/api", tags=["offerings"])


@router.get("/offerings/{offering_id}/region-info")
def get_region_info(offering_id: str, service: RegionInfoDep) -> dict[str, Any]:
    """Stored public metrics for the offering's mapped metro; never fetches live data."""
    result = service.for_offering(offering_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"unknown offering: {offering_id}")
    return result
