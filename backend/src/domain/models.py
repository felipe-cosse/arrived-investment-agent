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
    source_url: str | None = None
    thumbnail_url: str | None = None
    description: str | None = None
    purchase_price_usd: float | None = None
    monthly_rent_usd: float | None = None
    annual_rent_usd: float | None = None
    annual_platform_fee_usd: float | None = None
    closing_offering_holding_costs_usd: float | None = None
    property_improvements_reserves_usd: float | None = None
    investor_count: int | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    square_feet: int | None = None
    year_built: int | None = None
    street_address: str | None = None
    postal_code: str | None = None
    lease_status: str | None = None
    lease_end_date: str | None = None
    hold_period_min_years: int | None = None
    hold_period_max_years: int | None = None
    debt_amount_usd: float | None = None
    debt_interest_pct: float | None = None  # Arrived percentage points: 5.625 means 5.625%
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
