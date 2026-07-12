"""Regression tests for local-only exposure and bounded public request models."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.api.routes_chat import ChatRequest
from app.api.routes_plans import SavePlanRequest

ROOT = Path(__file__).parents[3]


def test_compose_publishes_services_on_loopback_only() -> None:
    """The unauthenticated personal app must not listen on LAN/internet interfaces."""
    compose = (ROOT / "docker-compose.yml").read_text()
    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:5173:80"' in compose
    assert '\n      - "8000:8000"' not in compose
    assert '\n      - "5173:80"' not in compose


def test_chat_request_preserves_normal_history_but_bounds_abuse() -> None:
    """Legitimate long history stays valid while message count and size are finite."""
    messages = [{"role": "user", "content": f"message {i}"} for i in range(120)]
    assert len(ChatRequest(messages=messages).messages) == 120
    with pytest.raises(ValidationError):
        ChatRequest(messages=messages * 2)
    with pytest.raises(ValidationError):
        ChatRequest(messages=[{"role": "user", "content": "x" * 25_001}])


def test_saved_plan_name_is_bounded() -> None:
    """Normal labels remain valid; oversized database/UI payloads are rejected."""
    assert SavePlanRequest(amount=1000, name="x" * 120).name == "x" * 120
    with pytest.raises(ValidationError):
        SavePlanRequest(amount=1000, name="x" * 121)
