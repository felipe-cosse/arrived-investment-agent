"""PlanService: risk strategy + market momentum -> allocation engine; snapshots (§4).

Depends only on the OfferingReader and PlanStore ports (R2). Unknown risk-profile
names are rejected here as infeasible results, never exceptions (R12), so the
agent can relay them conversationally.
"""

from __future__ import annotations

import logging
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
        """Run the engine over current offerings; momentum is applied automatically."""
        strategy = RISK_STRATEGIES.get(risk_profile)
        if strategy is None:
            known = ", ".join(sorted(RISK_STRATEGIES))
            return {"feasible": False,
                    "reason": f"unknown risk profile '{risk_profile}'; expected one of: {known}"}
        offerings = [o.model_dump() for o in self._reader.list_offerings()]
        tilts = self._market.momentum_by_market({str(o["market"]) for o in offerings})
        return self._engine.build(amount, strategy, horizon_years, offerings=offerings,
                                  momentum_by_market=tilts,
                                  existing_positions=_normalize_existing(existing_positions))

    def save_plan(self, amount: float, risk_profile: str = DEFAULT_RISK_PROFILE,
                  horizon_years: int = DEFAULT_HORIZON_YEARS,
                  existing_positions: ExistingPositions = None,
                  name: str | None = None) -> dict[str, Any]:
        """Re-run the engine and persist an immutable snapshot of the result (R16)."""
        output = self.build_plan(amount, risk_profile, horizon_years, existing_positions)
        if not output.get("feasible"):
            return output  # nothing worth snapshotting; the agent relays the reason (R12)
        record = PlanRecord(
            id=uuid.uuid4().hex,
            name=name,
            created_at=datetime.now(UTC),
            inputs={"amount": amount, "risk_profile": risk_profile,
                    "horizon_years": horizon_years,
                    "existing_positions": _normalize_existing(existing_positions) or {}},
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
        """Snapshot freshness: max(as_of) across offerings and market_metrics (§9)."""
        stats = self._reader.stats()
        candidates = [ts for ts in (stats.get("offerings", {}).get("latest_as_of"),
                                    stats.get("market_metrics", {}).get("latest_as_of"))
                      if isinstance(ts, datetime)]
        if not candidates:
            return datetime.now(UTC)
        return max(candidates)
