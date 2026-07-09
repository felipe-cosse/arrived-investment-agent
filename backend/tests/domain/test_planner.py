from __future__ import annotations

from typing import Any

import pytest

from domain.planner import INCREMENT_USD, MIN_POSITION_USD, AllocationEngine
from domain.risk import RISK_STRATEGIES

BREAKDOWN_KEYS = {"yield", "appreciation", "momentum", "leverage", "total"}


def _offering(oid: str, market: str, ptype: str = "single_family", dy: float = 0.05,
              appr: float = 0.03, leverage: float | None = None) -> dict[str, Any]:
    return {"id": oid, "name": oid.title(), "market": market, "property_type": ptype,
            "status": "available", "projected_dividend_yield": dy,
            "projected_appreciation": appr, "leverage_pct": leverage}


@pytest.fixture()
def offerings() -> list[dict[str, Any]]:
    return [
        _offering("a1", "Nashville, TN", dy=0.050, appr=0.030),
        _offering("a2", "Nashville, TN", dy=0.048, appr=0.032),
        _offering("a3", "Nashville, TN", dy=0.046, appr=0.031),
        _offering("b1", "Tucson, AZ", dy=0.055, appr=0.025),
        _offering("c1", "Boise, ID", dy=0.038, appr=0.045),
        _offering("f1", "Diversified", ptype="fund", dy=0.042, appr=0.031),
        _offering("f2", "Diversified", ptype="fund", dy=0.081, appr=0.000),
    ]


ENGINE = AllocationEngine()
BAL = RISK_STRATEGIES["balanced"]


@pytest.mark.parametrize("profile", sorted(RISK_STRATEGIES))
@pytest.mark.parametrize("amount", [100, 250, 1_000, 5_000, 12_345.67])
def test_budget_conservation_increments_breakdown(offerings, profile: str, amount: float) -> None:
    plan = ENGINE.build(amount, RISK_STRATEGIES[profile], 5, offerings=offerings)
    assert plan["feasible"], plan
    s = plan["summary"]
    assert s["total_invested_usd"] + s["unallocated_cash_usd"] == pytest.approx(amount, abs=0.01)
    for pos in plan["positions"]:
        assert pos["amount_usd"] >= MIN_POSITION_USD
        assert pos["amount_usd"] % INCREMENT_USD == 0
        assert set(pos["score_breakdown"]) == BREAKDOWN_KEYS


def test_position_cap_and_market_diversification(offerings) -> None:
    for name, strategy in RISK_STRATEGIES.items():
        plan = ENGINE.build(10_000, strategy, 5, offerings=offerings)
        cap = max(MIN_POSITION_USD, int(10_000 * strategy.max_position_pct))
        assert all(p["amount_usd"] <= cap for p in plan["positions"]), name
        nash = [p for p in plan["positions"]
                if p["market"] == "Nashville, TN" and p["property_type"] != "fund"]
        assert len(nash) <= 2


def test_conservative_fund_floor_bounded_by_cap(offerings) -> None:
    plan = ENGINE.build(1_000, RISK_STRATEGIES["conservative"], 5, offerings=offerings)
    funds = [p for p in plan["positions"] if p["property_type"] == "fund"]
    assert funds and funds[0]["amount_usd"] == 150  # min(30% floor, 15% cap) of 1000


def test_vacation_rental_type_share_cap() -> None:
    vacs = [_offering(f"v{i}", f"V{i}, XX", ptype="vacation_rental", dy=0.09, appr=0.05)
            for i in range(4)]
    sfrs = [_offering(f"s{i}", f"S{i}, YY", dy=0.030, appr=0.020) for i in range(4)]
    plan = ENGINE.build(1_000, BAL, 5, offerings=vacs + sfrs)
    vac_total = sum(p["amount_usd"] for p in plan["positions"]
                    if p["property_type"] == "vacation_rental")
    assert vac_total <= 500  # TYPE_SHARE_CAPS['vacation_rental'] = 0.50 of usable


def test_leverage_penalty_tilts_ranking() -> None:
    twins = [_offering("hi-lev", "A, XX", leverage=0.70),
             _offering("no-lev", "B, YY", leverage=0.00)]
    plan = ENGINE.build(300, RISK_STRATEGIES["conservative"], 5, offerings=twins)
    assert plan["positions"][0]["offering_id"] == "no-lev"


def test_momentum_tilts_ranking_deterministically() -> None:
    twins = [_offering("m1", "Boise, ID"), _offering("m2", "Tucson, AZ")]
    hot = ENGINE.build(300, BAL, 5, offerings=twins,
                       momentum_by_market={"Boise, ID": 1.0, "Tucson, AZ": 0.0})
    assert hot["positions"][0]["offering_id"] == "m1"
    neutral = ENGINE.build(300, BAL, 5, offerings=twins)
    assert neutral["positions"][0]["offering_id"] == "m1"  # tie → id order


def test_existing_positions_respect_caps_and_markets(offerings) -> None:
    held_at_cap = {"b1": 2_500}  # cap = 25% of (7_500 + 2_500)
    plan = ENGINE.build(7_500, BAL, 5, offerings=offerings, existing_positions=held_at_cap)
    assert plan["feasible"]
    assert all(p["offering_id"] != "b1" for p in plan["positions"])
    assert plan["summary"]["existing_portfolio_usd"] == 2_500
    assert plan["summary"]["portfolio_total_usd"] == pytest.approx(
        2_500 + plan["summary"]["total_invested_usd"])

    two_nash = {"a1": 300.0, "a2": 300.0}  # market saturated by held positions
    plan2 = ENGINE.build(2_000, BAL, 5, offerings=offerings, existing_positions=two_nash)
    new_ids = {p["offering_id"] for p in plan2["positions"]}
    assert "a3" not in new_ids  # top-ups of a1/a2 allowed; new Nashville names are not


def test_unknown_existing_id_is_infeasible(offerings) -> None:
    plan = ENGINE.build(1_000, BAL, 5, offerings=offerings,
                        existing_positions={"ghost": 100.0})
    assert plan["feasible"] is False and "ghost" in plan["reason"]


def test_determinism(offerings) -> None:
    a = ENGINE.build(3_210, BAL, 7, offerings=offerings)
    b = ENGINE.build(3_210, BAL, 7, offerings=offerings)
    assert a == b


@pytest.mark.parametrize("amount,horizon,offs", [(60, 5, None), (1_000, 0, None), (1_000, 5, [])])
def test_infeasible_inputs_return_reason(offerings, amount, horizon, offs) -> None:
    plan = ENGINE.build(amount, BAL, horizon,
                        offerings=offerings if offs is None else offs)
    assert plan["feasible"] is False and plan["reason"]
