---
name: spec-audit
description: Audit source changes against the hard rules (R1–R31) of arrived-agent-spec.md. Use before completing any task that touched backend/ or frontend/ source, after a builder agent finishes a phase, or on demand. Mechanical script first, then judgment checklist.
---

# Spec Audit

Two layers: a mechanical script for greppable rules, and a judgment checklist for rules that need reading the code. Every finding cites a rule ID (R#) or section (§) from `arrived-agent-spec.md` — no rule reference, no finding.

Scope: audit the files/dirs you were given; if none, audit what `git status` and `git diff --name-only` show as changed. Families like DuckDB semantics need whole-module context — read the full module, not just the diff.

## Layer 1 — mechanical checks

Run from the repo root and include the full output in your report:

```bash
bash .claude/skills/spec-audit/scripts/mechanical-checks.sh
```

Covers R5 (200-line cap), R1 (domain purity), R2 (service imports), R9 (`SELECT *`), R27 (`print` in src), R29 (TS `any`), R19 (`EventSource`), R10 (naive datetimes), R23 (secret literals). `NOTE` lines mark not-yet-built paths — normal while the repo is greenfield. Exit 0 clean, 1 findings.

## Layer 2 — judgment checklist

Apply the families relevant to the audited scope. For each entry: read the named code, decide, record a finding or move on.

### Layering & DI (R2–R4, §3)
- R2/R3: adapters (`OfferingsRepo`, `PlansRepo`, `AsyncAnthropic`, enrichment fetchers) are constructed **only** in `backend/src/app/dependencies.py` (and tests). Services type-hint against the Protocols in `domain/ports.py`.
- R4: each router body is parse → service call → response shaping. Loops, allocation math, SQL, or business branching in a router = violation.
- §3: only the sanctioned patterns (Repository, Strategy, Adapter, DI, App Factory). Speculative abstractions = concern.

### DuckDB semantics (R6–R8, R11, §5)
- R6: seeding and enrichment refresh run inside the API process; no second writer container in `docker-compose.yml`.
- R7: exactly one `DuckDBConn(...)` constructed in app code (the composition root); repos share it; every query goes through `connection.cursor()`.
- R8: all writes are `INSERT ... ON CONFLICT DO UPDATE`, except `plans` which is insert/delete only (R16).
- R11: every offering→metrics join goes through `market_aliases`; each enrichment adapter owns its region map; no inline raw-market string matching.
- §5: table DDL matches the spec exactly (columns, CHECKs, primary keys).

### Engine & market invariants (R12–R14, §6, §7)
- R12: invalid input → `{"feasible": false, "reason": ...}`; the engine never raises on user input; unknown risk-profile names are checked in `PlanService`.
- R13: every position carries `score_breakdown` with keys `{yield, appreciation, momentum, leverage, total}` rounded to 6 dp.
- R14: momentum contributes at most `market_weight · (momentum − 0.5)`; offerings are never excluded for missing market data.
- §6 money rules: `INCREMENT_USD = 10`, `MIN_POSITION_USD = 100`, integer-USD positions, `MAX_POSITIONS_PER_MARKET = 2` (funds exempt), `TYPE_SHARE_CAPS = {"vacation_rental": 0.50}`, ties broken by offering id, invariant `total_invested + unallocated == requested` (±$0.01, new money only).
- §7: `yoy`/`norm`/`momentum` are pure; live sources preferred over `seed` for the same metric; neutral 0.5 when data is missing.

### API & SSE contract (R16–R19, §9)
- R16: no plan update endpoint; `data_as_of = max(as_of)` across offerings + market_metrics at save time; a later refresh never mutates stored snapshots.
- R17: the server truncates history to `MAX_HISTORY_MESSAGES` before the first model call.
- R18: the system prompt tells the model to summarize, not restate rows the UI renders.
- R19: SSE consumed via `fetch` + `ReadableStream` through `createSseDecoder`; the Appendix A decoder test is present verbatim.
- §9: event names/payloads match the spec table; 503 without `ANTHROPIC_API_KEY`; `MAX_AGENT_TURNS` cap emits `done {stop_reason: "max_turns"}`; tool failures emit `tool_error` and a `tool_result` with `is_error`.

### Enrichment & offline (R20–R21, §10)
- R20: each source is isolated — one provider failing yields `{status: "error"}` for it alone, never aborts the others.
- R21: the seed path has no network dependency; the app is fully functional with no keys.
- §10: seed windows are relative to today (no hard-coded month ranges); RNG seed 42.

### Infra & CI (R22–R24, §11)
- R22: CI runs offline — no secrets, no network beyond package installs.
- R23 (beyond the grep): no secrets in Dockerfiles, compose, or images.
- R24: base images pinned by major tag; `uv.lock` and the frontend lockfile committed.

### Code standards (R25–R26, R28, R30–R31, §14)
- R25: tests never touch the network; tmp-path DBs; mocked transports for enrichment.
- R26: type hints on public functions; `from __future__ import annotations` in each backend module.
- R28: no swallowed exceptions (bare `except`, `except: pass`, silent fallbacks).
- R30: `aria-live="polite"` on the streaming message region; panes stack below the `md` breakpoint.
- R31: docstrings on every module and public class/function.

### Scope (§16, §17)
- Nothing from §16 (fees, DCA, `ingest_runs`, auto-refresh scheduler, property-based tests, Parquet export, admin auth) or §17 exists in the tree.

## Report format

1. Mechanical script output, verbatim.
2. Judgment findings, one line each: `R# · file:line · what is violated · suggested fix · severity`.
   - `violation` = breaks a MUST/NEVER. `concern` = SHOULD/PREFER or a smell worth flagging.
3. Coverage statement, always: `Audited families: <list> — N violations, M concerns.` A clean audit states "no violations" explicitly — never end in silence.
