"""Settings guards: R17 truncation stays enforceable; demo seeding stays opt-in."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_max_history_messages_rejects_zero() -> None:
    """A zero (or negative) limit would silently disable R17 truncation."""
    with pytest.raises(ValidationError):
        Settings(max_history_messages=0)


def test_max_history_messages_accepts_minimum() -> None:
    """The smallest valid limit, 1, is accepted."""
    assert Settings(max_history_messages=1).max_history_messages == 1


def test_seed_demo_data_defaults_off() -> None:
    """SEED_DEMO_DATA is a test/dev escape hatch; the runtime never seeds by default."""
    assert Settings().seed_demo_data is False
