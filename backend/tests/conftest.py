from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.duckdb.connection import DuckDBConn
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.duckdb.plans_repo import PlansRepo
from infrastructure.seed import seed_all


@pytest.fixture()
def conn(tmp_path: Path) -> DuckDBConn:
    """One connection per test, per R7. Tests never touch the network."""
    return DuckDBConn(tmp_path / "test.duckdb")


@pytest.fixture()
def repo(conn: DuckDBConn) -> OfferingsRepo:
    r = OfferingsRepo(conn)
    seed_all(r)
    return r


@pytest.fixture()
def plans(conn: DuckDBConn) -> PlansRepo:
    return PlansRepo(conn)
