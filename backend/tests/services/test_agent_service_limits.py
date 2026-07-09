"""Limit-guard tests for AgentService: §9 done stop_reason union and the R17 floor.

Complements the canonical Appendix A suite (kept verbatim): the live API can
return stop reasons outside the §9 union (stop_sequence, refusal, ...), and a
zero max_history must never disable server-side truncation.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from services.agent_service import AgentService
from services.market_service import MarketService
from services.plan_service import PlanService
from services.tools import ToolDispatcher


class _FakeStream:
    """Async context manager + iterator matching the LLMClient stream contract."""

    def __init__(self, events: list[Any], final: Any) -> None:
        self._events, self._final = events, final

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def __aiter__(self) -> _FakeStream:
        self._it = iter(self._events)
        return self

    async def __anext__(self) -> Any:
        try:
            return next(self._it)
        except StopIteration as e:
            raise StopAsyncIteration from e

    async def get_final_message(self) -> Any:
        return self._final


class FakeLLM:
    """Scripted LLMClient; records the kwargs of every call."""

    def __init__(self, turns: list[tuple[list[Any], Any]]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []

    def stream(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        events, final = self._turns.pop(0)
        return _FakeStream(events, final)


def _events(chunks: list[str]) -> list[tuple[str, dict[str, Any]]]:
    """Parse SSE frames into (event, data) pairs."""
    out: list[tuple[str, dict[str, Any]]] = []
    for chunk in chunks:
        lines = chunk.strip().split("\n")
        out.append((lines[0].removeprefix("event: "),
                    json.loads(lines[1].removeprefix("data: "))))
    return out


def _service(repo: Any, plans: Any, llm: FakeLLM, **kwargs: Any) -> AgentService:
    """AgentService over a seeded repo, a real dispatcher, and the scripted LLM."""
    plan_service = PlanService(repo, plans)
    dispatcher = ToolDispatcher(repo, plan_service, MarketService(repo))
    return AgentService(llm=llm, tools=dispatcher, **kwargs)


async def test_out_of_contract_stop_reason_normalizes_to_end_turn(repo, plans) -> None:
    """A live-API stop_reason outside the §9 union is emitted as end_turn."""
    llm = FakeLLM([([], SimpleNamespace(stop_reason="stop_sequence", content=[]))])
    agent = _service(repo, plans, llm)
    chunks = [c async for c in agent.run([{"role": "user", "content": "hi"}])]
    assert dict(_events(chunks))["done"] == {"stop_reason": "end_turn"}


async def test_max_tokens_stop_reason_passes_through(repo, plans) -> None:
    """In-union stop reasons are emitted unchanged."""
    llm = FakeLLM([([], SimpleNamespace(stop_reason="max_tokens", content=[]))])
    agent = _service(repo, plans, llm)
    chunks = [c async for c in agent.run([{"role": "user", "content": "hi"}])]
    assert dict(_events(chunks))["done"] == {"stop_reason": "max_tokens"}


async def test_zero_max_history_still_truncates(repo, plans) -> None:
    """max_history=0 must not disable R17 truncation; the floor keeps one message."""
    llm = FakeLLM([([], SimpleNamespace(stop_reason="end_turn", content=[]))])
    agent = _service(repo, plans, llm, max_history=0)
    history = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    _ = [c async for c in agent.run(history)]
    sent = llm.calls[0]["messages"]
    assert len(sent) == 1
    assert sent[0]["content"] == "m4"
