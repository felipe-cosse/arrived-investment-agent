"""App factory: `create_app()` wires middleware, lifespan seeding, and routers (§4).

The lifespan builds the object graph (single DuckDB connection, R6/R7), seeds
an empty database so the app works fully offline (R21), and closes the
connection on shutdown. Tests pass a `Settings` pointing at a tmp database.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    routes_admin,
    routes_chat,
    routes_meta,
    routes_offerings,
    routes_plan,
    routes_plans,
)
from app.config import Settings
from app.dependencies import build_state
from infrastructure.seed import seed_all

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the process's single connection, seed if empty, close on shutdown (R6)."""
    settings = cast(Settings, app.state.settings)
    state = build_state(settings)
    app.state.arrived = state
    if state.offerings.stats()["offerings"]["rows"] == 0:
        counts = seed_all(state.offerings)
        logger.info("seeded_empty_database counts=%s", counts)
    yield
    state.conn.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI app (App Factory, §3); settings default to the environment."""
    resolved = settings if settings is not None else Settings()
    app = FastAPI(title="Arrived Investment Agent", lifespan=_lifespan)
    app.state.settings = resolved
    origins = resolved.cors_origin_list
    if origins:  # dev only (§13); the nginx proxy makes prod same-origin
        app.add_middleware(CORSMiddleware, allow_origins=origins,
                           allow_methods=["*"], allow_headers=["*"])
    for module in (routes_offerings, routes_plan, routes_plans,
                   routes_chat, routes_admin, routes_meta):
        app.include_router(module.router)
    return app


app = create_app()
