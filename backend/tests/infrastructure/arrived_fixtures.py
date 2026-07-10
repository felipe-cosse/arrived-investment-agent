"""Offline fixtures modeled on Arrived's public catalogue API (live-data design doc).

Field names are verbatim from the 2026-07-09 reconnaissance: shortName, name,
status, type, assetType, sharePrice, minTransactionAmount, fundedPercent,
targetRaiseAmount, totalPurchasePrice, latestDividend{dividendPerShare, endDate},
properties[0]{purchasePrice, address{city, province}}. Tests never touch the
network (R25); these dicts stand in for the catalogue and share-price endpoints.
"""

from __future__ import annotations

from typing import Any

# Buyable long-term rental with a dividend: yield 0.05*12/10 = 0.06, leverage 0.5.
LTR_WITH_DIVIDEND: dict[str, Any] = {
    "shortName": "maple",
    "name": "The Maple",
    "status": "TRANSACT_ALL",
    "type": "IPO",
    "assetType": "LTR",
    "sharePrice": 10.0,
    "minTransactionAmount": 100.0,
    "fundedPercent": 42.5,
    "targetRaiseAmount": 150_000.0,
    "totalPurchasePrice": 300_000.0,
    "latestDividend": {"dividendPerShare": 0.05, "endDate": "2026-06-30"},
    "properties": [{"purchasePrice": 325_000.0,
                    "address": {"city": "Nashville", "province": "US-TN"}}],
}

# Buyable long-term rental before its first dividend: yield falls back to the
# same-type median; property value falls back to totalPurchasePrice.
LTR_NO_DIVIDEND: dict[str, Any] = {
    "shortName": "birch",
    "name": "The Birch",
    "status": "TRANSACT_EARLY_ACCESS",
    "type": "IPO",
    "assetType": "LTR",
    "sharePrice": 10.0,
    "minTransactionAmount": 100.0,
    "fundedPercent": 10.0,
    "targetRaiseAmount": 240_000.0,
    "totalPurchasePrice": 300_000.0,
    "latestDividend": None,
    "properties": [{"purchasePrice": None,
                    "address": {"city": "Chattanooga", "province": "US-TN"}}],
}

# Buyable short-term (vacation) rental with a dividend: yield 0.10*12/15 = 0.08.
STR_WITH_DIVIDEND: dict[str, Any] = {
    "shortName": "dune",
    "name": "The Dune",
    "status": "TRANSACT_ALL",
    "type": "IPO",
    "assetType": "STR",
    "sharePrice": 15.0,
    "minTransactionAmount": 100.0,
    "fundedPercent": 88.0,
    "targetRaiseAmount": 350_000.0,
    "totalPurchasePrice": 500_000.0,
    "latestDividend": {"dividendPerShare": 0.10, "endDate": "2026-06-30"},
    "properties": [{"purchasePrice": 500_000.0,
                    "address": {"city": "Joshua Tree", "province": "US-CA"}}],
}

# Buyable fund: no properties -> Diversified; yield 0.075*12/10 = 0.09;
# property value falls all the way back to targetRaiseAmount.
FUND_OFFERING: dict[str, Any] = {
    "shortName": "haven-fund",
    "name": "The Haven Fund",
    "status": "TRANSACT_ALL",
    "type": "FUND",
    "assetType": "PRIVATE_CREDIT",
    "sharePrice": 10.0,
    "minTransactionAmount": 100.0,
    "fundedPercent": 55.0,
    "targetRaiseAmount": 5_000_000.0,
    "totalPurchasePrice": None,
    "latestDividend": {"dividendPerShare": 0.075, "endDate": "2026-06-30"},
    "properties": [],
}

# Fully funded listing: must be filtered out (its 0.048 yield would skew medians).
FUNDED_OFFERING: dict[str, Any] = {
    "shortName": "sold-out",
    "name": "The Sold Out",
    "status": "FUNDED",
    "type": "IPO",
    "assetType": "LTR",
    "sharePrice": 10.0,
    "minTransactionAmount": 100.0,
    "fundedPercent": 100.0,
    "targetRaiseAmount": 200_000.0,
    "totalPurchasePrice": 400_000.0,
    "latestDividend": {"dividendPerShare": 0.04, "endDate": "2026-06-30"},
    "properties": [{"purchasePrice": 400_000.0,
                    "address": {"city": "Memphis", "province": "US-TN"}}],
}

# Not yet open for investment: must be filtered out.
COMING_SOON_OFFERING: dict[str, Any] = {
    "shortName": "teaser",
    "name": "The Teaser",
    "status": "COMING_SOON",
    "type": "IPO",
    "assetType": "STR",
    "sharePrice": 10.0,
    "minTransactionAmount": 100.0,
    "fundedPercent": 0.0,
    "targetRaiseAmount": 250_000.0,
    "totalPurchasePrice": 500_000.0,
    "latestDividend": None,
    "properties": [{"purchasePrice": 500_000.0,
                    "address": {"city": "Boise", "province": "US-ID"}}],
}

CATALOGUE: list[dict[str, Any]] = [
    LTR_WITH_DIVIDEND, LTR_NO_DIVIDEND, STR_WITH_DIVIDEND, FUND_OFFERING,
    FUNDED_OFFERING, COMING_SOON_OFFERING,
]

# Exactly 365 days first-to-last: 10.0 -> 10.6 annualizes to 6%. The extra
# mid-June point pins "last price of the month" for historical_returns rows.
RISING_HISTORY: list[dict[str, Any]] = [
    {"date": "2025-06-01", "sharePrice": 10.0},
    {"date": "2025-06-15", "sharePrice": 10.02},
    {"date": "2025-09-01", "sharePrice": 10.15},
    {"date": "2025-12-01", "sharePrice": 10.3},
    {"date": "2026-03-01", "sharePrice": 10.45},
    {"date": "2026-06-01", "sharePrice": 10.6},
]

# Two points only 14 days apart (< 28): no direct appreciation -> fallback chain.
FLAT_HISTORY: list[dict[str, Any]] = [
    {"date": "2026-06-01", "sharePrice": 10.0},
    {"date": "2026-06-15", "sharePrice": 10.0},
]

# A single point can never annualize -> fallback chain.
SINGLE_POINT_HISTORY: list[dict[str, Any]] = [
    {"date": "2026-06-01", "sharePrice": 15.0},
]

# Keyed by shortName, as the share-prices endpoint is; the fund has no history.
SHARE_PRICES: dict[str, list[dict[str, Any]]] = {
    "maple": RISING_HISTORY,
    "birch": FLAT_HISTORY,
    "dune": SINGLE_POINT_HISTORY,
}
