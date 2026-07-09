"""PlansRepo: DuckDB adapter satisfying PlanStore for immutable saved snapshots.

R16: snapshots are insert/delete only — no update path exists, so a later
enrichment refresh can never change a saved plan. Inputs/output are stored as
JSON text (VARCHAR) to avoid depending on the DuckDB JSON extension.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from domain.models import PlanRecord
from infrastructure.duckdb.connection import DuckDBConn

_PLAN_COLS: tuple[str, ...] = ("id", "name", "created_at", "inputs", "output", "data_as_of")


def _as_utc(value: datetime) -> datetime:
    """Re-tag a TIMESTAMP read back from DuckDB as UTC (R10 read path).

    Columns store UTC wall clock but come back naive; without the re-tag their
    ISO form lacks an offset and JS `Date` would parse it as local time.
    """
    return value.replace(tzinfo=UTC)


class PlansRepo:
    """Insert/delete-only store for immutable saved-plan snapshots (R16)."""

    def __init__(self, conn: DuckDBConn) -> None:
        """Share the process's single connection; each call takes a cursor (R7)."""
        self._conn = conn

    def save(self, record: PlanRecord) -> str:
        """Persist a snapshot (plain INSERT — never upsert, R16) and return its id."""
        self._conn.cursor().execute(
            f"INSERT INTO plans ({', '.join(_PLAN_COLS)}) VALUES (?, ?, ?, ?, ?, ?)",
            [record.id, record.name, record.created_at,
             json.dumps(record.inputs), json.dumps(record.output), record.data_as_of])
        return record.id

    def list_plans(self) -> list[dict[str, Any]]:
        """Return JSON-serializable snapshot summaries, newest first."""
        rows = self._conn.cursor().execute(
            "SELECT id, name, created_at, inputs, data_as_of FROM plans "
            "ORDER BY created_at DESC, id").fetchall()
        return [
            {
                "id": str(r[0]),
                "name": None if r[1] is None else str(r[1]),
                "created_at": _as_utc(r[2]).isoformat(),
                "inputs": json.loads(r[3]),
                "data_as_of": _as_utc(r[4]).isoformat(),
            }
            for r in rows
        ]

    def get_plan(self, plan_id: str) -> PlanRecord | None:
        """Return one full snapshot by id, or None when unknown."""
        row = self._conn.cursor().execute(
            f"SELECT {', '.join(_PLAN_COLS)} FROM plans WHERE id = ?", [plan_id]).fetchone()
        if row is None:
            return None
        return PlanRecord(
            id=str(row[0]),
            name=None if row[1] is None else str(row[1]),
            created_at=_as_utc(row[2]),
            inputs=json.loads(row[3]),
            output=json.loads(row[4]),
            data_as_of=_as_utc(row[5]),
        )

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a snapshot; True when a row was removed."""
        cur = self._conn.cursor()
        found = cur.execute("SELECT count(*) FROM plans WHERE id = ?", [plan_id]).fetchone()
        assert found is not None  # count(*) always returns one row
        if int(found[0]) == 0:
            return False
        cur.execute("DELETE FROM plans WHERE id = ?", [plan_id])
        return True

    def stats(self) -> dict[str, Any]:
        """Row count for `/api/meta`."""
        row = self._conn.cursor().execute("SELECT count(*) FROM plans").fetchone()
        assert row is not None  # count(*) always returns one row
        return {"rows": int(row[0])}
