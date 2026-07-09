# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Greenfield. `arrived-agent-spec.md` is the **single source of truth** for what to build: a web app exploring fractional real-estate offerings (modeled on Arrived) with a Claude tool-use chat agent, a deterministic Python allocation engine, and a React data-explorer/plan UI. `DESIGN.md` is the **binding visual identity** for all UI work: design tokens (colors, Inter typography, spacing/rounding scales), component token values (card, button-primary), and layout rules. Read the spec before doing anything; this file is only an orientation layer and never overrides it.

Key spec sections: §3 architecture rules · §4 file map (fixed responsibilities) · §6 allocation engine · §9 SSE contract · §15 build order + acceptance criteria · §16/§17 **deferred/out-of-scope — do not build those items**.

## Build order

Copy the Appendix A test files from the spec **verbatim first** (`backend/tests/conftest.py`, `backend/tests/domain/test_planner.py`, `backend/tests/services/test_agent_service.py`, `frontend/src/api/sse.test.ts`), then build until they pass, in spec §15 order: domain → DuckDB repos/seeder → services/tools → agent loop + API → enrichment → frontend types/SSE → UI → Docker/CI.

## Commands

Stack: Python 3.12 + FastAPI + DuckDB (backend, `uv` with committed lockfile), React 18 + TypeScript strict + Vite (frontend).

Backend (from `backend/`):
- `uv run pytest` — all tests; single test: `uv run pytest tests/domain/test_planner.py::test_determinism`
- `uv run ruff check .` and `uv run mypy .` — must be clean (configured in `pyproject.toml`)
- Dev server: uvicorn on 8000

Frontend (from `frontend/`):
- `npm run test` (vitest) · `npx tsc --noEmit` · `npm run build`
- Dev: vite on 5173 with `VITE_API_URL=http://localhost:8000/api`

Full stack: `docker compose up --build` → web on :5173, api on :8000. Everything (tests, CI, the app itself) must work **offline with no API keys** — only `/api/chat` needs `ANTHROPIC_API_KEY`.

## Architecture (big picture)

Layered ports-and-adapters; dependencies point inward only:

```
api (FastAPI routers, SSE) → services (agent loop, tools, plan/market orchestration)
                           → domain (models, risk strategies, engine, market math) ← pure
infrastructure (DuckDB repos, Anthropic adapter, enrichment fetchers, seeder) implements domain/ports.py
```

- `domain/` is **pure**: no I/O, no SDK/framework imports, no env reads. Services depend only on the `Protocol` ports in `domain/ports.py`; concrete adapters are wired solely in `app/dependencies.py` (single composition root). Routers hold zero business logic.
- **AllocationEngine** (`domain/planner.py`) does all allocation math deterministically (same inputs → same plan; ties broken by offering id). The agent never does math or invents data — it calls tools. Invalid input returns `{"feasible": false, "reason": ...}`, never raises. Every position carries a `score_breakdown`.
- **DuckDB**: one process, one `read_write` connection (`DuckDBConn`, shared by both repos via `cursor()`); all writes are keyed upserts except `plans` (insert/delete only — saved plans are immutable snapshots). Offering→enrichment joins go through the `market_aliases` table, never inline string matching.
- **Chat SSE**: `POST /api/chat` streams typed events (`text_delta`, `tool_started`, `*_result`, `tool_error`, `done`, `error`). The frontend renders `*_result` events as components and must consume the stream with `fetch` + `ReadableStream` through `createSseDecoder` — `EventSource` cannot be used (POST). Server truncates history to `MAX_HISTORY_MESSAGES` (40) and caps the tool loop at 8 turns.
- **Enrichment** (Zillow/FRED/Census adapters implementing `MarketDataSource`): optional at runtime, failures isolated per source, refresh runs inside the API process only (DuckDB single-writer rule). Momentum is a bounded tilt in scoring, never a gate.

## Hard rules that shape every file

- Every source file (backend, frontend, tests) **≤ 200 lines** — split by responsibility when a file wants to grow.
- Tests never touch the network; fixtures use a tmp DuckDB file.
- Python: type hints on public functions, `from __future__ import annotations`, stdlib `logging` (no `print` in `src/`), no swallowed exceptions.
- TypeScript: strict, no `any` in `src/`; SSE events are a discriminated union, exhaustively switched.
- Money: integer-USD positions, $10 increments, $100 minimum; engine invariant `total_invested + unallocated == requested`.
- Every plan output and agent plan reply carries the "hypothetical projection, not investment advice" disclaimer.
- Secrets only via env; `.env.example` committed and complete.
- Frontend UI follows `DESIGN.md`: its color/typography/spacing/rounding tokens and component rules — no invented colors or fonts; `success` (#10B981) marks positive yields; charts use `accent` + `success`.

## Project tooling (.claude/)

- **Build a spec phase:** run the `build-phase` workflow with `{phase: 1..9}` (spec §15 steps) — the right builder agent implements, spec-compliance reviewers audit rule families in parallel, the verifier runs the gates, and a fix loop runs until green (max 3 rounds). `{phase: "fix", scope: "..."}` runs an audit+fix round without building.
- **Agents:** `backend-builder` / `frontend-builder` implement phases and fixes; `spec-compliance-reviewer` audits against R1–R31 (read-only); `verifier` runs the gates and reports evidence.
- **Skills:** invoke `spec-audit` before completing any change that touched source (mechanical script + judgment checklist); invoke `verify-gate` before claiming anything complete — a gate that cannot run is a failure, not a skip.
