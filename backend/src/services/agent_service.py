"""AgentService: truncate history, stream model turns, run tools, emit SSE (§9).

Takes any LLMClient port implementation (DIP) — tests inject a scripted fake.
The loop streams a turn, runs requested tools in a worker thread, feeds
`tool_result` blocks back, and stops at `MAX_AGENT_TURNS` with a `done` event.
Unexpected stream failures become a terminal `error` event, never silence (R28).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from domain.ports import LLMClient
from services.tools import RESULT_EVENTS, ToolDispatcher

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 4096
MAX_AGENT_TURNS = 8
MAX_HISTORY_MESSAGES = 40
# §9 pins the done-event union; the live API can return other stop reasons
# (stop_sequence, refusal, ...) which map conservatively to end_turn.
DONE_STOP_REASONS = frozenset({"end_turn", "max_tokens", "max_turns"})

SYSTEM_PROMPT = (
    "You are the Arrived investment research agent for fractional real-estate offerings.\n"
    "- All data and math come from tools. Never invent offerings, market statistics, or "
    "allocations; always call build_investment_plan to allocate money.\n"
    "- Use score_breakdown to explain why an offering ranks where it does, and "
    "get_market_context for market questions or comparisons.\n"
    "- If the investment amount is missing, ask for it. If the user implies current "
    "holdings, ask for them and pass existing_positions.\n"
    "- Default the risk profile to balanced and say that you did.\n"
    "- After presenting a plan, offer to save it; call save_plan only when the user confirms.\n"
    "- The UI renders tool results as rich components: summarize insights instead of "
    "restating rows or tables.\n"
    "- Briefly note that projections are hypothetical and not financial advice.\n"
    "- Offerings are either seeded demo data or refreshed from Arrived's public catalogue; "
    "market metrics may mix seeded and live sources — say so if asked about data freshness."
)


def sse(event: str, data: dict[str, Any]) -> str:
    """Format one SSE frame per the §9 contract: event line + single-line JSON data."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _normalize_stop_reason(stop_reason: Any) -> str:
    """Clamp a final stop_reason to the §9 done union; anything else becomes end_turn."""
    reason = str(stop_reason)
    return reason if reason in DONE_STOP_REASONS else "end_turn"


def _stream_frame(event: Any) -> str | None:
    """SSE frame for one raw stream event; None for event types we do not surface."""
    if getattr(event, "type", None) == "content_block_start":
        block = event.content_block
        if getattr(block, "type", None) == "tool_use":
            return sse("tool_started", {"tool": block.name, "id": block.id})
    if getattr(event, "type", None) == "content_block_delta":
        delta = event.delta
        if getattr(delta, "type", None) == "text_delta":
            return sse("text_delta", {"text": delta.text})
    return None


def _block_dict(block: Any) -> dict[str, Any]:
    """Serialize an assistant content block for the follow-up messages payload."""
    if getattr(block, "type", None) == "tool_use":
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    return {"type": "text", "text": getattr(block, "text", "")}


class AgentService:
    """Drives the §9 tool-use chat loop over an injected LLMClient."""

    def __init__(self, llm: LLMClient, tools: ToolDispatcher, *,
                 model: str = DEFAULT_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS,
                 max_turns: int = MAX_AGENT_TURNS,
                 max_history: int = MAX_HISTORY_MESSAGES) -> None:
        """Wire the LLM port and dispatcher; limits come from Settings at the root."""
        self._llm = llm
        self._tools = tools
        self._model = model
        self._max_tokens = max_tokens
        self._max_turns = max_turns
        self._max_history = max_history

    async def run(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """Yield SSE frames for one exchange; always ends with `done` or `error`."""
        # Server-side truncation (R17); the floor keeps truncation active even if
        # a caller slips past Settings validation with max_history <= 0.
        convo = list(messages)[-max(1, self._max_history):]
        try:
            for _ in range(self._max_turns):
                async with self._llm.stream(model=self._model, max_tokens=self._max_tokens,
                                            system=SYSTEM_PROMPT, messages=convo,
                                            tools=self._tools.definitions) as stream:
                    async for event in stream:
                        frame = _stream_frame(event)
                        if frame is not None:
                            yield frame
                    final = await stream.get_final_message()
                if final.stop_reason != "tool_use":
                    yield sse("done", {"stop_reason": _normalize_stop_reason(final.stop_reason)})
                    return
                convo.append({"role": "assistant",
                              "content": [_block_dict(b) for b in final.content]})
                results: list[dict[str, Any]] = []
                for block in final.content:
                    if getattr(block, "type", None) != "tool_use":
                        continue
                    async for frame in self._run_tool(block, results):
                        yield frame
                convo.append({"role": "user", "content": results})
            yield sse("done", {"stop_reason": "max_turns"})
        except Exception:
            logger.exception("agent_stream_failed")
            yield sse("error", {"message": "The agent stream failed unexpectedly."})

    async def _run_tool(self, block: Any,
                        results: list[dict[str, Any]]) -> AsyncIterator[str]:
        """Dispatch one tool_use block off-loop; emit its typed event or tool_error."""
        name = str(block.name)
        args = dict(block.input or {})
        try:
            result = await asyncio.to_thread(self._tools.dispatch, name, args)
        except Exception as exc:
            logger.exception("tool_failed tool=%s", name)
            yield sse("tool_error", {"tool": name, "error": str(exc)})
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": str(exc), "is_error": True})
        else:
            yield sse(RESULT_EVENTS[name], {"tool": name, "input": args, "result": result})
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": json.dumps(result)})
