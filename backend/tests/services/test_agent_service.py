from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from services.agent_service import AgentService
from services.market_service import MarketService
from services.plan_service import PlanService
from services.tools import ToolDispatcher


class _FakeStream:
    def __init__(self, events: list[Any], final: Any) -> None:
        self._events, self._final = events, final
    async def __aenter__(self): return self
    async def __aexit__(self, *exc: Any) -> bool: return False
    def __aiter__(self):
        self._it = iter(self._events); return self
    async def __anext__(self):
        try: return next(self._it)
        except StopIteration as e: raise StopAsyncIteration from e
    async def get_final_message(self): return self._final


class FakeLLM:
    """Scripted LLMClient; records kwargs of every call."""
    def __init__(self, turns: list[tuple[list[Any], Any]]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []
    def stream(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        events, final = self._turns.pop(0)
        return _FakeStream(events, final)


def _parse(chunks: list[str]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for c in chunks:
        lines = c.strip().split("\n")
        out.append((lines[0].removeprefix("event: "),
                    json.loads(lines[1].removeprefix("data: "))))
    return out


def _service(repo, plans, llm: FakeLLM) -> AgentService:
    plan_service = PlanService(repo, plans)
    dispatcher = ToolDispatcher(repo, plan_service, MarketService(repo))
    return AgentService(llm=llm, tools=dispatcher)


@pytest.fixture()
def scripted(repo, plans) -> tuple[AgentService, FakeLLM]:
    tool_block = SimpleNamespace(type="tool_use", name="build_investment_plan",
                                 id="toolu_1", input={"amount": 1000})
    turn1 = ([SimpleNamespace(type="content_block_start", content_block=tool_block)],
             SimpleNamespace(stop_reason="tool_use", content=[tool_block]))
    turn2 = ([SimpleNamespace(type="content_block_delta",
                              delta=SimpleNamespace(type="text_delta", text="Done."))],
             SimpleNamespace(stop_reason="end_turn", content=[]))
    llm = FakeLLM([turn1, turn2])
    return _service(repo, plans, llm), llm


async def test_event_sequence_and_tool_feedback(scripted) -> None:
    agent, llm = scripted
    chunks = [c async for c in agent.run([{"role": "user", "content": "Invest $1000"}])]
    events = _parse(chunks)
    assert [e for e, _ in events] == ["tool_started", "plan_result", "text_delta", "done"]
    plan = dict(events)["plan_result"]
    assert plan["tool"] == "build_investment_plan"
    assert plan["result"]["feasible"] is True
    assert plan["result"]["summary"]["total_invested_usd"] <= 1000
    assert dict(events)["done"] == {"stop_reason": "end_turn"}
    followup = llm.calls[1]["messages"][-1]
    assert followup["role"] == "user"
    assert followup["content"][0]["type"] == "tool_result"
    assert followup["content"][0]["tool_use_id"] == "toolu_1"


async def test_history_is_truncated_server_side(repo, plans) -> None:
    llm = FakeLLM([([], SimpleNamespace(stop_reason="end_turn", content=[]))])
    agent = _service(repo, plans, llm)
    history = [{"role": "user", "content": f"m{i}"} for i in range(120)]
    _ = [c async for c in agent.run(history)]
    sent = llm.calls[0]["messages"]
    assert len(sent) <= 40                      # MAX_HISTORY_MESSAGES default
    assert sent[-1]["content"] == "m119"        # most recent kept
