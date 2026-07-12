"""Atomic replacement of the live Arrived catalogue snapshot."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import duckdb

from domain.models import Offering, ReturnRecord
from infrastructure.duckdb.connection import DuckDBConn


def _upsert(
    cur: duckdb.DuckDBPyConnection,
    table: str,
    cols: Sequence[str],
    keys: Sequence[str],
    params: list[tuple[Any, ...]],
) -> int:
    """Upsert one row collection through the transaction's single cursor."""
    if not params:
        return 0
    updates = ", ".join(f"{column} = excluded.{column}" for column in cols
                        if column not in keys)
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}"
    )
    cur.executemany(sql, params)
    return len(params)


def _delete_ids(cur: duckdb.DuckDBPyConnection, table: str, column: str,
                ids: Sequence[str]) -> int:
    """Delete rows matching ids and return DuckDB's affected-row count."""
    if not ids:
        return 0
    placeholders = ", ".join("?" for _ in ids)
    row = cur.execute(
        f"DELETE FROM {table} WHERE {column} IN ({placeholders})", list(ids)
    ).fetchone()
    return 0 if row is None else int(row[0])


def replace_live_catalogue(
    conn: DuckDBConn,
    offerings: Sequence[Offering],
    returns: Sequence[ReturnRecord],
    aliases: Sequence[tuple[str, str]],
    seed_ids: Sequence[str],
) -> dict[str, int]:
    """Commit one complete live snapshot or roll every catalogue write back."""
    # Imported lazily to avoid a module cycle with OfferingsRepo's small delegate.
    from infrastructure.duckdb.offering_columns import OFFERING_COLS
    from infrastructure.duckdb.offerings_repo import _RETURN_COLS

    cur = conn.cursor()
    live_ids = [row.id for row in offerings]
    offering_values = [tuple(row.model_dump()[column] for column in OFFERING_COLS)
                       for row in offerings]
    return_values = [tuple(row.model_dump()[column] for column in _RETURN_COLS)
                     for row in returns]
    try:
        cur.execute("BEGIN TRANSACTION")
        offering_count = _upsert(cur, "offerings", OFFERING_COLS, ("id",),
                                 offering_values)
        return_count = _upsert(cur, "historical_returns", _RETURN_COLS,
                               ("offering_id", "month"), return_values)
        alias_count = _upsert(cur, "market_aliases", ("raw_market", "metro"),
                              ("raw_market",), [tuple(row) for row in aliases])

        stale_rows = cur.execute(
            "SELECT id FROM offerings WHERE id LIKE 'arrived-%' "
            + (f"AND id NOT IN ({', '.join('?' for _ in live_ids)})" if live_ids else ""),
            live_ids,
        ).fetchall()
        stale_ids = [str(row[0]) for row in stale_rows]
        _delete_ids(cur, "historical_returns", "offering_id", stale_ids)
        _delete_ids(cur, "offerings", "id", stale_ids)
        _delete_ids(cur, "historical_returns", "offering_id", seed_ids)
        seeds_purged = _delete_ids(cur, "offerings", "id", seed_ids)
        cur.execute("DELETE FROM market_metrics WHERE source = 'seed'")
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    return {"offerings": offering_count, "returns": return_count,
            "aliases": alias_count, "seeds_purged": seeds_purged}
