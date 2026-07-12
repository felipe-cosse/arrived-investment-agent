"""App factory: `create_app()` wires middleware, the lifespan, and routers (§4).

The lifespan builds the object graph (single DuckDB connection, R6/R7) and, by
default, purges any leftover seed demo rows so the runtime only ever shows
data loaded from Arrived's catalogue (amended R21). Seeding the demo fixture
requires the test/dev-only SEED_DEMO_DATA flag. The connection closes on
shutdown; tests pass a `Settings` pointing at a tmp database.
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
    routes_region,
)
from app.config import Settings
from app.dependencies import build_state
from infrastructure.seed import SEED_OFFERING_IDS, seed_all

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the process's single connection; purge (or opt-in seed) demo rows (R6)."""
    settings = cast(Settings, app.state.settings)
    state = build_state(settings)
    app.state.arrived = state
    if settings.seed_demo_data:  # test/dev-only escape hatch (amended R21)
        if state.offerings.stats()["offerings"]["rows"] == 0:
            counts = seed_all(state.offerings)
            logger.info("seeded_empty_database counts=%s", counts)
    else:  # default: old volumes lose their demo rows at boot
        logger.info("purged_seed_rows n=%d",
                    state.offerings.purge_seed_data(SEED_OFFERING_IDS))
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
    for module in (routes_offerings, routes_region, routes_plan, routes_plans,
                   routes_chat, routes_admin, routes_meta):
        app.include_router(module.router)
    return app


app = create_app()
