"""Behavioral tests for the Arrived catalogue mapper (live-data design doc).

Pure-function coverage over offline fixture dicts (R25): the buyable-status
filter, every mapping-table rule, the yield and appreciation fallback chains,
the leverage clamp, historical-returns rows, and alias generation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from domain.models import Offering
from infrastructure.arrived.mapper import MappedData, map_offerings
from tests.infrastructure.arrived_fixtures import (
    CATALOGUE,
    COMING_SOON_OFFERING,
    FLAT_HISTORY,
    FUND_OFFERING,
    FUNDED_OFFERING,
    LTR_NO_DIVIDEND,
    LTR_WITH_DIVIDEND,
    RISING_HISTORY,
    SHARE_PRICES,
    STR_WITH_DIVIDEND,
)

AS_OF = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)


def _mapped() -> MappedData:
    return map_offerings(CATALOGUE, SHARE_PRICES, AS_OF)


def _by_id() -> dict[str, Offering]:
    return {o.id: o for o in _mapped().offerings}


def _variant(base: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    return {**base, **overrides}


def test_filter_keeps_only_buyable_statuses_and_prefixes_ids() -> None:
    ids = [o.id for o in _mapped().offerings]
    assert ids == ["arrived-maple", "arrived-birch", "arrived-dune", "arrived-haven-fund"]


def test_filtered_offerings_never_leak_into_returns_or_aliases() -> None:
    data = _mapped()
    assert not any("sold-out" in r.offering_id or "teaser" in r.offering_id
                   for r in data.returns)
    assert all(raw not in ("Memphis, TN", "Boise, ID") for raw, _slug in data.aliases)


def test_no_buyable_offerings_maps_to_empty() -> None:
    assert map_offerings([FUNDED_OFFERING, COMING_SOON_OFFERING], {}, AS_OF) == \
        MappedData([], [], [])


def test_identity_and_passthrough_fields() -> None:
    maple = _by_id()["arrived-maple"]
    assert maple.name == "The Maple"
    assert maple.status == "available"
    assert maple.share_price_usd == 10.0
    assert maple.min_investment_usd == 100.0
    assert maple.funded_pct == pytest.approx(0.425)  # fundedPercent 42.5 -> decimal
    assert maple.as_of == AS_OF


def test_funded_pct_scales_to_decimal_clamps_and_preserves_none() -> None:
    over = _variant(LTR_WITH_DIVIDEND, shortName="over", fundedPercent=250.0)
    negative = _variant(LTR_WITH_DIVIDEND, shortName="neg", fundedPercent=-5.0)
    missing = _variant(LTR_WITH_DIVIDEND, shortName="none", fundedPercent=None)
    data = map_offerings([over, negative, missing], {}, AS_OF)
    assert [o.funded_pct for o in data.offerings] == [1.0, 0.0, None]


def test_market_strips_us_prefix_and_funds_are_diversified() -> None:
    by_id = _by_id()
    assert by_id["arrived-maple"].market == "Nashville, TN"
    assert by_id["arrived-birch"].market == "Chattanooga, TN"
    assert by_id["arrived-dune"].market == "Joshua Tree, CA"
    assert by_id["arrived-haven-fund"].market == "Diversified"


def test_property_type_mapping() -> None:
    by_id = _by_id()
    assert by_id["arrived-maple"].property_type == "single_family"
    assert by_id["arrived-dune"].property_type == "vacation_rental"
    assert by_id["arrived-haven-fund"].property_type == "fund"


def test_city_blend_asset_type_is_fund_even_without_fund_type() -> None:
    blend = _variant(FUND_OFFERING, type="IPO", assetType="CITY_BLEND")
    assert map_offerings([blend], {}, AS_OF).offerings[0].property_type == "fund"


def test_yield_derives_from_latest_dividend() -> None:
    by_id = _by_id()
    assert by_id["arrived-maple"].projected_dividend_yield == pytest.approx(0.06)
    assert by_id["arrived-dune"].projected_dividend_yield == pytest.approx(0.08)
    assert by_id["arrived-haven-fund"].projected_dividend_yield == pytest.approx(0.09)


def test_yield_fallback_uses_same_type_median_not_all_median() -> None:
    # single_family median is maple's 0.06; the all-offering median would be 0.08.
    assert _by_id()["arrived-birch"].projected_dividend_yield == pytest.approx(0.06)


def test_yield_fallback_all_median_then_zero() -> None:
    quiet_fund = _variant(FUND_OFFERING, latestDividend=None)
    data = map_offerings([LTR_WITH_DIVIDEND, quiet_fund], {}, AS_OF)
    fund = next(o for o in data.offerings if o.property_type == "fund")
    assert fund.projected_dividend_yield == pytest.approx(0.06)  # no fund dividends -> all
    alone = map_offerings([LTR_NO_DIVIDEND], {}, AS_OF)
    assert alone.offerings[0].projected_dividend_yield == 0.0  # nobody has one -> 0.0


def test_appreciation_annualized_from_rising_history() -> None:
    # 10.0 -> 10.6 across exactly 365 days annualizes to 6%.
    assert _by_id()["arrived-maple"].projected_appreciation == pytest.approx(0.06)


def test_appreciation_fallback_for_flat_short_and_missing_histories() -> None:
    by_id = _by_id()
    for oid in ("arrived-birch", "arrived-dune", "arrived-haven-fund"):
        assert by_id[oid].projected_appreciation == pytest.approx(0.06), oid


def test_appreciation_fallback_prefers_same_type_median() -> None:
    steeper = [{"date": "2025-06-01", "sharePrice": 15.0},
               {"date": "2026-06-01", "sharePrice": 16.5}]  # 10% for the STR
    prices = {"maple": RISING_HISTORY, "birch": FLAT_HISTORY, "dune": steeper}
    data = map_offerings([LTR_WITH_DIVIDEND, LTR_NO_DIVIDEND, STR_WITH_DIVIDEND,
                          FUND_OFFERING], prices, AS_OF)
    by_id = {o.id: o for o in data.offerings}
    assert by_id["arrived-birch"].projected_appreciation == pytest.approx(0.06)  # same-type
    assert by_id["arrived-haven-fund"].projected_appreciation == pytest.approx(0.08)  # all


def test_appreciation_zero_when_no_history_anywhere() -> None:
    assert map_offerings([LTR_WITH_DIVIDEND], {}, AS_OF).offerings[0] \
        .projected_appreciation == 0.0


def test_leverage_from_raise_vs_purchase() -> None:
    by_id = _by_id()
    assert by_id["arrived-maple"].leverage_pct == pytest.approx(0.5)
    assert by_id["arrived-birch"].leverage_pct == pytest.approx(0.2)
    assert by_id["arrived-haven-fund"].leverage_pct == 0.0  # no totalPurchasePrice


def test_leverage_clamps_to_unit_interval() -> None:
    over = _variant(LTR_WITH_DIVIDEND, shortName="over", targetRaiseAmount=600_000.0)
    negative = _variant(LTR_WITH_DIVIDEND, shortName="neg", targetRaiseAmount=-300_000.0)
    zero_price = _variant(LTR_WITH_DIVIDEND, shortName="zero", totalPurchasePrice=0.0)
    missing = {k: v for k, v in LTR_WITH_DIVIDEND.items() if k != "totalPurchasePrice"}
    data = map_offerings([over, negative, zero_price, missing], {}, AS_OF)
    assert [o.leverage_pct for o in data.offerings] == [0.0, 1.0, 0.0, 0.0]


def test_property_value_fallback_order() -> None:
    by_id = _by_id()
    assert by_id["arrived-maple"].property_value_usd == 325_000.0  # purchasePrice wins
    assert by_id["arrived-birch"].property_value_usd == 300_000.0  # totalPurchasePrice
    assert by_id["arrived-haven-fund"].property_value_usd == 5_000_000.0  # targetRaise


def test_returns_rows_last_price_per_month_and_dividend_on_end_month() -> None:
    rows = [r for r in _mapped().returns if r.offering_id == "arrived-maple"]
    assert [(r.month, r.share_value_usd) for r in rows] == [
        ("2025-06", 10.02), ("2025-09", 10.15), ("2025-12", 10.3),
        ("2026-03", 10.45), ("2026-06", 10.6)]
    assert [r.dividend_per_share for r in rows] == [None, None, None, None, 0.05]


def test_returns_row_for_dividend_without_history() -> None:
    rows = [r for r in _mapped().returns if r.offering_id == "arrived-haven-fund"]
    assert [(r.month, r.dividend_per_share, r.share_value_usd) for r in rows] == [
        ("2026-06", 0.075, None)]


def test_aliases_cover_every_non_diversified_market_once() -> None:
    assert sorted(_mapped().aliases) == [
        ("Chattanooga, TN", "chattanooga-tn"),
        ("Joshua Tree, CA", "joshua-tree-ca"),
        ("Nashville, TN", "nashville-tn")]
