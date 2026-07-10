"""Tests for seed-retirement support: SEED_OFFERING_IDS and close_offerings.

The live refresh runner (live-data design doc) retires the 11 seed offerings by
flipping their status to 'closed' after the first successful scrape — the
spec's sanctioned R8 exception besides insert/delete-only plans.
"""

from __future__ import annotations

from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.seed import SEED_OFFERING_IDS


def test_seed_offering_ids_match_seeded_rows(repo: OfferingsRepo) -> None:
    """The exported tuple names exactly the 11 rows the seeder writes, in §10 order."""
    assert len(SEED_OFFERING_IDS) == 11
    assert set(SEED_OFFERING_IDS) == {o.id for o in repo.list_offerings()}
    assert SEED_OFFERING_IDS[0] == "sfr-meridian"
    assert SEED_OFFERING_IDS[-1] == "fund-credit"


def test_close_offerings_flips_status_to_closed(repo: OfferingsRepo) -> None:
    """Every named id ends up 'closed' and the count of matched rows comes back."""
    assert repo.close_offerings(SEED_OFFERING_IDS) == 11
    assert {o.status for o in repo.list_offerings()} == {"closed"}


def test_close_offerings_is_idempotent(repo: OfferingsRepo) -> None:
    """A second retirement pass matches the same rows and leaves them closed."""
    repo.close_offerings(SEED_OFFERING_IDS)
    assert repo.close_offerings(SEED_OFFERING_IDS) == 11
    assert all(o.status == "closed" for o in repo.list_offerings())


def test_close_offerings_only_touches_named_ids(repo: OfferingsRepo) -> None:
    """Untargeted rows keep their status; unknown ids and empty input match nothing."""
    assert repo.close_offerings([]) == 0
    assert repo.close_offerings(["no-such-id"]) == 0
    assert repo.close_offerings(["sfr-meridian"]) == 1
    statuses = {o.id: o.status for o in repo.list_offerings()}
    assert statuses.pop("sfr-meridian") == "closed"
    assert set(statuses.values()) == {"available"}
