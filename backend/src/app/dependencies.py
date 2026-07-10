"""Composition root: the one place concrete adapters are constructed and wired (R3).

`build_state` creates the process's single DuckDB connection (R7), the
repositories, services, dispatcher, and — when an API key is configured — the
Anthropic-backed agent, exactly once per process. Routers reach everything
through the FastAPI `Depends` providers below and never build adapters (R2/R4).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, cast

from fastapi import Depends, HTTPException, Request

from app.config import Settings
from domain.ports import MarketDataSource, OfferingReader, OfferingWriter, PlanStore
from infrastructure.anthropic_client import create_llm_client
from infrastructure.arrived.fetcher import ArrivedCatalogue
from infrastructure.arrived.refresh import refresh_offerings
from infrastructure.duckdb.connection import DuckDBConn
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.duckdb.plans_repo import PlansRepo
from infrastructure.enrichment.refresh import build_sources, refresh_all
from services.agent_service import AgentService
from services.market_service import MarketService
from services.plan_service import PlanService
from services.tools import ToolDispatcher

logger = logging.getLogger(__name__)

RefreshRunner = Callable[[], dict[str, dict[str, Any]]]


@dataclass
class AppState:
    """Everything the process wires once: connection, repos, services, agent."""

    settings: Settings
    conn: DuckDBConn
    offerings: OfferingsRepo
    plans: PlansRepo
    plan_service: PlanService
    dispatcher: ToolDispatcher
    agent: AgentService | None
    sources: list[MarketDataSource]


def build_state(settings: Settings) -> AppState:
    """Construct the object graph for one process (single composition root, R3)."""
    conn = DuckDBConn(settings.db_path)
    offerings = OfferingsRepo(conn)
    plans = PlansRepo(conn)
    plan_service = PlanService(offerings, plans)
    dispatcher = ToolDispatcher(offerings, plan_service, MarketService(offerings))
    agent: AgentService | None = None
    if settings.anthropic_api_key:
        agent = AgentService(
            llm=create_llm_client(settings.anthropic_api_key),
            tools=dispatcher,
            model=settings.anthropic_model,
            max_tokens=settings.max_tokens,
            max_turns=settings.max_agent_turns,
            max_history=settings.max_history_messages,
        )
    else:
        logger.info("agent_disabled reason=no_anthropic_api_key")
    sources = build_sources(
        zhvi_url=settings.zillow_zhvi_url, zori_url=settings.zillow_zori_url,
        fred_api_key=settings.fred_api_key, census_api_key=settings.census_api_key)
    return AppState(settings=settings, conn=conn, offerings=offerings, plans=plans,
                    plan_service=plan_service, dispatcher=dispatcher, agent=agent,
                    sources=sources)


def get_state(request: Request) -> AppState:
    """The AppState the lifespan attached; cast because Starlette state is untyped."""
    return cast(AppState, request.app.state.arrived)


def get_reader(request: Request) -> OfferingReader:
    """Read-side offerings port for routers."""
    return get_state(request).offerings


def get_writer(request: Request) -> OfferingWriter:
    """Write-side offerings port; only the refresh runner needs it."""
    return get_state(request).offerings


def get_plan_store(request: Request) -> PlanStore:
    """Saved-plan snapshot store."""
    return get_state(request).plans


def get_plan_service(request: Request) -> PlanService:
    """Deterministic planner orchestration service."""
    return get_state(request).plan_service


def get_sources(request: Request) -> list[MarketDataSource]:
    """Enabled enrichment sources; the override point for tests (R25)."""
    return list(get_state(request).sources)


def get_agent_service(request: Request) -> AgentService:
    """The chat agent, or 503 when ANTHROPIC_API_KEY is not configured (§9)."""
    agent = get_state(request).agent
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not set; /api/chat is unavailable.",
        )
    return agent


def get_refresh_runner(
    sources: Annotated[list[MarketDataSource], Depends(get_sources)],
    reader: Annotated[OfferingReader, Depends(get_reader)],
    writer: Annotated[OfferingWriter, Depends(get_writer)],
) -> RefreshRunner:
    """Bind the enrichment refresh to this process's sources and repos (R3/R6)."""

    def run() -> dict[str, dict[str, Any]]:
        """Run every enabled source with per-source isolation (R20)."""
        return refresh_all(sources, reader=reader, writer=writer)

    return run


OfferingsRefreshRunner = Callable[[], dict[str, Any]]


def get_offerings_refresh_runner(request: Request) -> OfferingsRefreshRunner:
    """Bind the live catalogue refresh to this process's repo and settings (R3/R6)."""
    state = get_state(request)

    def run() -> dict[str, Any]:
        """Fetch, map, upsert the buyable Arrived catalogue; purge seeds on success."""
        catalogue = ArrivedCatalogue(state.settings.arrived_api_url)
        return refresh_offerings(catalogue, repo=state.offerings)

    return run


ReaderDep = Annotated[OfferingReader, Depends(get_reader)]
PlanStoreDep = Annotated[PlanStore, Depends(get_plan_store)]
PlanServiceDep = Annotated[PlanService, Depends(get_plan_service)]
AgentDep = Annotated[AgentService, Depends(get_agent_service)]
RefreshRunnerDep = Annotated[RefreshRunner, Depends(get_refresh_runner)]
OfferingsRefreshRunnerDep = Annotated[
    OfferingsRefreshRunner, Depends(get_offerings_refresh_runner)]
