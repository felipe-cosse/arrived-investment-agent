"""Source-backed optional presentation fields from an Arrived offering detail row."""

from __future__ import annotations

from math import isfinite
from typing import Any

RawItem = dict[str, Any]
_FUND_TYPES = frozenset({"PRIVATE_CREDIT", "CITY_BLEND"})


def _number(value: Any) -> float | None:
    """Return finite numeric input without coercing strings or booleans."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    result = float(value)
    return result if isfinite(result) else None


def _integer(value: Any) -> int | None:
    """Return a whole-number source value as int, otherwise None."""
    number = _number(value)
    return int(number) if number is not None and number.is_integer() else None


def _property(item: RawItem) -> RawItem:
    """Return the sole house for property offerings; funds have no house-level facts."""
    if item.get("type") == "FUND" or item.get("assetType") in _FUND_TYPES:
        return {}
    properties = item.get("properties") or []
    return properties[0] or {} if len(properties) == 1 else {}


def _text(value: Any) -> str | None:
    """Trim non-empty string source values."""
    return value.strip() if isinstance(value, str) and value.strip() else None


def offering_details(item: RawItem) -> dict[str, Any]:
    """Map optional facts; annual values are labeled arithmetic derivations."""
    prop = _property(item)
    monthly_rent = _number(prop.get("rent"))
    quarterly_fee = _number(item.get("quarterlyAumFeeAmount"))
    full_baths = _integer(prop.get("fullBathrooms"))
    half_baths = _integer(prop.get("halfBathrooms"))
    bathrooms = None
    if full_baths is not None or half_baths is not None:
        bathrooms = float(full_baths or 0) + float(half_baths or 0) * 0.5
    photos = prop.get("photos") or []
    photo_url = (photos[0] or {}).get("url") if photos else None
    address = prop.get("address") or {}
    short_name = _text(item.get("shortName"))
    return {
        "source_url": f"https://arrived.com/properties/{short_name}" if short_name else None,
        "thumbnail_url": _text(item.get("thumbnailPhotoUrl")) or _text(photo_url),
        "description": _text(item.get("description")),
        "purchase_price_usd": _number(prop.get("purchasePrice")),
        "monthly_rent_usd": monthly_rent,
        "annual_rent_usd": monthly_rent * 12.0 if monthly_rent is not None else None,
        "annual_platform_fee_usd": quarterly_fee * 4.0 if quarterly_fee is not None else None,
        "closing_offering_holding_costs_usd": _number(
            item.get("closingOfferingAndHoldingCosts")),
        "property_improvements_reserves_usd": _number(
            item.get("propertyImprovementsAndCashReserves")),
        "investor_count": _integer(item.get("investorsCount")),
        "bedrooms": _integer(prop.get("bedrooms")),
        "bathrooms": bathrooms,
        "square_feet": _integer(prop.get("squareFootage")),
        "year_built": _integer(prop.get("yearBuilt")),
        "street_address": _text(address.get("street")),
        "postal_code": _text(address.get("zipCode")),
        "lease_status": _text(prop.get("leaseStatus")),
        "lease_end_date": _text(prop.get("leaseEndAt")),
        "hold_period_min_years": _integer(item.get("holdPeriodYearsMin")),
        "hold_period_max_years": _integer(item.get("holdPeriodYearsMax")),
        "debt_amount_usd": _number(item.get("debtAmount")),
        "debt_interest_pct": _number(item.get("debtInterestPercent")),
    }
