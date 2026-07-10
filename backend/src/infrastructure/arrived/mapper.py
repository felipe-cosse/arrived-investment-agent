"""Pure mapping from Arrived's public catalogue JSON to domain rows.

Implements the live-data design doc's mapping table exactly: only buyable
listings (status in BUYABLE_STATUSES) map; ids are ``arrived-{shortName}``;
projected yield and appreciation fall back from their direct derivation to the
same-property_type median, then the all-offering median, then 0.0. No I/O
happens here — the fetcher supplies raw dicts and the refresh runner writes;
a missing required field raises and becomes the runner's error report.
"""

from __future__ import annotations

from datetime import date, datetime
from statistics import median
from typing import Any, NamedTuple

from domain.models import Offering, PropertyType, ReturnRecord
from infrastructure.seed import FUND_MARKET, slugify_market

# The catalogue statuses the site shows as buyable ("Available"/"New"/"Almost Gone").
BUYABLE_STATUSES: frozenset[str] = frozenset({"TRANSACT_ALL", "TRANSACT_EARLY_ACCESS"})
_FUND_ASSET_TYPES: frozenset[str] = frozenset({"PRIVATE_CREDIT", "CITY_BLEND"})
MIN_HISTORY_DAYS = 28
_DAYS_PER_YEAR = 365.0

RawItem = dict[str, Any]
_History = list[tuple[date, float]]


class MappedData(NamedTuple):
    """Mapper output: rows ready for the OfferingWriter upserts."""

    offerings: list[Offering]
    returns: list[ReturnRecord]
    aliases: list[tuple[str, str]]


def _number(value: Any) -> float | None:
    """The value as a float when it is a real (non-bool) number, else None."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _market(item: RawItem) -> str:
    """'{city}, {ST}' from the first property's address; funds have none -> Diversified."""
    properties = item.get("properties") or []
    address = ((properties[0] or {}).get("address") or {}) if properties else {}
    city, province = address.get("city"), address.get("province")
    if not city or not province:
        return FUND_MARKET
    return f"{city}, {str(province).removeprefix('US-')}"


def _property_type(item: RawItem) -> PropertyType:
    """FUND type or PRIVATE_CREDIT/CITY_BLEND asset -> fund; STR -> vacation_rental."""
    if item.get("type") == "FUND" or item.get("assetType") in _FUND_ASSET_TYPES:
        return "fund"
    if item.get("assetType") == "STR":
        return "vacation_rental"
    return "single_family"


def _property_value(item: RawItem) -> float | None:
    """First positive of properties[0].purchasePrice, totalPurchasePrice, targetRaiseAmount."""
    properties = item.get("properties") or []
    purchase = (properties[0] or {}).get("purchasePrice") if properties else None
    for candidate in (purchase, item.get("totalPurchasePrice"), item.get("targetRaiseAmount")):
        value = _number(candidate)
        if value is not None and value > 0:
            return value
    return None


def _leverage(item: RawItem) -> float:
    """1 - targetRaiseAmount/totalPurchasePrice clamped to [0, 1]; 0.0 when unknowable."""
    raise_amount = _number(item.get("targetRaiseAmount"))
    purchase = _number(item.get("totalPurchasePrice"))
    if raise_amount is None or purchase is None or purchase <= 0:
        return 0.0
    return min(1.0, max(0.0, 1.0 - raise_amount / purchase))


def _funded_pct(item: RawItem) -> float | None:
    """fundedPercent (API's 0-100 scale) as the schema's [0, 1] decimal; None preserved."""
    value = _number(item.get("fundedPercent"))
    if value is None:
        return None
    return min(1.0, max(0.0, value / 100.0))


def _direct_yield(item: RawItem) -> float | None:
    """Annualized dividendPerShare*12/sharePrice, or None before the first dividend."""
    dividend = _number((item.get("latestDividend") or {}).get("dividendPerShare"))
    share_price = _number(item.get("sharePrice"))
    if dividend is None or dividend <= 0 or share_price is None or share_price <= 0:
        return None
    return dividend * 12.0 / share_price


