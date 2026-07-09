"""SSE response helper for the API layer: media type and anti-buffering headers (§9).

Frame *formatting* lives beside the agent loop (`services.agent_service.sse`)
because the canonical Appendix A test consumes formatted frames straight from
`AgentService.run`; this module owns the HTTP envelope those frames travel in.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def sse_response(frames: AsyncIterator[str]) -> StreamingResponse:
    """Wrap pre-formatted SSE frames in a `text/event-stream` response (§9 headers)."""
    return StreamingResponse(frames, media_type="text/event-stream", headers=dict(_SSE_HEADERS))
