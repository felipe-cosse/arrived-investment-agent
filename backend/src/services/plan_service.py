"""PlanService: risk strategy + market momentum -> allocation engine; snapshots (§4).

Depends only on the OfferingReader and PlanStore ports (R2). Unknown risk-profile
names are rejected here as infeasible results, never exceptions (R12), so the
agent can relay them conversationally.
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any

from domain.models import PlanRecord
from domain.planner import AllocationEngine
from domain.ports import OfferingReader, PlanStore
from domain.risk import RISK_STRATEGIES
from services.market_service import MarketService

logger = logging.getLogger(__name__)

DEFAULT_RISK_PROFILE = "balanced"
DEFAULT_HORIZON_YEARS = 5

ExistingPositions = list[dict[str, Any]] | dict[str, float] | None


def _normalize_existing(existing: ExistingPositions) -> dict[str, float] | None:
    """Accept the tool-schema list form or a plain dict; None passes through."""
    if existing is None:
        return None
    if isinstance(existing, dict):
        return {str(k): float(v) for k, v in existing.items()}
    return {str(row["offering_id"]): float(row["amount_usd"]) for row in existing}


def _coerce_request(amount: Any, horizon_years: Any, existing: ExistingPositions,
                    ) -> tuple[float, int, dict[str, float] | None] | str:
    """Coerce untyped model-supplied tool args; return a rejection reason on failure.

    R12 assigns input checks to PlanService: malformed values become a
    human-readable string the caller wraps as `{"feasible": false, ...}`,
    never an exception.
    """
    try:
        amount_f = float(amount)
    except (TypeError, ValueError):
        return f"amount must be a number, got {amount!r}"
    if not math.isfinite(amount_f):
        return f"amount must be a finite number, got {amount!r}"
    try:
        horizon = int(horizon_years)
    except (TypeError, ValueError):
        return f"horizon_years must be a whole number, got {horizon_years!r}"
    try:
        positions = _normalize_existing(existing)
    except (TypeError, ValueError, KeyError):
        return ("existing_positions must be a list of {offering_id, amount_usd} "
                "rows with numeric amounts")
    return amount_f, horizon, positions


class PlanService:
    """Runs the deterministic engine with momentum tilts and manages saved snapshots."""

    def __init__(self, reader: OfferingReader, store: PlanStore) -> None:
        """Wire the ports; MarketService supplies the §7 momentum tilt per market."""
        self._reader = reader
        self._store = store
        self._market = MarketService(reader)
        self._engine = AllocationEngine()

    def build_plan(self, amount: float, risk_profile: str = DEFAULT_RISK_PROFILE,
                   horizon_years: int = DEFAULT_HORIZON_YEARS,
                   existing_positions: ExistingPositions = None) -> dict[str, Any]:
        """Run the engine over current offerings; momentum is applied automatically.

        Tool args arrive from the model untyped, so values are coerced first and
        malformed input becomes an infeasible result, never an exception (R12).
        """
        coerced = _coerce_request(amount, horizon_years, existing_positions)
        if isinstance(coerced, str):
            return {"feasible": False, "reason": coerced}
        amount_f, horizon, existing = coerced
        strategy = RISK_STRATEGIES.get(str(risk_profile))
        if strategy is None:
            known = ", ".join(sorted(RISK_STRATEGIES))
            return {"feasible": False,
                    "reason": f"unknown risk profile '{risk_profile}'; expected one of: {known}"}
        offerings = [o.model_dump() for o in self._reader.list_offerings()]
        tilts = self._market.momentum_by_market({str(o["market"]) for o in offerings})
        return self._engine.build(amount_f, strategy, horizon, offerings=offerings,
                                  momentum_by_market=tilts, existing_positions=existing)

    def save_plan(self, amount: float, risk_profile: str = DEFAULT_RISK_PROFILE,
                  horizon_years: int = DEFAULT_HORIZON_YEARS,
                  existing_positions: ExistingPositions = None,
                  name: str | None = None) -> dict[str, Any]:
        """Re-run the engine and persist an immutable snapshot of the result (R16)."""
        coerced = _coerce_request(amount, horizon_years, existing_positions)
        if isinstance(coerced, str):
            return {"feasible": False, "reason": coerced}
        amount_f, horizon, existing = coerced
        output = self.build_plan(amount_f, risk_profile, horizon, existing)
        if not output.get("feasible"):
            return output  # nothing worth snapshotting; the agent relays the reason (R12)
        record = PlanRecord(
            id=uuid.uuid4().hex,
            name=name,
            created_at=datetime.now(UTC),
            inputs={"amount": amount_f, "risk_profile": risk_profile,
                    "horizon_years": horizon,
                    "existing_positions": existing or {}},
            output=output,
            data_as_of=self._data_as_of(),
        )
        self._store.save(record)
        logger.info("plan_saved id=%s name=%s", record.id, record.name)
        return {"id": record.id, "name": record.name,
                "created_at": record.created_at.isoformat(),
                "data_as_of": record.data_as_of.isoformat(),
                "inputs": record.inputs, "output": record.output}

    def list_plans(self) -> list[dict[str, Any]]:
        """Saved-snapshot summaries, newest first."""
        return self._store.list_plans()

    def _data_as_of(self) -> datetime:
        """Snapshot freshness: max(as_of) across offerings and market_metrics (§9).

        Values are re-tagged as UTC if a reader ever yields them naive, so the
        serialized timestamp always carries an offset (R10 read path).
        """
        stats = self._reader.stats()
        candidates = [ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)
                      for ts in (stats.get("offerings", {}).get("latest_as_of"),
                                 stats.get("market_metrics", {}).get("latest_as_of"))
                      if isinstance(ts, datetime)]
        if not candidates:
            return datetime.now(UTC)
        return max(candidates)
