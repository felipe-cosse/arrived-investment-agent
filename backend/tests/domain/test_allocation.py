"""Behavioral tests for grant-time MIN gating across engine passes (§6 steps 5–6).

The greedy fill may grant below MIN_POSITION_USD only to already-held names;
the step-6 top-up pass extends that waiver to names allocated earlier in the
same run. Names allocated this run must NOT get sub-MIN grants greedily.
"""

from __future__ import annotations

from typing import Any

from domain.planner import AllocationEngine
from domain.risk import RISK_STRATEGIES

ENGINE = AllocationEngine()
BAL = RISK_STRATEGIES["balanced"]


def _offering(oid: str, market: str, ptype: str = "single_family", dy: float = 0.05,
              appr: float = 0.03) -> dict[str, Any]:
    return {"id": oid, "name": oid.title(), "market": market, "property_type": ptype,
            "status": "available", "projected_dividend_yield": dy,
            "projected_appreciation": appr, "leverage_pct": None}


def _catalog() -> list[dict[str, Any]]:
    """One top-ranked fund plus four single-family homes in distinct markets."""
    return [
        _offering("f1", "Diversified", ptype="fund", dy=0.090, appr=0.050),
        _offering("s1", "Austin, TX", dy=0.060, appr=0.040),
        _offering("s2", "Boise, ID", dy=0.058, appr=0.038),
        _offering("s3", "Tucson, AZ", dy=0.056, appr=0.036),
        _offering("s4", "Tampa, FL", dy=0.054, appr=0.034),
    ]


def test_greedy_pass_never_grants_sub_min_to_new_names() -> None:
    """$830 balanced: the fund floor grants f1 $120, leaving $80 of cap room.

    That sub-MIN $80 must not be taken in the greedy pass (§6 step 5 waives MIN
    only for already-held names): taking it early would starve s4 below MIN.
    Instead s4 reaches $110 greedily and the fund keeps exactly its floor grant.
    """
    plan = ENGINE.build(830, BAL, 5, offerings=_catalog())
    assert plan["feasible"], plan
    by_id = {p["offering_id"]: p["amount_usd"] for p in plan["positions"]}
    assert by_id == {"f1": 120, "s1": 200, "s2": 200, "s3": 200, "s4": 110}
    assert plan["summary"]["unallocated_cash_usd"] == 0.0


def test_topup_pass_still_waives_min_for_run_allocated_names() -> None:
    """$790 balanced: leftover $80 (< MIN) still tops up the run-allocated fund.

    §6 step 6 keeps the alloc-or-held waiver: after the greedy fill leaves $110,
    the fund (floor-granted $110, cap $190) absorbs $80 in the top-up pass.
    """
    plan = ENGINE.build(790, BAL, 5, offerings=_catalog()[:4])
    assert plan["feasible"], plan
    by_id = {p["offering_id"]: p["amount_usd"] for p in plan["positions"]}
    assert by_id == {"f1": 190, "s1": 190, "s2": 190, "s3": 190}
    assert plan["summary"]["unallocated_cash_usd"] == 30.0
