"""Protocol ports that decouple services from concrete adapters (spec §3, R2/ISP).

Services import only these Protocols; DuckDB, httpx, and the Anthropic SDK stay
behind `infrastructure/` adapters wired in the composition root (R3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from domain.models import MetricRow, Offering, PlanRecord, ReturnRecord


class OfferingReader(Protocol):
    """Read-side access to offerings, return history, and market enrichment."""

    def list_offerings(
        self,
        *,
        market: str | None = None,
        property_type: str | None = None,
        min_dividend_yield: float | None = None,
        limit: int | None = None,
    ) -> list[Offering]:
        """Return offerings matching the given filters."""
        ...

    def get_offering(self, offering_id: str) -> Offering | None:
        """Return one offering by id, or None when unknown."""
        ...

    def get_returns(self, offering_id: str, months: int) -> list[ReturnRecord]:
        """Return up to `months` of monthly history, oldest first."""
        ...

    def get_market_metrics(self, metro: str, months: int) -> list[MetricRow]:
        """Return enrichment rows for a canonical metro over recent months."""
        ...

    def get_metro_for_market(self, raw_market: str) -> str | None:
        """Resolve a raw offering market to its canonical metro slug (R11)."""
        ...

    def stats(self) -> dict[str, Any]:
        """Row counts and latest `as_of` per table, for `/api/meta` staleness."""
        ...


class OfferingWriter(Protocol):
    """Write-side idempotent upserts for seed and enrichment data (R8)."""

    def upsert_offerings(self, rows: Sequence[Offering]) -> int:
        """Upsert offerings by id; returns the row count written."""
        ...

    def upsert_returns(self, rows: Sequence[ReturnRecord]) -> int:
        """Upsert monthly returns keyed by (offering_id, month)."""
        ...

    def upsert_market_metrics(self, rows: Sequence[MetricRow]) -> int:
        """Upsert enrichment rows keyed by (metro, month, source, metric)."""
        ...

    def upsert_market_aliases(self, rows: Sequence[tuple[str, str]]) -> int:
        """Upsert (raw_market, metro) alias rows for entity resolution (R11)."""
        ...


class PlanStore(Protocol):
    """Insert/delete-only store for immutable saved-plan snapshots (R16)."""

    def save(self, record: PlanRecord) -> str:
        """Persist a snapshot and return its id."""
        ...

    def list_plans(self) -> list[dict[str, Any]]:
        """Return snapshot summaries, newest first."""
        ...

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        """Return one full snapshot by id, or None when unknown."""
        ...

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a snapshot; True when a row was removed."""
        ...

    def stats(self) -> dict[str, Any]:
        """Row counts for `/api/meta`."""
        ...


class MarketDataSource(Protocol):
    """One external enrichment provider (Zillow, FRED, Census) behind an Adapter."""

    name: str

    def fetch(self, metros: list[str]) -> list[MetricRow]:
        """Fetch metric rows for the given canonical metros; never partial-crash (R20)."""
        ...


class LLMStream(Protocol):
    """Async streaming handle structurally mirroring the Anthropic SDK stream."""

    async def __aenter__(self) -> LLMStream:
        """Enter the stream context."""
        ...

    async def __aexit__(self, *exc_info: Any) -> bool:
        """Exit the stream context without suppressing errors."""
        ...

    def __aiter__(self) -> AsyncIterator[Any]:
        """Iterate raw stream events (content_block_start, content_block_delta, ...)."""
        ...

    async def get_final_message(self) -> Any:
        """Return the final message (`.stop_reason`, `.content`) after the stream ends."""
        ...


class LLMClient(Protocol):
    """Minimal structural surface of the async Anthropic client used by the agent (§3)."""

    def stream(
        self,
        *,
        model: str,
        max_tokens: int,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> LLMStream:
        """Open one streamed model turn; the Appendix A fake pins this contract."""
        ...
