"""Deterministic offline seed data: offerings, returns, metrics, aliases (spec §10).

Windows are relative to today (UTC at seed time): returns cover the 12 most recent
complete months and seeded metrics the 24 most recent — never hard-coded ranges.
All values derive from RNG seed 42, so the app is fully functional offline (R21).
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime

from domain.models import MetricRow, Offering, PropertyType, ReturnRecord
from domain.ports import OfferingWriter

logger = logging.getLogger(__name__)

RNG_SEED = 42
SHARE_PRICE_USD = 10.0
MIN_INVESTMENT_USD = 100.0
RETURN_MONTHS = 12
METRIC_MONTHS = 24
FUND_MARKET = "Diversified"

# (id, name, market, property_type, dividend_yield, appreciation, leverage_pct) — §10.
_OFFERINGS: tuple[tuple[str, str, str, PropertyType, float, float, float], ...] = (
    ("sfr-meridian", "The Meridian", "Nashville, TN", "single_family", 0.041, 0.042, 0.55),
    ("sfr-cedarbrook", "The Cedarbrook", "Chattanooga, TN", "single_family", 0.048, 0.035, 0.60),
    ("sfr-saguaro", "The Saguaro", "Tucson, AZ", "single_family", 0.052, 0.028, 0.62),
    ("sfr-fairview", "The Fairview", "Fayetteville, AR", "single_family", 0.055, 0.025, 0.58),
    ("sfr-larkspur", "The Larkspur", "Colorado Springs, CO", "single_family", 0.037, 0.045, 0.50),
    ("sfr-juniper", "The Juniper", "Boise, ID", "single_family", 0.039, 0.044, 0.52),
    ("vac-roadrunner", "The Roadrunner", "Joshua Tree, CA", "vacation_rental", 0.061, 0.030, 0.45),
    ("vac-summit", "The Summit Chalet", "Gatlinburg, TN", "vacation_rental", 0.067, 0.028, 0.48),
    ("vac-driftwood", "The Driftwood", "Gulf Shores, AL", "vacation_rental", 0.058, 0.033, 0.40),
    ("fund-sfr", "Single Family Residential Fund", FUND_MARKET, "fund", 0.042, 0.031, 0.35),
    ("fund-credit", "Private Credit Fund", FUND_MARKET, "fund", 0.081, 0.000, 0.00),
)


def slugify_market(market: str) -> str:
    """Canonical metro slug for a raw market name: 'Nashville, TN' -> 'nashville-tn'."""
    return market.lower().replace(",", "").replace(" ", "-")


def _recent_months(count: int, now: datetime) -> list[str]:
    """The `count` most recent *complete* months relative to `now`, oldest first."""
    year, month = now.year, now.month  # the current month is incomplete
    out: list[str] = []
    for _ in range(count):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        out.append(f"{year:04d}-{month:02d}")
    return list(reversed(out))


def _offerings(as_of: datetime) -> list[Offering]:
    """The 11 catalog offerings; all share price $10, minimum investment $100 (§10)."""
    return [
        Offering(id=oid, name=name, market=market, property_type=ptype, status="available",
                 share_price_usd=SHARE_PRICE_USD, min_investment_usd=MIN_INVESTMENT_USD,
                 projected_dividend_yield=dy, projected_appreciation=appr,
                 leverage_pct=leverage, as_of=as_of)
        for oid, name, market, ptype, dy, appr, leverage in _OFFERINGS
    ]


def _returns(months: list[str], rng: random.Random) -> list[ReturnRecord]:
    """Monthly dividends at price*yield/12 ±15% noise; values drift at appr/12 ±0.2%."""
    rows: list[ReturnRecord] = []
    for oid, _name, _market, _ptype, dy, appr, _lev in _OFFERINGS:
        value = SHARE_PRICE_USD
        for month in months:
            dividend = SHARE_PRICE_USD * dy / 12 * (1 + rng.uniform(-0.15, 0.15))
            value *= 1 + appr / 12 + rng.uniform(-0.002, 0.002)
            rows.append(ReturnRecord(offering_id=oid, month=month,
                                     dividend_per_share=round(dividend, 4),
                                     share_value_usd=round(value, 4)))
    return rows


def _metrics(months: list[str], rng: random.Random, as_of: datetime) -> list[MetricRow]:
    """Seeded indexes from 100.0 growing at appr (hv) and appr+0.5pp (rent) ±0.1% noise."""
    rows: list[MetricRow] = []
    for _oid, _name, market, _ptype, _dy, appr, _lev in _OFFERINGS:
        if market == FUND_MARKET:
            continue
        metro = slugify_market(market)
        for metric, annual in (("home_value_index", appr), ("rent_index", appr + 0.005)):
            value = 100.0
            for month in months:
                rows.append(MetricRow(metro=metro, month=month, source="seed", metric=metric,
                                      value=round(value, 4), as_of=as_of))
                value *= 1 + annual / 12 + rng.uniform(-0.001, 0.001)
    return rows


def _aliases() -> list[tuple[str, str]]:
    """One (raw_market, metro-slug) alias per non-fund market (§10, R11)."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for _oid, _name, market, _ptype, _dy, _appr, _lev in _OFFERINGS:
        if market == FUND_MARKET or market in seen:
            continue
        seen.add(market)
        out.append((market, slugify_market(market)))
    return out


def seed_all(writer: OfferingWriter) -> dict[str, int]:
    """Idempotently upsert the full offline dataset; returns rows written per table."""
    now = datetime.now(UTC)
    rng = random.Random(RNG_SEED)
    counts = {
        "offerings": writer.upsert_offerings(_offerings(now)),
        "historical_returns": writer.upsert_returns(_returns(_recent_months(RETURN_MONTHS, now),
                                                             rng)),
        "market_metrics": writer.upsert_market_metrics(_metrics(_recent_months(METRIC_MONTHS, now),
                                                                rng, now)),
        "market_aliases": writer.upsert_market_aliases(_aliases()),
    }
    logger.info(
        "seeded offerings=%d returns=%d metrics=%d aliases=%d",
        counts["offerings"], counts["historical_returns"],
        counts["market_metrics"], counts["market_aliases"])
    return counts
