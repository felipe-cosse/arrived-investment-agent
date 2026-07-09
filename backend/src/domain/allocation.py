"""Money-grid constants and capped fill state for the allocation engine (spec §6).

Split from `domain/planner.py` per R5 (200-line cap): this module owns grant-time
enforcement of the per-offering cap, market saturation, and type-share caps.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

INCREMENT_USD = 10
MIN_POSITION_USD = 100
MAX_POSITIONS_PER_MARKET = 2
TYPE_SHARE_CAPS: dict[str, float] = {"vacation_rental": 0.50}
FUND_TYPE = "fund"

_Row = Mapping[str, Any]


def floor_to_increment(value: float) -> int:
    """Floor dollars onto the $10 grid, tolerating binary float noise."""
    return int(round(value, 6) // INCREMENT_USD) * INCREMENT_USD


class Allocator:
    """Mutable fill state enforcing per-offering, market, and type caps on grants."""

    def __init__(self, usable: int, base: float, cap: int,
                 existing: Mapping[str, float], catalog: Mapping[str, _Row]) -> None:
        """Seed running totals from what is already held so caps see the whole portfolio."""
        self.remaining = usable
        self.base = base
        self.cap = cap
        self.existing = existing
        self.alloc: dict[str, int] = {}
        self.type_used: dict[str, float] = {}
        self.market_ids: dict[str, set[str]] = {}
        for oid, amount in existing.items():
            row = catalog[oid]
            ptype = str(row["property_type"])
            self.type_used[ptype] = self.type_used.get(ptype, 0.0) + amount
            if ptype != FUND_TYPE:
                self.market_ids.setdefault(str(row["market"]), set()).add(oid)

    def _market_blocked(self, row: _Row) -> bool:
        """New distinct non-fund names are blocked in saturated markets (§6 step 5)."""
        if row["property_type"] == FUND_TYPE:
            return False
        ids = self.market_ids.get(str(row["market"]), set())
        return str(row["id"]) not in ids and len(ids) >= MAX_POSITIONS_PER_MARKET

    def grant(self, row: _Row, want: float) -> int:
        """Grant up to `want` new dollars, capped by room/type share/budget; return it."""
        oid, ptype = str(row["id"]), str(row["property_type"])
        if self._market_blocked(row):
            return 0
        room = self.cap - self.existing.get(oid, 0.0) - self.alloc.get(oid, 0)
        share_room = (TYPE_SHARE_CAPS.get(ptype, 1.0) * self.base
                      - self.type_used.get(ptype, 0.0))
        take = floor_to_increment(min(want, room, share_room, self.remaining))
        if take <= 0:
            return 0
        if take < MIN_POSITION_USD and oid not in self.existing and oid not in self.alloc:
            return 0  # top-ups below MIN stay allowed for held/allocated names
        self.alloc[oid] = self.alloc.get(oid, 0) + take
        self.type_used[ptype] = self.type_used.get(ptype, 0.0) + take
        self.remaining -= take
        if ptype != FUND_TYPE:
            self.market_ids.setdefault(str(row["market"]), set()).add(oid)
        return take
