"""Thin factory adapting the Anthropic SDK to the LLMClient port (§4, Adapter).

`AsyncAnthropic().messages` already exposes the exact `stream(...)` surface the
port needs. The only mismatch is nominal: the SDK splits the async context
manager from the iterable stream it yields, while the `LLMStream` Protocol —
pinned by the Appendix A fake — collapses both onto one structural type. A
single `cast` at this seam keeps every other layer typed against the port (R2).
"""

from __future__ import annotations

from typing import cast

from anthropic import AsyncAnthropic

from domain.ports import LLMClient


def create_llm_client(api_key: str) -> LLMClient:
    """Build the async Anthropic messages client; the key only comes from env (R23)."""
    return cast(LLMClient, AsyncAnthropic(api_key=api_key).messages)
