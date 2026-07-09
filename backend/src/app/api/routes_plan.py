"""POST /api/plan: validate the request body and run the deterministic planner (R4)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import PlanServiceDep
from services.plan_service import DEFAULT_HORIZON_YEARS, DEFAULT_RISK_PROFILE

router = APIRouter(prefix="/api", tags=["plan"])


class ExistingPositionBody(BaseModel):
    """One already-held position: money invested in an offering."""

    offering_id: str
    amount_usd: float


class PlanRequest(BaseModel):
    """POST /api/plan body (§9); `existing_positions` is optional."""

    amount: float
    risk_profile: str = DEFAULT_RISK_PROFILE
    horizon_years: int = DEFAULT_HORIZON_YEARS
    existing_positions: list[ExistingPositionBody] | None = None

    def existing_as_args(self) -> list[dict[str, Any]] | None:
        """Existing positions in the tool-schema list shape PlanService accepts."""
        if self.existing_positions is None:
            return None
        return [position.model_dump() for position in self.existing_positions]


@router.post("/plan")
def build_plan(body: PlanRequest, plan_service: PlanServiceDep) -> dict[str, Any]:
    """Run the engine; infeasible inputs come back as results, never 500s (R12)."""
    return plan_service.build_plan(body.amount, body.risk_profile, body.horizon_years,
                                   body.existing_as_args())
