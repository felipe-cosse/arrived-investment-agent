"""REST-boundary validation for existing investment positions."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path):
    """Seeded API over a temporary database."""
    app = create_app(Settings(anthropic_api_key=None, db_path=tmp_path / "api.duckdb",
                              seed_demo_data=True))
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("amount", [0, -1, "NaN", "Infinity"])
def test_rest_rejects_non_positive_or_non_finite_holding(client: TestClient,
                                                         amount: object) -> None:
    response = client.post("/api/plan", json={"amount": 1000, "existing_positions": [{
        "offering_id": "sfr-meridian", "amount_usd": amount}]})
    assert response.status_code == 422


def test_rest_rejects_duplicate_holding_ids(client: TestClient) -> None:
    response = client.post("/api/plan", json={"amount": 1000, "existing_positions": [
        {"offering_id": "sfr-meridian", "amount_usd": 100},
        {"offering_id": " sfr-meridian ", "amount_usd": 200},
    ]})
    assert response.status_code == 422


def test_rest_accepts_one_positive_finite_holding(client: TestClient) -> None:
    response = client.post("/api/plan", json={"amount": 1000, "existing_positions": [{
        "offering_id": "sfr-meridian", "amount_usd": 100}]})
    assert response.status_code == 200
    assert response.json()["feasible"] is True
