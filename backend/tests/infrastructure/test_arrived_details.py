"""Focused mapping tests for optional facts from Arrived's public detail endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from infrastructure.arrived.mapper import map_offerings
from tests.infrastructure.arrived_fixtures import FUND_OFFERING, LTR_WITH_DIVIDEND

AS_OF = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def test_rich_detail_fields_are_source_backed_or_labeled_derivations() -> None:
    maple = map_offerings([LTR_WITH_DIVIDEND], {}, AS_OF).offerings[0]
    assert maple.source_url == "https://arrived.com/properties/maple"
    assert maple.thumbnail_url and maple.thumbnail_url.endswith("/maple.jpg")
    assert maple.description and maple.description.startswith("An occupied")
    assert maple.purchase_price_usd == 325_000.0
    assert maple.monthly_rent_usd == 1_995.0
    assert maple.annual_rent_usd == 23_940.0
    assert maple.annual_platform_fee_usd == 1_920.0
    assert maple.closing_offering_holding_costs_usd == 21_512.0
    assert maple.property_improvements_reserves_usd == 28_000.0
    assert maple.investor_count == 921
    assert (maple.bedrooms, maple.bathrooms, maple.square_feet) == (4, 3.5, 2_021)
    assert (maple.year_built, maple.lease_status) == (2018, "OCCUPIED")
    assert (maple.street_address, maple.postal_code) == (
        "5066 West Claxton Circle", "72704")
    assert maple.lease_end_date == "2028-02-29T00:00:00.000Z"
    assert (maple.hold_period_min_years, maple.hold_period_max_years) == (5, 7)
    # debtInterestPercent is already percentage points, not a 0-1 decimal rate.
    assert (maple.debt_amount_usd, maple.debt_interest_pct) == (150_000.0, 5.625)


def test_house_fields_remain_optional_for_funds() -> None:
    fund = map_offerings([FUND_OFFERING], {}, AS_OF).offerings[0]
    assert fund.source_url == "https://arrived.com/properties/haven-fund"
    assert fund.monthly_rent_usd is None
    assert fund.purchase_price_usd is None
    assert fund.bedrooms is None


def test_nonfinite_and_malformed_optional_values_are_not_exposed() -> None:
    malformed = {
        **LTR_WITH_DIVIDEND,
        "investorsCount": 1.5,
        "quarterlyAumFeeAmount": float("inf"),
        "properties": [{**LTR_WITH_DIVIDEND["properties"][0], "rent": "1995"}],
    }
    offering = map_offerings([malformed], {}, AS_OF).offerings[0]
    assert offering.investor_count is None
    assert offering.annual_platform_fee_usd is None
    assert offering.monthly_rent_usd is None
    assert offering.annual_rent_usd is None
