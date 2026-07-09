"""Behavioral API tests (§12): routes, SSE headers, truncation, admin refresh.

Everything runs against a tmp DuckDB seeded by the lifespan; the network is
never touched (R25) — chat uses a scripted fake LLM via dependency override.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_agent_service, get_sources
from app.main import create_app
from domain.models import MetricRow
from infrastructure.enrichment.refresh import MissingApiKeyError
from services.agent_service import AgentService


class _FakeStream:
    """Empty scripted stream: no events, immediate end_turn final message."""

    async def __aenter__(self) -> _FakeStream: return self
    async def __aexit__(self, *exc: Any) -> bool: return False
    def __aiter__(self) -> _FakeStream: return self
    async def __anext__(self) -> Any: raise StopAsyncIteration
    async def get_final_message(self) -> Any:
        return SimpleNamespace(stop_reason="end_turn", content=[])


class _FakeLLM:
    """Records every call's kwargs; each turn ends immediately."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        return _FakeStream()


class _FakeSource:
    """Scripted MarketDataSource: returns rows or raises the configured error."""

    def __init__(self, name: str, rows: list[MetricRow] | None = None,
                 exc: Exception | None = None) -> None:
        self.name = name
        self._rows, self._exc = rows or [], exc
        self.seen_metros: list[str] = []

    def fetch(self, metros: list[str]) -> list[MetricRow]:
        self.seen_metros = metros
        if self._exc is not None:
            raise self._exc
        return self._rows


@pytest.fixture()
def client(tmp_path: Path):
    """App over a tmp DuckDB, seeded by the lifespan; no API key configured."""
    app = create_app(Settings(anthropic_api_key=None, db_path=tmp_path / "api.duckdb"))
    with TestClient(app) as c:
        yield c


def test_offerings_list_and_filters(client) -> None:
    body = client.get("/api/offerings").json()
    assert body["count"] == 11 and len(body["offerings"]) == 11
    funds = client.get("/api/offerings", params={"property_type": "fund"}).json()
    assert {o["id"] for o in funds["offerings"]} == {"fund-credit", "fund-sfr"}
    rich = client.get("/api/offerings", params={"min_dividend_yield": 0.06}).json()
    assert rich["count"] >= 1
    assert all(o["projected_dividend_yield"] >= 0.06 for o in rich["offerings"])
    assert client.get("/api/offerings", params={"limit": 3}).json()["count"] == 3


def test_offering_detail_includes_history_and_404(client) -> None:
    body = client.get("/api/offerings/sfr-meridian").json()
    assert body["offering"]["id"] == "sfr-meridian"
    assert len(body["history"]) == 12
    assert client.get("/api/offerings/nope").status_code == 404


def test_plan_happy_path_and_422(client) -> None:
    resp = client.post("/api/plan", json={"amount": 1000})
    assert resp.status_code == 200
    plan = resp.json()
    assert plan["feasible"] is True
    summary = plan["summary"]
    total = summary["total_invested_usd"] + summary["unallocated_cash_usd"]
    assert total == pytest.approx(1000, abs=0.01)
    assert plan["positions"] and all("score_breakdown" in p for p in plan["positions"])
    assert plan["disclaimer"]
    assert client.post("/api/plan", json={}).status_code == 422
    assert client.post("/api/plan", json={"amount": "lots"}).status_code == 422


def test_plan_infeasible_is_a_result_not_an_error(client) -> None:
    plan = client.post("/api/plan", json={"amount": 50}).json()
    assert plan["feasible"] is False and plan["reason"]


def test_plans_crud_roundtrip(client) -> None:
    created = client.post("/api/plans", json={"amount": 2000, "name": "demo"})
    assert created.status_code == 201
    record = created.json()
    plan_id = record["id"]
    assert record["name"] == "demo" and record["output"]["feasible"] is True
    listed = client.get("/api/plans").json()["plans"]
    assert [p["id"] for p in listed] == [plan_id]
    fetched = client.get(f"/api/plans/{plan_id}")
    assert fetched.status_code == 200
    assert fetched.json()["inputs"]["amount"] == 2000
    assert client.delete(f"/api/plans/{plan_id}").status_code == 204
    assert client.get(f"/api/plans/{plan_id}").status_code == 404
    assert client.delete(f"/api/plans/{plan_id}").status_code == 404


def test_save_plan_rejects_infeasible_inputs(client) -> None:
    assert client.post("/api/plans", json={"amount": 50}).status_code == 422
    assert client.get("/api/plans").json()["plans"] == []


def test_meta_shape(client) -> None:
    meta = client.get("/api/meta").json()
    assert set(meta) == {"offerings", "historical_returns", "market_metrics", "plans"}
    assert meta["offerings"]["rows"] == 11 and meta["offerings"]["latest_as_of"]
    assert meta["historical_returns"]["rows"] > 0
    assert meta["market_metrics"]["rows"] > 0
    assert meta["plans"] == {"rows": 0}


def test_health(client) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_chat_503_without_api_key(client) -> None:
    resp = client.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_chat_truncates_history_and_sets_sse_headers(client) -> None:
    llm = _FakeLLM()
    app = client.app
    dispatcher = app.state.arrived.dispatcher
    app.dependency_overrides[get_agent_service] = (
        lambda: AgentService(llm=llm, tools=dispatcher))
    history = [{"role": "user", "content": f"m{i}"} for i in range(120)]
    resp = client.post("/api/chat", json={"messages": history})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["cache-control"] == "no-cache"
    assert resp.headers["x-accel-buffering"] == "no"
    assert "event: done" in resp.text
    sent = llm.calls[0]["messages"]
    assert len(sent) <= 40                    # MAX_HISTORY_MESSAGES default (R17)
    assert sent[-1]["content"] == "m119"      # most recent kept


def test_admin_refresh_reports_per_source_status(client) -> None:
    row = MetricRow(metro="nashville-tn", month="2025-01", source="fred",
                    metric="unemployment_rate", value=3.4, as_of=datetime.now(UTC))
    ok = _FakeSource("zillow_zhvi", rows=[row])
    no_key = _FakeSource("fred", exc=MissingApiKeyError("FRED_API_KEY unset"))
    boom = _FakeSource("census_acs", exc=RuntimeError("boom"))
    client.app.dependency_overrides[get_sources] = lambda: [ok, no_key, boom]
    resp = client.post("/api/admin/refresh-market-data")
    assert resp.status_code == 200
    assert resp.json() == {
        "zillow_zhvi": {"status": "upserted", "rows": 1},
        "fred": {"status": "skipped_no_key", "rows": 0},
        "census_acs": {"status": "error", "rows": 0},
    }
    assert "nashville-tn" in ok.seen_metros  # metros resolved via aliases (R11)
