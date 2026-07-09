"""Frozen domain entities shared by services, repositories, and the API (spec §4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

PropertyType = Literal["single_family", "vacation_rental", "fund"]
OfferingStatus = Literal["available", "funded", "closed"]


class Offering(BaseModel):
    """One fractional real-estate offering as listed in the explorer."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    market: str
    property_type: PropertyType
    status: OfferingStatus = "available"
    share_price_usd: float
    min_investment_usd: float
    projected_dividend_yield: float
    projected_appreciation: float
    funded_pct: float | None = None
    property_value_usd: float | None = None
    leverage_pct: float | None = None
    as_of: datetime


class ReturnRecord(BaseModel):
    """One month of dividend and share-value history for an offering."""

    model_config = ConfigDict(frozen=True)

    offering_id: str
    month: str
    dividend_per_share: float | None = None
    share_value_usd: float | None = None


class MetricRow(BaseModel):
    """One (metro, month, source, metric) market-enrichment observation."""

    model_config = ConfigDict(frozen=True)

    metro: str
    month: str
    source: str
    metric: str
    value: float
    as_of: datetime


class Position(BaseModel):
    """One new-money allocation inside a plan, with its score breakdown (R13)."""

    model_config = ConfigDict(frozen=True)

    offering_id: str
    name: str
    market: str
    property_type: PropertyType
    amount_usd: int
    weight_pct: float
    projected_dividend_yield: float
    projected_appreciation: float
    est_annual_dividend_usd: float
    score_breakdown: dict[str, float]


class Plan(BaseModel):
    """Typed view of an engine result; infeasible plans carry only a reason (R12)."""

    model_config = ConfigDict(frozen=True)

    feasible: bool
    reason: str | None = None
    risk_profile: str | None = None
    horizon_years: int | None = None
    positions: tuple[Position, ...] = ()
    summary: dict[str, float] = {}
    assumptions: tuple[str, ...] = ()
    disclaimer: str | None = None


class PlanRecord(BaseModel):
    """Immutable saved-plan snapshot: inputs + full output + data freshness (R16)."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str | None = None
    created_at: datetime
    inputs: dict[str, Any]
    output: dict[str, Any]
    data_as_of: datetime
