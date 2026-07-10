"""POST /api/admin/refresh-offerings behavioral tests (§12 style).

The runner dependency is overridden with a scripted callable (R25) — the route
itself owns no logic (R4) and simply returns whatever report the runner built,
success or error alike.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import get_offerings_refresh_runner
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    """App over a tmp DuckDB, seeded by the lifespan; no API key configured."""
    app = create_app(Settings(anthropic_api_key=None, db_path=tmp_path / "api.duckdb"))
    with TestClient(app) as c:
        yield c


def test_refresh_offerings_returns_runner_report(client) -> None:
    report = {"status": "upserted", "offerings": 4, "returns": 8,
              "aliases": 3, "seeds_retired": 11}
    client.app.dependency_overrides[get_offerings_refresh_runner] = lambda: (lambda: report)
    resp = client.post("/api/admin/refresh-offerings")
    assert resp.status_code == 200
    assert resp.json() == report


def test_refresh_offerings_passes_error_reports_through(client) -> None:
    report = {"status": "error", "detail": "no buyable offerings found"}
    client.app.dependency_overrides[get_offerings_refresh_runner] = lambda: (lambda: report)
    resp = client.post("/api/admin/refresh-offerings")
    assert resp.status_code == 200
    assert resp.json() == report
