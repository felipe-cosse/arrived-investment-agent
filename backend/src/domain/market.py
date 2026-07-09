"""Pure market-enrichment math: YoY change, normalization, momentum (spec §7).

Momentum is a bounded tilt used by the engine, never a gate (R14): offerings in
markets without data score neutral and are never excluded.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from domain.models import MetricRow

SEED_SOURCE = "seed"
NORM_LO = -0.05
NORM_HI = 0.10
NEUTRAL_MOMENTUM = 0.5


def yoy(series: Iterable[MetricRow]) -> float | None:
    """Year-over-year change: latest month vs 12 months back; None if either is missing.

    When both a live source and `seed` provide a month, the live value wins (§7).
    """
    live: dict[str, float] = {}
    seeded: dict[str, float] = {}
    for row in series:
        target = seeded if row.source == SEED_SOURCE else live
        target[row.month] = row.value
    merged = {**seeded, **live}
    if not merged:
        return None
    latest = max(merged)
    prior = f"{int(latest[:4]) - 1:04d}{latest[4:]}"
    base = merged.get(prior)
    if base is None or base == 0:
        return None
    return merged[latest] / base - 1.0


def norm(x: float, lo: float, hi: float) -> float:
    """Clamp `(x - lo) / (hi - lo)` into [0, 1]."""
    return min(1.0, max(0.0, (x - lo) / (hi - lo)))


def momentum(hv_yoy: float | None, rent_yoy: float | None) -> float:
    """Mean of normalized YoY signals that are present; neutral 0.5 when none are."""
    signals = [norm(v, NORM_LO, NORM_HI) for v in (hv_yoy, rent_yoy) if v is not None]
    if not signals:
        return NEUTRAL_MOMENTUM
    return sum(signals) / len(signals)


class MarketContext(BaseModel):
    """Enrichment snapshot of one metro, served by tools and the planner tilt."""

    model_config = ConfigDict(frozen=True)

    metro: str
    home_value_yoy: float | None = None
    rent_yoy: float | None = None
    unemployment_rate: float | None = None
    population: float | None = None
    median_income: float | None = None
    momentum: float = NEUTRAL_MOMENTUM
