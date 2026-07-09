---
name: verify-gate
description: Run the project's verification gates before claiming any work complete, fixed, or passing. Exact commands for backend lint/type/tests, frontend type/tests/build, the mechanical spec audit, and the offline docker smoke test. Evidence required; a gate that cannot run is a failure.
---

# Verify Gate

Run every applicable gate — never stop at the first failure; report all of them. For each gate paste real command output (the relevant tail is enough). Never assert a verdict for a command you did not run in this session.

**Not-present rule:** a layer whose directory does not exist yet is `not_present` (build phase pending) — not a failure. A layer that exists but whose gate errors out (missing deps, tool crashes) is a **fail**, never a skip.

Gate names below are a contract: `.claude/workflows/build-phase.js` routes `frontend-*` failures to the frontend builder. Do not rename gates.

## Gates (in order)

### 1. backend-lint
```bash
cd backend && uv run ruff check .
```
Pass: `All checks passed!`, exit 0.

### 2. backend-types
```bash
cd backend && uv run mypy .
```
Pass: `Success: no issues found`, exit 0.

### 3. backend-tests
```bash
cd backend && uv run pytest
```
Pass: exit 0, zero failures/errors. Targeted rerun while iterating:
`uv run pytest tests/domain/test_planner.py::test_determinism -v`

### 4. frontend-types
```bash
cd frontend && npx tsc --noEmit
```
Pass: no output, exit 0.

### 5. frontend-tests
```bash
cd frontend && npx vitest run
```
Pass: all test files green, exit 0.

### 6. frontend-build
```bash
cd frontend && npm run build
```
Pass: vite build completes, exit 0.

### 7. mechanical-audit
```bash
bash .claude/skills/spec-audit/scripts/mechanical-checks.sh
```
Pass: final line `PASS: no mechanical findings` (NOTE lines are fine).

### 8. docker-smoke — only when docker-compose.yml exists, or on explicit request
Proves R21: the stack works offline with no keys. `$SCRATCH` is the session scratchpad.
```bash
docker compose up --build -d
curl -sf http://localhost:8000/api/health
curl -s http://localhost:8000/api/offerings | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'
curl -s -X POST http://localhost:8000/api/plan -H 'Content-Type: application/json' \
  -d '{"amount": 2000, "risk_profile": "balanced", "horizon_years": 5}' -o "$SCRATCH/plan_a.json"
curl -s -X POST http://localhost:8000/api/plan -H 'Content-Type: application/json' \
  -d '{"amount": 2000, "risk_profile": "balanced", "horizon_years": 5}' -o "$SCRATCH/plan_b.json"
diff "$SCRATCH/plan_a.json" "$SCRATCH/plan_b.json" && echo deterministic
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"hi"}]}'
docker compose down
```
Pass: health returns 200; offerings count is 11; the two plans are byte-identical (`deterministic`); chat returns `503` when `ANTHROPIC_API_KEY` is absent from `backend/.env` (if a key is configured, note that and skip the 503 assertion). Always run `docker compose down` afterward, even on failure.

## Report format

Per gate, one line: `<name> · pass|fail|not_present · <one-line evidence>`, followed by the pasted output per gate. Final line, always:

```
VERIFY: PASS
```
or
```
VERIFY: FAIL — <comma-separated failed gate names>
```
