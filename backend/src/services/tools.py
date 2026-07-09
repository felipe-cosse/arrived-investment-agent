"""ToolDispatcher: Anthropic tool JSON schemas plus synchronous dispatch (§8).

Owns `.definitions` (the schemas sent with every model turn) and
`.dispatch(name, args)`, which raises KeyError on unknown tool names. Handler
failures raise; the agent loop converts them to `tool_error` events (R28).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from domain.ports import OfferingReader
from services.market_service import MarketService
from services.plan_service import DEFAULT_HORIZON_YEARS, DEFAULT_RISK_PROFILE, PlanService

# §8: which typed SSE event carries each tool's result.
RESULT_EVENTS: dict[str, str] = {
    "get_offerings": "offerings_result",
    "get_offering_details": "offering_details_result",
    "get_historical_returns": "returns_result",
    "get_market_context": "market_context_result",
    "build_investment_plan": "plan_result",
    "save_plan": "plan_saved_result",
    "list_saved_plans": "saved_plans_result",
}

_PLAN_PROPS: dict[str, Any] = {
    "amount": {"type": "number", "description": "New money to invest, in USD."},
    "risk_profile": {"type": "string", "enum": ["conservative", "balanced", "aggressive"],
                     "description": f"Risk profile; defaults to {DEFAULT_RISK_PROFILE}."},
    "horizon_years": {"type": "integer", "minimum": 1, "maximum": 30,
                      "description": f"Projection horizon; defaults to {DEFAULT_HORIZON_YEARS}."},
    "existing_positions": {
        "type": "array",
        "description": "Money already invested, per offering.",
        "items": {"type": "object",
                  "properties": {"offering_id": {"type": "string"},
                                 "amount_usd": {"type": "number"}},
                  "required": ["offering_id", "amount_usd"]},
    },
}


def _tool(name: str, description: str, properties: dict[str, Any],
          required: list[str]) -> dict[str, Any]:
    """Shape one Anthropic tool definition."""
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": properties, "required": required}}


_DEFINITIONS: list[dict[str, Any]] = [
    _tool("get_offerings", "List offerings, optionally filtered.",
          {"market": {"type": "string"},
           "property_type": {"type": "string",
                             "enum": ["single_family", "vacation_rental", "fund"]},
           "min_dividend_yield": {"type": "number"},
           "limit": {"type": "integer", "minimum": 1}}, []),
    _tool("get_offering_details", "One offering plus its 12-month history.",
          {"offering_id": {"type": "string"}}, ["offering_id"]),
    _tool("get_historical_returns", "Monthly dividend/share-value series for an offering.",
          {"offering_id": {"type": "string"},
           "months": {"type": "integer", "minimum": 1, "maximum": 60}}, ["offering_id"]),
    _tool("get_market_context", "Enrichment view of one market (raw name).",
          {"market": {"type": "string"}}, ["market"]),
    _tool("build_investment_plan",
          "Run the deterministic allocation engine; momentum is applied automatically.",
          _PLAN_PROPS, ["amount"]),
    _tool("save_plan", "Re-run the engine and persist an immutable snapshot.",
          {**_PLAN_PROPS, "name": {"type": "string"}}, ["amount"]),
    _tool("list_saved_plans", "Summaries of saved plan snapshots.", {}, []),
]


class ToolDispatcher:
    """Maps tool names to service calls; every result is a JSON-serializable dict."""

    def __init__(self, reader: OfferingReader, plan_service: PlanService,
                 market_service: MarketService) -> None:
        """Wire the read port and the two orchestration services (R2)."""
        self._reader = reader
        self._plans = plan_service
        self._market = market_service
        self._handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "get_offerings": self._get_offerings,
            "get_offering_details": self._get_offering_details,
            "get_historical_returns": self._get_historical_returns,
            "get_market_context": self._get_market_context,
            "build_investment_plan": self._plans.build_plan,
            "save_plan": self._plans.save_plan,
            "list_saved_plans": self._list_saved_plans,
        }

    @property
    def definitions(self) -> list[dict[str, Any]]:
        """Anthropic tool schemas sent with every model turn (§8)."""
        return _DEFINITIONS

    def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Run one tool; unknown names raise KeyError (§8), bad args raise to the loop."""
        handler = self._handlers[name]
        return handler(**args)

    def _get_offerings(self, market: str | None = None, property_type: str | None = None,
                       min_dividend_yield: float | None = None,
                       limit: int | None = None) -> dict[str, Any]:
        """Filtered offering list."""
        rows = self._reader.list_offerings(market=market, property_type=property_type,
                                           min_dividend_yield=min_dividend_yield, limit=limit)
        return {"count": len(rows), "offerings": [r.model_dump(mode="json") for r in rows]}

    def _get_offering_details(self, offering_id: str) -> dict[str, Any]:
        """One offering plus 12 months of history; unknown ids fail loud (R28)."""
        offering = self._reader.get_offering(offering_id)
        if offering is None:
            raise ValueError(f"unknown offering_id: {offering_id}")
        history = self._reader.get_returns(offering_id, 12)
        return {"offering": offering.model_dump(mode="json"),
                "history": [r.model_dump(mode="json") for r in history]}

    def _get_historical_returns(self, offering_id: str, months: int = 12) -> dict[str, Any]:
        """Monthly series for an offering, `months` clamped to 1-60 (§8)."""
        if self._reader.get_offering(offering_id) is None:
            raise ValueError(f"unknown offering_id: {offering_id}")
        window = max(1, min(60, int(months)))
        rows = self._reader.get_returns(offering_id, window)
        return {"offering_id": offering_id, "months": window,
                "returns": [r.model_dump(mode="json") for r in rows]}

    def _get_market_context(self, market: str) -> dict[str, Any]:
        """Enrichment context for a raw market name; unmapped markets fail loud (R28)."""
        context = self._market.context_for_market(market)
        if context is None:
            raise ValueError(f"unknown market: {market}")
        return {"market": market, **context.model_dump(mode="json")}

    def _list_saved_plans(self) -> dict[str, Any]:
        """Summaries of saved snapshots, newest first."""
        return {"plans": self._plans.list_plans()}
