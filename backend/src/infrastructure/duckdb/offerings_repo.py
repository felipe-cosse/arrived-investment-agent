"""OfferingsRepo: DuckDB adapter satisfying OfferingReader and OfferingWriter.

All writes are keyed upserts (R8), all reads use explicit column lists (R9), and
offering markets resolve to canonical metros only through `market_aliases` (R11).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from domain.models import MetricRow, Offering, ReturnRecord
from infrastructure.duckdb.connection import DuckDBConn
from infrastructure.duckdb.offering_columns import OFFERING_COLS as _OFFERING_COLS

_RETURN_COLS: tuple[str, ...] = ("offering_id", "month", "dividend_per_share", "share_value_usd")
_METRIC_COLS: tuple[str, ...] = ("metro", "month", "source", "metric", "value", "as_of")


def _tag_utc(row: dict[str, Any]) -> dict[str, Any]:
    """Re-tag a naive `as_of` read from DuckDB as UTC before model construction (R10)."""
    as_of = row["as_of"]
    if isinstance(as_of, datetime) and as_of.tzinfo is None:
        row["as_of"] = as_of.replace(tzinfo=UTC)
    return row


def _upsert_sql(table: str, cols: Sequence[str], keys: Sequence[str]) -> str:
    """Build an idempotent `INSERT ... ON CONFLICT DO UPDATE` statement (R8)."""
    updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in keys)
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) "
        f"VALUES ({', '.join('?' for _ in cols)}) "
        f"ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {updates}"
    )


class OfferingsRepo:
    """Read/write access to offerings, return history, metrics, and aliases."""

    def __init__(self, conn: DuckDBConn) -> None:
        """Share the process's single connection; each call takes a cursor (R7)."""
        self._conn = conn

    # -- OfferingReader ----------------------------------------------------

    def list_offerings(
        self,
        *,
        market: str | None = None,
        property_type: str | None = None,
        min_dividend_yield: float | None = None,
        limit: int | None = None,
    ) -> list[Offering]:
        """Return offerings matching the filters, ordered by id for determinism."""
        clauses: list[str] = []
        params: list[Any] = []
        for clause, value in (("market = ?", market), ("property_type = ?", property_type),
                              ("projected_dividend_yield >= ?", min_dividend_yield)):
            if value is not None:
                clauses.append(clause)
                params.append(value)
        sql = f"SELECT {', '.join(_OFFERING_COLS)} FROM offerings"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        rows = self._conn.cursor().execute(sql, params).fetchall()
        return [Offering.model_validate(_tag_utc(dict(zip(_OFFERING_COLS, r, strict=True))))
                for r in rows]

    def get_offering(self, offering_id: str) -> Offering | None:
        """Return one offering by id, or None when unknown."""
        row = self._conn.cursor().execute(
            f"SELECT {', '.join(_OFFERING_COLS)} FROM offerings WHERE id = ?",
            [offering_id]).fetchone()
        if row is None:
            return None
        return Offering.model_validate(_tag_utc(dict(zip(_OFFERING_COLS, row, strict=True))))

    def get_returns(self, offering_id: str, months: int) -> list[ReturnRecord]:
        """Return up to `months` most recent monthly records, oldest first."""
        rows = self._conn.cursor().execute(
            f"SELECT {', '.join(_RETURN_COLS)} FROM historical_returns "
            "WHERE offering_id = ? ORDER BY month DESC LIMIT ?",
            [offering_id, int(months)]).fetchall()
        return [ReturnRecord.model_validate(dict(zip(_RETURN_COLS, r, strict=True)))
                for r in reversed(rows)]

    def get_market_metrics(self, metro: str, months: int) -> list[MetricRow]:
        """Return all enrichment rows for `metro` in its `months` most recent months."""
        rows = self._conn.cursor().execute(
            f"SELECT {', '.join(_METRIC_COLS)} FROM market_metrics "
            "WHERE metro = ? ORDER BY month, source, metric", [metro]).fetchall()
        recent = set(sorted({str(r[1]) for r in rows})[-int(months):])
        return [MetricRow.model_validate(_tag_utc(dict(zip(_METRIC_COLS, r, strict=True))))
                for r in rows if str(r[1]) in recent]

    def get_metro_for_market(self, raw_market: str) -> str | None:
        """Resolve a raw offering market to its canonical metro slug via aliases (R11)."""
        row = self._conn.cursor().execute(
            "SELECT metro FROM market_aliases WHERE raw_market = ?", [raw_market]).fetchone()
        return None if row is None else str(row[0])

    def stats(self) -> dict[str, Any]:
        """Row counts and data freshness per table, for `/api/meta` staleness."""
        cur = self._conn.cursor()
        out: dict[str, Any] = {}
        for table, freshness in (("offerings", "max(as_of)"),
                                 ("historical_returns", "max(month)"),
                                 ("market_metrics", "max(as_of)")):
            row = cur.execute(f"SELECT count(*), {freshness} FROM {table}").fetchone()
            assert row is not None  # aggregates always return one row
            key = "latest_month" if table == "historical_returns" else "latest_as_of"
            latest = row[1]
            if isinstance(latest, datetime):  # R10 read path: stored UTC comes back naive
                latest = latest.replace(tzinfo=UTC)
            out[table] = {"rows": int(row[0]), key: latest}
        return out

    # -- OfferingWriter ----------------------------------------------------

    def upsert_offerings(self, rows: Sequence[Offering]) -> int:
        """Upsert offerings by id; returns the number of rows written."""
        return self._write(_upsert_sql("offerings", _OFFERING_COLS, ("id",)),
                           [tuple(r.model_dump()[c] for c in _OFFERING_COLS) for r in rows])

    def upsert_returns(self, rows: Sequence[ReturnRecord]) -> int:
        """Upsert monthly returns keyed by (offering_id, month)."""
        return self._write(
            _upsert_sql("historical_returns", _RETURN_COLS, ("offering_id", "month")),
            [tuple(r.model_dump()[c] for c in _RETURN_COLS) for r in rows])

    def upsert_market_metrics(self, rows: Sequence[MetricRow]) -> int:
        """Upsert enrichment rows keyed by (metro, month, source, metric)."""
        return self._write(
            _upsert_sql("market_metrics", _METRIC_COLS, ("metro", "month", "source", "metric")),
            [tuple(r.model_dump()[c] for c in _METRIC_COLS) for r in rows])

    def upsert_market_aliases(self, rows: Sequence[tuple[str, str]]) -> int:
        """Upsert (raw_market, metro) alias rows for entity resolution (R11)."""
        return self._write(
            _upsert_sql("market_aliases", ("raw_market", "metro"), ("raw_market",)),
            [tuple(r) for r in rows])

    def replace_live_catalogue(
        self, offerings: Sequence[Offering], returns: Sequence[ReturnRecord],
        aliases: Sequence[tuple[str, str]], seed_ids: Sequence[str],
    ) -> dict[str, int]:
        """Atomically replace the buyable Arrived snapshot and purge demo rows."""
        from infrastructure.duckdb.catalogue_snapshot import replace_live_catalogue

        return replace_live_catalogue(self._conn, offerings, returns, aliases, seed_ids)

    def purge_seed_data(self, seed_ids: Sequence[str]) -> int:
        """Delete seed demo rows; returns the number of offerings deleted.

        The spec's sanctioned R8 exception besides insert/delete-only plans:
        seed data is an offline test fixture (amended R21), so boot and the
        live catalogue refresh DELETE the seed offerings, their return
        history, and every `source='seed'` metric row. `market_aliases` stays:
        its raw-market -> metro mappings are factual and shared with real
        listings (e.g. Fayetteville, AR).
        """
        cur = self._conn.cursor()
        deleted = 0
        if seed_ids:
            placeholders = ", ".join("?" for _ in seed_ids)
            cur.execute(
                f"DELETE FROM historical_returns WHERE offering_id IN ({placeholders})",
                list(seed_ids))
            row = cur.execute(
                f"DELETE FROM offerings WHERE id IN ({placeholders})",
                list(seed_ids)).fetchone()
            deleted = 0 if row is None else int(row[0])
        cur.execute("DELETE FROM market_metrics WHERE source = 'seed'")
        return deleted

    def _write(self, sql: str, params: list[tuple[Any, ...]]) -> int:
        """Run one upsert statement over all rows; empty input writes nothing."""
        if not params:
            return 0
        self._conn.cursor().executemany(sql, params)
        return len(params)
