"""Canonical DuckDB column order for Offering serialization."""

from __future__ import annotations

OFFERING_COLS: tuple[str, ...] = (
    "id", "name", "market", "property_type", "status", "share_price_usd",
    "min_investment_usd", "projected_dividend_yield", "projected_appreciation",
    "funded_pct", "property_value_usd", "leverage_pct", "source_url", "thumbnail_url",
    "description", "purchase_price_usd", "monthly_rent_usd", "annual_rent_usd",
    "annual_platform_fee_usd", "closing_offering_holding_costs_usd",
    "property_improvements_reserves_usd", "investor_count", "bedrooms", "bathrooms",
    "square_feet", "year_built", "street_address", "postal_code", "lease_status",
    "lease_end_date", "hold_period_min_years", "hold_period_max_years",
    "debt_amount_usd", "debt_interest_pct", "as_of",
)