def _history(points: list[RawItem]) -> _History:
    """Chronologically sorted (day, price) share-price points; malformed entries drop."""
    parsed: _History = []
    for entry in points:
        raw_day = entry.get("date") or entry.get("effectiveDate")
        price = _number(entry.get("sharePrice", entry.get("price")))
        if raw_day and price is not None and price > 0:
            parsed.append((date.fromisoformat(str(raw_day)[:10]), price))
    return sorted(parsed)


def _direct_appreciation(history: _History) -> float | None:
    """Annualized first-vs-last change; needs >= 2 points >= MIN_HISTORY_DAYS apart."""
    if len(history) < 2:
        return None
    (first_day, first_price), (last_day, last_price) = history[0], history[-1]
    days = (last_day - first_day).days
    if days < MIN_HISTORY_DAYS or first_price <= 0:
        return None
    return float((last_price / first_price) ** (_DAYS_PER_YEAR / days)) - 1.0


def _with_fallback(direct: float | None, ptype: str, by_type: dict[str, list[float]]) -> float:
    """The design doc's chain: direct -> same-type median -> all-offering median -> 0.0."""
    if direct is not None:
        return direct
    same_type = by_type.get(ptype)
    if same_type:
        return median(same_type)
    all_values = [value for values in by_type.values() for value in values]
    return median(all_values) if all_values else 0.0


def _return_rows(offering_id: str, history: _History,
                 latest_dividend: RawItem | None) -> list[ReturnRecord]:
    """One row per month (last price of the month); the dividend on its end-date month."""
    value_by_month: dict[str, float] = {}
    for day, price in history:  # chronological, so later points win their month
        value_by_month[f"{day.year:04d}-{day.month:02d}"] = price
    dividend_by_month: dict[str, float] = {}
    dividend = _number((latest_dividend or {}).get("dividendPerShare"))
    end_date = (latest_dividend or {}).get("endDate")
    if dividend is not None and dividend > 0 and end_date:
        dividend_by_month[str(end_date)[:7]] = dividend
    return [ReturnRecord(offering_id=offering_id, month=month,
                         dividend_per_share=dividend_by_month.get(month),
                         share_value_usd=value_by_month.get(month))
            for month in sorted(set(value_by_month) | set(dividend_by_month))]


def map_offerings(raw: list[RawItem], share_prices: dict[str, list[RawItem]],
                  as_of: datetime) -> MappedData:
    """Map buyable catalogue entries plus share-price histories to domain rows.

    ``share_prices`` is keyed by shortName (the share-prices endpoint's key);
    offerings without a usable history take the median appreciation chain.
    """
    buyable = [item for item in raw if item.get("status") in BUYABLE_STATUSES]
    prepared: list[tuple[RawItem, PropertyType, float | None, float | None, _History]] = []
    yields_by_type: dict[str, list[float]] = {}
    apprs_by_type: dict[str, list[float]] = {}
    for item in buyable:  # first pass: direct derivations feed the medians
        ptype = _property_type(item)
        history = _history(share_prices.get(str(item["shortName"]), []))
        direct_yield, direct_appr = _direct_yield(item), _direct_appreciation(history)
        prepared.append((item, ptype, direct_yield, direct_appr, history))
        for value, bucket in ((direct_yield, yields_by_type), (direct_appr, apprs_by_type)):
            if value is not None:
                bucket.setdefault(ptype, []).append(value)

    offerings: list[Offering] = []
    returns: list[ReturnRecord] = []
    aliases: dict[str, str] = {}
    for item, ptype, direct_yield, direct_appr, history in prepared:
        offering_id = f"arrived-{item['shortName']}"
        market = _market(item)
        offerings.append(Offering(
            id=offering_id, name=str(item["name"]), market=market, property_type=ptype,
            status="available", share_price_usd=float(item["sharePrice"]),
            min_investment_usd=float(item["minTransactionAmount"]),
            projected_dividend_yield=_with_fallback(direct_yield, ptype, yields_by_type),
            projected_appreciation=_with_fallback(direct_appr, ptype, apprs_by_type),
            funded_pct=_funded_pct(item),
            property_value_usd=_property_value(item),
            leverage_pct=_leverage(item), as_of=as_of))
        returns.extend(_return_rows(offering_id, history, item.get("latestDividend")))
        if market != FUND_MARKET and market not in aliases:
            aliases[market] = slugify_market(market)
    return MappedData(offerings, returns, list(aliases.items()))
