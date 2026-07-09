"""Risk-profile Strategy objects and their registry (spec §6; OCP).

Adding a profile is one `RiskStrategy` plus a registry entry — no engine edits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskStrategy:
    """Scoring weights and portfolio-shape limits for one risk profile."""

    name: str
    yield_weight: float
    appreciation_weight: float
    market_weight: float
    leverage_weight: float
    max_position_pct: float
    fund_floor_pct: float


RISK_STRATEGIES: dict[str, RiskStrategy] = {
    strategy.name: strategy
    for strategy in (
        RiskStrategy("conservative", 0.8, 0.2, 0.005, 0.010, 0.15, 0.30),
        RiskStrategy("balanced", 0.5, 0.5, 0.010, 0.005, 0.25, 0.15),
        RiskStrategy("aggressive", 0.3, 0.7, 0.020, 0.000, 0.35, 0.00),
    )
}
