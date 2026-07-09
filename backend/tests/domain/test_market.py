"""Behavioral tests for pure market math: yoy/norm/momentum incl. neutrality (§7, §12)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from domain.market import MarketContext, momentum, norm, yoy
from domain.models import MetricRow

AS_OF = datetime(2026, 1, 1, tzinfo=UTC)


def _row(month: str, value: float, source: str = "seed") -> MetricRow:
    return MetricRow(metro="nashville-tn", month=month, source=source,
                     metric="home_value_index", value=value, as_of=AS_OF)


def test_yoy_latest_vs_twelve_months_back() -> None:
    series = [_row("2025-01", 100.0), _row("2025-06", 102.0), _row("2026-01", 105.0)]
    assert yoy(series) == pytest.approx(0.05)


def test_yoy_missing_data_is_none() -> None:
    assert yoy([]) is None
    assert yoy([_row("2026-01", 105.0)]) is None  # no month 12 back


def test_yoy_prefers_live_source_over_seed() -> None:
    series = [_row("2025-01", 100.0), _row("2026-01", 105.0),
              _row("2026-01", 110.0, source="zillow_zhvi")]
    assert yoy(series) == pytest.approx(0.10)


def test_norm_clamps_to_unit_interval() -> None:
    assert norm(-0.10, -0.05, 0.10) == 0.0
    assert norm(0.20, -0.05, 0.10) == 1.0
    assert norm(0.025, -0.05, 0.10) == pytest.approx(0.5)


def test_momentum_neutral_when_no_signals() -> None:
    assert momentum(None, None) == 0.5


def test_momentum_uses_whichever_signal_is_present() -> None:
    assert momentum(0.10, None) == 1.0
    assert momentum(None, -0.05) == 0.0
    assert momentum(0.10, -0.05) == pytest.approx(0.5)


def test_market_context_defaults_are_neutral() -> None:
    ctx = MarketContext(metro="boise-id")
    assert ctx.momentum == 0.5
    assert ctx.home_value_yoy is None and ctx.rent_yoy is None
