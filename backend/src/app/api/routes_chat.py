"""POST /api/chat: validate the transcript and stream agent SSE frames (R4, §9)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.sse import sse_response
from app.dependencies import AgentDep

router = APIRouter(prefix="/api", tags=["chat"])


class ChatMessage(BaseModel):
    """One visible transcript message sent by the client."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=25_000)


class ChatRequest(BaseModel):
    """POST /api/chat body: the full visible transcript — the server is stateless (§9)."""

    messages: list[ChatMessage] = Field(min_length=1, max_length=200)


@router.post("/chat")
async def chat(body: ChatRequest, agent: AgentDep) -> StreamingResponse:
    """Stream one agent exchange as SSE; the dependency 503s when no key is set (§9)."""
    return sse_response(agent.run([message.model_dump() for message in body.messages]))
