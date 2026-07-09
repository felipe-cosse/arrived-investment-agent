"""Settings validation guards: MAX_HISTORY_MESSAGES must keep R17 enforceable."""

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
