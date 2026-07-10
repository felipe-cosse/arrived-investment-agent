# Real-only runtime (seed data = offline test fixture)

- [x] Tests first: retarget `test_seed_retirement.py` -> `test_seed_purge.py` (purge semantics)
- [x] Tests: `test_arrived_refresh.py` -> `seeds_purged`, rows deleted, idempotent second run = 0
- [x] Tests: `test_admin_offerings.py` report shape `seeds_purged`
- [x] Tests: `test_api.py` fixture opts into `seed_demo_data=True`; new empty-boot test (count 0)
- [x] `config.py`: `seed_demo_data: bool = False` (env SEED_DEMO_DATA)
- [x] `offerings_repo.py`: `purge_seed_data(seed_ids)` replaces `close_offerings`
- [x] `arrived/refresh.py`: purge instead of close; report key `seeds_purged`
- [x] `main.py` lifespan: seed only when flag true; purge otherwise; log both paths
- [x] `agent_service.py`: freshness line in SYSTEM_PROMPT
- [x] `.env.example`: document SEED_DEMO_DATA (test/dev-only)
- [x] SPEC.md: R21, §8, §9, §10, §15 (+ consistency: §1, R8, §4 map, §10 arrived bullet, §13 table)
- [x] verify-gate SKILL.md gate 8: `0 0` fresh boot, optional live refresh, plan-check note
- [x] Gates: ruff / mypy / pytest green (136 passed); mechanical audit PASS

## Review

Runtime is now real-only: default boot purges seed rows (offerings + their
returns + source='seed' metrics; aliases kept) and the app starts empty until
the Arrived catalogue refresh. `SEED_DEMO_DATA=true` is the documented
test/dev escape hatch; Appendix A canonical files untouched (conftest seeds at
the repo layer). Refresh report key renamed `seeds_retired` -> `seeds_purged`
(frontend consumers to be fixed in a separate task). Consequential extra SPEC
consistency edits beyond the enumerated five: §1 overview bullet, R8 exception
wording, §4 main.py map comment, §10 arrived bullet, §13 SEED_DEMO_DATA row;
plus docker-compose.yml R21 comments.
