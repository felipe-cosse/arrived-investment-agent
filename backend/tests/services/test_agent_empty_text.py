"""Regression: real models emit an empty text block beside a tool_use, and
echoing it back on the next turn trips Anthropic 400 'text content blocks must
be non-empty'. The agent loop must drop empty text blocks before re-sending
assistant content. Reuses the canonical scripted fakes (Appendix A untouched).
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.services.test_agent_service import FakeLLM, _parse, _service


async def test_empty_assistant_text_block_is_not_echoed(repo, plans) -> None:
    empty_text = SimpleNamespace(type="text", text="")
    tool_block = SimpleNamespace(type="tool_use", name="build_investment_plan",
                                 id="toolu_1", input={"amount": 1000})
    turn1 = ([SimpleNamespace(type="content_block_start", content_block=tool_block)],
             SimpleNamespace(stop_reason="tool_use", content=[empty_text, tool_block]))
    turn2 = ([SimpleNamespace(type="content_block_delta",
                              delta=SimpleNamespace(type="text_delta", text="Done."))],
             SimpleNamespace(stop_reason="end_turn", content=[]))
    llm = FakeLLM([turn1, turn2])
    agent = _service(repo, plans, llm)

    events = _parse([c async for c in agent.run([{"role": "user", "content": "Invest $1000"}])])
    assert "error" not in [name for name, _ in events]

    assistant = next(m for m in llm.calls[1]["messages"] if m["role"] == "assistant")
    blocks = assistant["content"]
    assert all(b["type"] != "text" or b["text"].strip() != "" for b in blocks)
    assert any(b["type"] == "tool_use" for b in blocks)  # the real content survives
