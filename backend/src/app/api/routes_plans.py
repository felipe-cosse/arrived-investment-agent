"""Saved-plan snapshot CRUD under /api/plans (§9). Snapshots are immutable (R16)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import Field

from app.api.routes_plan import PlanRequest
from app.dependencies import PlanServiceDep, PlanStoreDep

router = APIRouter(prefix="/api", tags=["plans"])


class SavePlanRequest(PlanRequest):
    """POST /api/plans body: plan inputs plus an optional snapshot name."""

    name: str | None = Field(default=None, max_length=120)


@router.post("/plans", status_code=201)
def create_plan(body: SavePlanRequest, plan_service: PlanServiceDep) -> dict[str, Any]:
    """Re-run the engine and persist an immutable snapshot; 201 with the record (§9)."""
    record = plan_service.save_plan(body.amount, body.risk_profile, body.horizon_years,
                                    body.existing_as_args(), name=body.name)
    if record.get("feasible") is False:  # nothing was snapshotted (R12 reason relayed)
        raise HTTPException(status_code=422, detail=str(record.get("reason", "plan infeasible")))
    return record


@router.get("/plans")
def list_plans(store: PlanStoreDep) -> dict[str, Any]:
    """Snapshot summaries, newest first (§9)."""
    return {"plans": store.list_plans()}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, store: PlanStoreDep) -> dict[str, Any]:
    """One full snapshot; 404 when unknown (§9)."""
    record = store.get_plan(plan_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"unknown plan: {plan_id}")
    return record.model_dump(mode="json")


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: str, store: PlanStoreDep) -> None:
    """Delete a snapshot; 204 on success, 404 when unknown (§9)."""
    if not store.delete_plan(plan_id):
        raise HTTPException(status_code=404, detail=f"unknown plan: {plan_id}")
