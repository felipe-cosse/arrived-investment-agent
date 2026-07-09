"""Deterministic allocation engine: budget + offerings -> ranked plan (spec §6).

Same inputs always produce the same plan; ties break by offering id. Invalid
input returns `{"feasible": false, "reason": ...}` — the engine never raises (R12).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from domain.allocation import (
    FUND_TYPE,
    INCREMENT_USD,
    MIN_POSITION_USD,
    Allocator,
    floor_to_increment,
)
from domain.risk import RiskStrategy

# The money-grid constants are part of this module's public §6 contract.
__all__ = ["DISCLAIMER", "INCREMENT_USD", "MIN_POSITION_USD", "AllocationEngine"]

DISCLAIMER = (
    "This plan is a hypothetical projection for research and education. "
    "It is not investment advice."
)

_Row = Mapping[str, Any]


def _infeasible(reason: str) -> dict[str, Any]:
    """Engine failures are data the agent can relay, never exceptions (R12)."""
    return {"feasible": False, "reason": reason}


def _score_breakdown(row: _Row, s: RiskStrategy, momentum: Mapping[str, float]) -> dict[str, float]:
    """Per-offering score components — the sanctioned way to explain rankings (R13)."""
    parts = {
        "yield": s.yield_weight * float(row["projected_dividend_yield"]),
        "appreciation": s.appreciation_weight * float(row["projected_appreciation"]),
        "momentum": s.market_weight * (momentum.get(str(row["market"]), 0.5) - 0.5),
        "leverage": -s.leverage_weight * float(row.get("leverage_pct") or 0.0),
    }
    parts["total"] = sum(parts.values())
    return parts


def _assumptions(s: RiskStrategy, momentum: Mapping[str, float],
                 existing: Mapping[str, float]) -> list[str]:
    """Narrate the §6 levers that shaped the plan (market signal, leverage, caps)."""
    return [
        (f"Market momentum was applied as a bounded score tilt (weight {s.market_weight}); "
         "markets without a signal scored neutral (0.5)."
         if momentum else
         "No market momentum signals were supplied; every market scored neutral (0.5)."),
        f"Leverage is penalized in scoring at weight {s.leverage_weight}; "
        "offerings with unknown leverage are treated as unlevered.",
        "Property-type share caps were enforced: vacation rentals are capped at 50% "
        "of the portfolio base.",
        (f"Existing holdings totaling ${sum(existing.values()):,.2f} were considered: "
         "position caps, market limits, and the fund floor account for them."
         if existing else
         "No existing holdings were provided; caps apply to new money only."),
        f"Positions are whole dollars in ${INCREMENT_USD} increments (min ${MIN_POSITION_USD}); "
        f"per-offering cap {s.max_position_pct:.0%} of the portfolio base; "
        f"fund floor {s.fund_floor_pct:.0%}.",
    ]


class AllocationEngine:
    """Builds deterministic investment plans around any existing holdings (§6)."""

    def build(self, amount_usd: float, strategy: RiskStrategy, horizon_years: int, *,
              offerings: Sequence[_Row],
              momentum_by_market: Mapping[str, float] | None = None,
              existing_positions: Mapping[str, float] | None = None) -> dict[str, Any]:
        """Allocate `amount_usd` of new money; returns the §6 output contract."""
        existing = {str(k): float(v) for k, v in (existing_positions or {}).items()}
        momentum = dict(momentum_by_market or {})
        usable = floor_to_increment(amount_usd)
        if usable < MIN_POSITION_USD:
            return _infeasible(
                f"amount ${amount_usd:,.2f} is below the ${MIN_POSITION_USD} minimum position")
        if not 1 <= horizon_years <= 30:
            return _infeasible(f"horizon_years must be between 1 and 30, got {horizon_years}")
        catalog = {str(o["id"]): o for o in offerings}
        unknown = sorted(set(existing) - set(catalog))
        if unknown:
            return _infeasible("unknown existing position ids: " + ", ".join(unknown))
        available = [o for o in offerings if o.get("status", "available") == "available"]
        if not available:
            return _infeasible("no available offerings to allocate against")

        breakdowns = {str(o["id"]): _score_breakdown(o, strategy, momentum) for o in available}
        ranked = sorted(available, key=lambda o: (-breakdowns[str(o["id"])]["total"], str(o["id"])))
        base = usable + sum(existing.values())
        cap = max(MIN_POSITION_USD, floor_to_increment(base * strategy.max_position_pct))
        state = Allocator(usable, base, cap, existing, catalog)

        self._apply_fund_floor(state, ranked, strategy, catalog)
        for row in ranked:  # greedy fill down the ranking (§6 step 5)
            if state.remaining <= 0:
                break
            state.grant(row, state.remaining)
        for row in ranked:  # top-up pass: leftover to allocated-or-held names (§6 step 6)
            if state.remaining < INCREMENT_USD:
                break
            if str(row["id"]) in state.alloc or str(row["id"]) in existing:
                state.grant(row, state.remaining, allow_topup=True)
        return self._render(amount_usd, strategy, horizon_years, ranked, breakdowns,
                            state, momentum)

    @staticmethod
    def _apply_fund_floor(state: Allocator, ranked: Sequence[_Row], strategy: RiskStrategy,
                          catalog: Mapping[str, _Row]) -> None:
        """Reserve the strategy's fund floor before the greedy fill (§6 step 4).

        Interpretation (confirmed intended reading of §6): `fund_floor_pct == 0`
        means no fund requirement at all — the step is skipped entirely, and the
        `max(MIN_POSITION_USD, ...)` clamp in the target formula applies only
        when a strategy actually demands a floor. Aggressive (0%) plans may
        therefore hold no fund.
        """
        if strategy.fund_floor_pct <= 0:
            return
        funds = [o for o in ranked if o["property_type"] == FUND_TYPE]
        if not funds:
            return
        target = min(max(MIN_POSITION_USD,
                         floor_to_increment(state.base * strategy.fund_floor_pct)), state.cap)
        held_in_funds = sum(amount for oid, amount in state.existing.items()
                            if catalog[oid]["property_type"] == FUND_TYPE)
        if held_in_funds < target:
            state.grant(funds[0], target - held_in_funds)

    @staticmethod
    def _render(amount_usd: float, strategy: RiskStrategy, horizon_years: int,
                ranked: Sequence[_Row], breakdowns: Mapping[str, dict[str, float]],
                state: Allocator, momentum: Mapping[str, float]) -> dict[str, Any]:
        """Shape the §6 output: ranked positions, summary, assumptions, disclaimer."""
        invested = sum(state.alloc.values())
        positions: list[dict[str, Any]] = []
        annual_div = 0.0
        value_at_horizon = 0.0
        for row in ranked:
            amount = state.alloc.get(str(row["id"]), 0)
            if amount <= 0:
                continue
            dy = float(row["projected_dividend_yield"])
            appreciation = float(row["projected_appreciation"])
            annual_div += amount * dy
            value_at_horizon += amount * (1 + appreciation) ** horizon_years
            positions.append({
                "offering_id": str(row["id"]), "name": str(row["name"]),
                "market": str(row["market"]), "property_type": str(row["property_type"]),
                "amount_usd": amount,
                "weight_pct": round(100.0 * amount / invested, 2),
                "projected_dividend_yield": dy, "projected_appreciation": appreciation,
                "est_annual_dividend_usd": round(amount * dy, 2),
                "score_breakdown": {k: round(v, 6)
                                    for k, v in breakdowns[str(row["id"])].items()},
            })
        existing_total = round(sum(state.existing.values()), 2)
        cumulative_div = annual_div * horizon_years
        summary = {
            "requested_usd": round(float(amount_usd), 2),
            "total_invested_usd": invested,
            "unallocated_cash_usd": round(float(amount_usd) - invested, 2),
            "existing_portfolio_usd": existing_total,
            "portfolio_total_usd": round(existing_total + invested, 2),
            "position_count": len(positions),
            "blended_dividend_yield": round(annual_div / invested, 6) if invested else 0.0,
            "projected_annual_dividends_usd": round(annual_div, 2),
            "projected_value_at_horizon_usd": round(value_at_horizon, 2),
            "projected_cumulative_dividends_usd": round(cumulative_div, 2),
            "projected_total_at_horizon_usd": round(value_at_horizon + cumulative_div, 2),
        }
        return {"feasible": True, "risk_profile": strategy.name,
                "horizon_years": horizon_years, "positions": positions, "summary": summary,
                "assumptions": _assumptions(strategy, momentum, state.existing),
                "disclaimer": DISCLAIMER}
