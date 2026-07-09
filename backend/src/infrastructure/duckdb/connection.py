"""Process-wide DuckDB connection owner: opens the file once and initializes schema.

R6/R7: the API process is the sole owner of the database file, and this class holds
its ONE `read_write` connection. Every repository operation goes through `cursor()`,
which is thread-safe. NEVER open a second read-write connection to the same file.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS offerings (
        id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, market VARCHAR NOT NULL,
        property_type VARCHAR NOT NULL
            CHECK (property_type IN ('single_family','vacation_rental','fund')),
        status VARCHAR NOT NULL DEFAULT 'available'
            CHECK (status IN ('available','funded','closed')),
        share_price_usd DOUBLE NOT NULL, min_investment_usd DOUBLE NOT NULL,
        projected_dividend_yield DOUBLE NOT NULL,
        projected_appreciation DOUBLE NOT NULL,
        funded_pct DOUBLE,
        property_value_usd DOUBLE,
        leverage_pct DOUBLE,
        as_of TIMESTAMP NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS historical_returns (
        offering_id VARCHAR NOT NULL, month VARCHAR NOT NULL,
        dividend_per_share DOUBLE, share_value_usd DOUBLE,
        PRIMARY KEY (offering_id, month)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_metrics (
        metro VARCHAR NOT NULL, month VARCHAR NOT NULL,
        source VARCHAR NOT NULL,
        metric VARCHAR NOT NULL,
        value DOUBLE NOT NULL, as_of TIMESTAMP NOT NULL,
        PRIMARY KEY (metro, month, source, metric)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_aliases (
        raw_market VARCHAR PRIMARY KEY,
        metro VARCHAR NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS plans (
        id VARCHAR PRIMARY KEY,
        name VARCHAR,
        created_at TIMESTAMP NOT NULL,
        inputs VARCHAR NOT NULL,
        output VARCHAR NOT NULL,
        data_as_of TIMESTAMP NOT NULL
    )
    """,
)


class DuckDBConn:
    """The process's single read-write connection to the DuckDB file (R7)."""

    def __init__(self, db_path: str | Path) -> None:
        """Open (creating if needed) the database at `db_path` and apply the §5 schema."""
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = duckdb.connect(str(path))
        for statement in _SCHEMA_STATEMENTS:
            self._conn.execute(statement)
        logger.info("duckdb_opened path=%s", path)

    def cursor(self) -> duckdb.DuckDBPyConnection:
        """Return a thread-safe cursor sharing this single connection (R7)."""
        return self._conn.cursor()

    def close(self) -> None:
        """Close the underlying connection (application shutdown)."""
        self._conn.close()
        logger.info("duckdb_closed")
