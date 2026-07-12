"""Behavioral tests for PlanService input hardening (R12).

Tool args arrive from the model untyped: malformed amounts, horizons, or
existing_positions rows must come back as {"feasible": false, "reason": ...} —
never as exceptions — while coercible values (numeric strings) still work.
"""

from __future__ import annotations

from typing import Any

import pytest

from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.duckdb.plans_repo import PlansRepo
from services.plan_service import PlanService


@pytest.fixture()
def service(repo: OfferingsRepo, plans: PlansRepo) -> PlanService:
    """PlanService over the seeded test database (conftest fixtures)."""
    return PlanService(repo, plans)


def test_numeric_string_amount_is_coerced(service: PlanService) -> None:
    """A numeric string amount coerces to float and produces a feasible plan."""
    amount: Any = "2000"
    plan = service.build_plan(amount)
    assert plan["feasible"] is True
    assert plan["summary"]["requested_usd"] == 2000.0


def test_non_numeric_amount_is_infeasible(service: PlanService) -> None:
    """A non-numeric amount yields feasible:false with a reason, not a TypeError."""
    amount: Any = "a few grand"
    plan = service.build_plan(amount)
    assert plan["feasible"] is False
    assert "amount" in plan["reason"]


def test_non_finite_amount_is_infeasible(service: PlanService) -> None:
    """NaN/inf amounts are rejected conversationally instead of crashing the engine."""
    amount: Any = "nan"
    plan = service.build_plan(amount)
    assert plan["feasible"] is False
    assert "amount" in plan["reason"]


def test_garbage_horizon_is_infeasible(service: PlanService) -> None:
    """A non-integer horizon yields feasible:false with a reason, not a ValueError."""
    horizon: Any = "a decade"
    plan = service.build_plan(2000, horizon_years=horizon)
    assert plan["feasible"] is False
    assert "horizon" in plan["reason"]


@pytest.mark.parametrize("rows", [
    [{"offering": "sfr-meridian", "amount_usd": 500}],   # missing offering_id key
    [{"offering_id": "sfr-meridian"}],                   # missing amount_usd key
    [{"offering_id": "sfr-meridian", "amount_usd": "lots"}],  # non-numeric amount
    ["sfr-meridian"],                                    # row is not a mapping
    "sfr-meridian:500",                                  # not a list at all
])
def test_malformed_existing_positions_are_infeasible(service: PlanService,
                                                     rows: Any) -> None:
    """Every malformed existing_positions shape yields a reason, never an exception."""
    plan = service.build_plan(2000, existing_positions=rows)
    assert plan["feasible"] is False
    assert "existing_positions" in plan["reason"]


def test_save_plan_rejects_malformed_input_without_persisting(
        service: PlanService, plans: PlansRepo) -> None:
    """save_plan relays the rejection and never snapshots an infeasible result."""
    amount: Any = "not money"
    out = service.save_plan(amount)
    assert out["feasible"] is False
    assert plans.stats() == {"rows": 0}


@pytest.mark.parametrize("amount", [0, -100, float("nan"), float("inf"), "nan"])
def test_existing_position_amount_must_be_positive_and_finite(
    service: PlanService, amount: Any,
) -> None:
    plan = service.build_plan(2000, existing_positions=[{
        "offering_id": "sfr-meridian", "amount_usd": amount}])
    assert plan["feasible"] is False
    assert "positive finite" in plan["reason"]


def test_duplicate_existing_position_ids_are_infeasible(service: PlanService) -> None:
    rows = [{"offering_id": "sfr-meridian", "amount_usd": 200},
            {"offering_id": "sfr-meridian", "amount_usd": 300}]
    plan = service.build_plan(2000, existing_positions=rows)
    assert plan["feasible"] is False
    assert "duplicate offering_id" in plan["reason"]


def test_ids_that_collide_after_normalization_are_duplicates(service: PlanService) -> None:
    positions: Any = {1: 200, "1": 300}
    plan = service.build_plan(2000, existing_positions=positions)
    assert plan["feasible"] is False
    assert "duplicate offering_id" in plan["reason"]
