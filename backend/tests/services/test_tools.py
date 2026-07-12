"""Behavioral tests for ToolDispatcher (§8, §12).

Every §8 tool dispatches against a seeded tmp DuckDB, every result is
json.dumps-able, and unknown tool names raise KeyError.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.duckdb.plans_repo import PlansRepo
from services.market_service import MarketService
from services.plan_service import PlanService
from services.tools import RESULT_EVENTS, ToolDispatcher

TOOL_NAMES = {
    "get_offerings", "get_offering_details", "get_historical_returns",
    "get_market_context", "build_investment_plan", "save_plan", "list_saved_plans",
}


@pytest.fixture()
def dispatcher(repo: OfferingsRepo, plans: PlansRepo) -> ToolDispatcher:
    """Dispatcher wired over the seeded test database (conftest fixtures)."""
    plan_service = PlanService(repo, plans)
    return ToolDispatcher(repo, plan_service, MarketService(repo))


def _dispatch(dispatcher: ToolDispatcher, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one tool and assert its result round-trips through json.dumps (§12)."""
    result = dispatcher.dispatch(name, args)
    assert result == json.loads(json.dumps(result))
    return result


def test_definitions_cover_every_tool(dispatcher: ToolDispatcher) -> None:
    """One Anthropic schema per §8 tool, each mapped to a typed result event."""
    names = [d["name"] for d in dispatcher.definitions]
    assert set(names) == TOOL_NAMES and len(names) == len(TOOL_NAMES)
    assert set(RESULT_EVENTS) == TOOL_NAMES
    for definition in dispatcher.definitions:
        assert definition["description"]
        assert definition["input_schema"]["type"] == "object"
    plan_schema = next(d for d in dispatcher.definitions
                       if d["name"] == "build_investment_plan")["input_schema"]
    existing = plan_schema["properties"]["existing_positions"]
    assert existing["uniqueItems"] is True
    assert existing["items"]["properties"]["amount_usd"]["exclusiveMinimum"] == 0
    assert existing["items"]["properties"]["offering_id"]["minLength"] == 1


def test_get_offerings_unfiltered_and_filtered(dispatcher: ToolDispatcher) -> None:
    """Unfiltered list returns the 11 seeded offerings; each filter narrows it."""
    everything = _dispatch(dispatcher, "get_offerings", {})
    assert everything["count"] == 11 and len(everything["offerings"]) == 11
    nashville = _dispatch(dispatcher, "get_offerings", {"market": "Nashville, TN"})
    assert [o["id"] for o in nashville["offerings"]] == ["sfr-meridian"]
    funds = _dispatch(dispatcher, "get_offerings", {"property_type": "fund"})
    assert {o["id"] for o in funds["offerings"]} == {"fund-sfr", "fund-credit"}
    high_yield = _dispatch(dispatcher, "get_offerings", {"min_dividend_yield": 0.06})
    assert {o["id"] for o in high_yield["offerings"]} == {
        "vac-roadrunner", "vac-summit", "fund-credit"}
    limited = _dispatch(dispatcher, "get_offerings", {"limit": 3})
    assert limited["count"] == 3


def test_get_offering_details_includes_history(dispatcher: ToolDispatcher) -> None:
    """Details carry the offering plus its 12 seeded months of history."""
    result = _dispatch(dispatcher, "get_offering_details", {"offering_id": "sfr-meridian"})
    assert result["offering"]["id"] == "sfr-meridian"
    assert result["offering"]["market"] == "Nashville, TN"
    assert len(result["history"]) == 12


def test_get_offering_details_unknown_id_raises(dispatcher: ToolDispatcher) -> None:
    """Unknown offering ids fail loud so the loop emits tool_error (R28)."""
    with pytest.raises(ValueError, match="ghost"):
        dispatcher.dispatch("get_offering_details", {"offering_id": "ghost"})


def test_get_historical_returns_windows(dispatcher: ToolDispatcher) -> None:
    """The months window is honored and clamped to the §8 bounds of 1-60."""
    six = _dispatch(dispatcher, "get_historical_returns",
                    {"offering_id": "vac-summit", "months": 6})
    assert six["months"] == 6 and len(six["returns"]) == 6
    assert all(r["offering_id"] == "vac-summit" for r in six["returns"])
    clamped = _dispatch(dispatcher, "get_historical_returns",
                        {"offering_id": "vac-summit", "months": 999})
    assert clamped["months"] == 60 and len(clamped["returns"]) == 12  # 12 seeded


def test_get_market_context_via_alias(dispatcher: ToolDispatcher) -> None:
    """A raw market name resolves through market_aliases to a metric-backed context."""
    result = _dispatch(dispatcher, "get_market_context", {"market": "Nashville, TN"})
    assert result["market"] == "Nashville, TN"
    assert result["metro"] == "nashville-tn"
    assert result["home_value_yoy"] is not None and result["rent_yoy"] is not None
    assert 0.0 <= result["momentum"] <= 1.0


def test_get_market_context_unmapped_market_raises(dispatcher: ToolDispatcher) -> None:
    """Markets with no alias row fail loud rather than fabricating a context (R28)."""
    with pytest.raises(ValueError, match="Atlantis"):
        dispatcher.dispatch("get_market_context", {"market": "Atlantis, XX"})


def test_build_investment_plan_dispatches_engine(dispatcher: ToolDispatcher) -> None:
    """The plan tool runs the engine over seeded offerings with breakdowns (R13)."""
    result = _dispatch(dispatcher, "build_investment_plan",
                       {"amount": 2000, "risk_profile": "balanced", "horizon_years": 5})
    assert result["feasible"] is True
    summary = result["summary"]
    assert summary["total_invested_usd"] + summary["unallocated_cash_usd"] == (
        pytest.approx(2000, abs=0.01))
    for position in result["positions"]:
        assert set(position["score_breakdown"]) == {
            "yield", "appreciation", "momentum", "leverage", "total"}
    assert result["disclaimer"]


def test_build_investment_plan_bad_input_is_infeasible(dispatcher: ToolDispatcher) -> None:
    """Invalid engine input comes back as feasible:false, never an exception (R12)."""
    result = _dispatch(dispatcher, "build_investment_plan",
                       {"amount": 2000, "risk_profile": "yolo"})
    assert result["feasible"] is False and "yolo" in result["reason"]


def test_save_plan_then_list_saved_plans(dispatcher: ToolDispatcher) -> None:
    """save_plan persists a snapshot that list_saved_plans then summarizes."""
    saved = _dispatch(dispatcher, "save_plan",
                      {"amount": 1500, "risk_profile": "conservative", "name": "nest egg"})
    assert saved["name"] == "nest egg" and saved["output"]["feasible"] is True
    assert saved["inputs"]["amount"] == 1500
    listed = _dispatch(dispatcher, "list_saved_plans", {})
    assert [p["id"] for p in listed["plans"]] == [saved["id"]]
    assert listed["plans"][0]["name"] == "nest egg"


def test_list_saved_plans_empty(dispatcher: ToolDispatcher) -> None:
    """No snapshots saved yet -> an empty, still JSON-serializable summary list."""
    assert _dispatch(dispatcher, "list_saved_plans", {}) == {"plans": []}


def test_unknown_tool_raises_key_error(dispatcher: ToolDispatcher) -> None:
    """Dispatching a name outside §8 raises KeyError for the agent loop (§8)."""
    with pytest.raises(KeyError):
        dispatcher.dispatch("summon_money", {})
