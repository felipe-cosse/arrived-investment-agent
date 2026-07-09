# Claude Tooling (Skills, Agents, Workflow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the project-local Claude Code tooling — 2 skills, 4 agents, 1 workflow — that builds the Arrived Investment Agent from `arrived-agent-spec.md` and enforces its rules on every change.

**Architecture:** Everything lives under `.claude/` in the repo and references the spec by rule ID (R1–R31) and section (§) instead of duplicating it. A bash script mechanizes the greppable rules; skills encode procedures; agents encode roles with those procedures baked in; the workflow orchestrates builder → audit → verify → fix loops.

**Tech Stack:** Bash (macOS bash 3.2-compatible), Markdown skill/agent files with YAML frontmatter, Claude Code Workflow script (plain JavaScript, `export const meta` + `agent()/parallel()/phase()/log()` hooks).

## Global Constraints

- Spec source of truth: `arrived-agent-spec.md` at repo root. Design doc: `docs/superpowers/specs/2026-07-09-skills-agents-design.md`.
- Repo root: `/Users/felipecosse/Docker/ArrivedInvestmentAgent` (git repo on `main`; run all commands from repo root unless a step says otherwise).
- Every finding/rule reference in any artifact must cite a rule ID (`R#`) or section (`§`) that exists in the spec. Never invent rule IDs.
- Agent files: YAML frontmatter with `name`, `description` (states when to use), optional `tools` (comma-separated). **No `model` field** — agents inherit the session model.
- Bash must run on macOS bash 3.2: no `declare -A`, no `mapfile`, no `${var,,}`. Process substitution `< <(...)` and herestrings `<<<` are fine.
- The mechanical script must be **greenfield-safe**: a path that doesn't exist yet prints a `NOTE` line and is skipped — never an error.
- Workflow scripts cannot use `Date.now()`, `Math.random()`, or argless `new Date()`.
- Commit after every task with the message given in the task. All commits end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- `$SCRATCH` below means the session scratchpad directory (listed in the executor's system prompt). Never write fixtures into the repo.

---

### Task 1: Mechanical checks script

**Files:**
- Create: `.claude/skills/spec-audit/scripts/mechanical-checks.sh`
- Test: fixture trees under `$SCRATCH/audit-fixture` (dirty) and `$SCRATCH/audit-clean` (clean) — not committed

**Interfaces:**
- Produces: `bash .claude/skills/spec-audit/scripts/mechanical-checks.sh [repo-root]`
  - stdout: one finding per line `RULE  file:line  message`; `NOTE  <path> not present; skipped <RULE>` for missing paths; final line `PASS: no mechanical findings` or `FAIL: <n> mechanical finding(s)`
  - exit codes: `0` clean, `1` findings, `2` bad invocation
  - default repo-root: resolved from the script's own location (four levels up)
- Consumed by: Task 2 (SKILL.md documents it), Task 4 (reviewer runs it), Task 3 (verify-gate gate 7), Task 6 (workflow's verifier/reviewers use it indirectly)

- [ ] **Step 1: Build the dirty fixture (the failing test)**

```bash
FIX="$SCRATCH/audit-fixture"
rm -rf "$FIX"
mkdir -p "$FIX/backend/src/domain" "$FIX/backend/src/services" "$FIX/backend/src/app" "$FIX/frontend/src"

cat > "$FIX/backend/src/domain/models.py" <<'EOF'
import duckdb
import os
KEY = os.getenv("X")
EOF

cat > "$FIX/backend/src/services/plan_service.py" <<'EOF'
from infrastructure.duckdb.connection import DuckDBConn
EOF

cat > "$FIX/backend/src/app/repo.py" <<'EOF'
from datetime import datetime
q = "SELECT * FROM offerings"
print("debug")
ts = datetime.now()
EOF

cat > "$FIX/backend/src/app/config.py" <<'EOF'
API_KEY = "sk-ant-api03-fixture-not-real"
EOF

for i in $(seq 201); do echo "# line $i"; done > "$FIX/backend/src/big_module.py"

cat > "$FIX/frontend/src/bad.ts" <<'EOF'
const x: any = 1;
const es = new EventSource("/api/chat");
EOF
```

Planted violations (10 findings expected): R1×2 (duckdb import, os.getenv), R2×1, R9×1, R27×1, R10×1, R23×1, R5×1, R29×1, R19×1.

- [ ] **Step 2: Run the script to verify it fails (doesn't exist yet)**

Run: `bash .claude/skills/spec-audit/scripts/mechanical-checks.sh "$FIX"`
Expected: `No such file or directory` — confirms we're building something new.

- [ ] **Step 3: Write the script**

Create `.claude/skills/spec-audit/scripts/mechanical-checks.sh` with exactly:

```bash
#!/usr/bin/env bash
# Mechanical checks for the hard rules in arrived-agent-spec.md.
# Usage: bash .claude/skills/spec-audit/scripts/mechanical-checks.sh [repo-root]
# Output: one finding per line: "RULE  file:line  message"; NOTE lines for skipped paths.
# Exit: 0 = clean, 1 = findings, 2 = bad invocation. Greenfield-safe: missing paths are skipped.
set -u

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)}"
cd "$ROOT" || { echo "cannot cd to $ROOT" >&2; exit 2; }
findings=0

scan() { # scan RULE MESSAGE PATTERN PATH [extra grep args...]
  local rule="$1" msg="$2" pattern="$3" path="$4"
  shift 4
  if [ ! -e "$path" ]; then
    echo "NOTE  $path not present; skipped $rule"
    return 0
  fi
  local out line
  out="$(grep -rnE "$@" -e "$pattern" "$path" 2>/dev/null || true)"
  [ -z "$out" ] && return 0
  while IFS= read -r line; do
    printf '%s  %s  %s\n' "$rule" "$(printf '%s' "$line" | cut -d: -f1,2)" "$msg"
    findings=$((findings + 1))
  done <<<"$out"
}

linecap() { # linecap PATH — R5: source files must be <= 200 lines
  local path="$1" f n
  if [ ! -d "$path" ]; then
    echo "NOTE  $path not present; skipped R5"
    return 0
  fi
  while IFS= read -r f; do
    n=$(wc -l <"$f")
    n=$((n + 0))
    if [ "$n" -gt 200 ]; then
      printf 'R5  %s:1  %s lines (max 200)\n' "$f" "$n"
      findings=$((findings + 1))
    fi
  done < <(find "$path" -type f \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) ! -path '*/node_modules/*' ! -path '*/dist/*')
}

# R5 — 200-line cap on every source file
linecap backend/src
linecap backend/tests
linecap frontend/src

# R1 — domain purity: no frameworks/SDKs, no env reads
scan R1 "domain/ must not import frameworks/SDKs" \
  '^[[:space:]]*(import|from)[[:space:]]+(fastapi|duckdb|httpx|anthropic|pydantic_settings)' \
  backend/src/domain --include='*.py'
scan R1 "domain/ must not read the environment" \
  'os\.environ|os\.getenv|getenv\(' \
  backend/src/domain --include='*.py'

# R2 — services depend on domain ports, never adapters/SDKs
scan R2 "services must depend on domain ports, not adapters/SDKs" \
  '^[[:space:]]*(import|from)[[:space:]]+(infrastructure|duckdb|httpx|anthropic)' \
  backend/src/services --include='*.py'

# R9 — explicit column lists
scan R9 "SELECT * is forbidden outside ad-hoc debugging" \
  'SELECT[[:space:]]+\*' \
  backend/src --include='*.py' -i

# R27 — structured logging, never print, in backend src
scan R27 "use stdlib logging, never print, in backend src" \
  '(^|[^[:alnum:]_.])print\(' \
  backend/src --include='*.py'

# R29 — no TypeScript `any` in frontend src
scan R29 "TypeScript any is forbidden in frontend src" \
  ':[[:space:]]*any([^[:alnum:]_]|$)|as[[:space:]]+any|<any>' \
  frontend/src --include='*.ts' --include='*.tsx'

# R19 — SSE is consumed via fetch + ReadableStream, never EventSource
scan R19 "use fetch + ReadableStream via createSseDecoder, never EventSource" \
  'EventSource' \
  frontend/src --include='*.ts' --include='*.tsx'

# R10 — timestamps must be UTC-aware
scan R10 "naive datetime (use datetime.now(UTC))" \
  'datetime\.now\(\)|\.utcnow\(' \
  backend/src --include='*.py'

# R23 — no secret literals in committed trees (.env is local-only, skip it)
for p in backend frontend docker-compose.yml; do
  scan R23 "possible secret literal committed" \
    'sk-ant-|API_KEY[[:space:]]*=[[:space:]]*"[A-Za-z0-9]' \
    "$p" --exclude='.env'
done

if [ "$findings" -gt 0 ]; then
  printf 'FAIL: %d mechanical finding(s)\n' "$findings"
  exit 1
fi
echo "PASS: no mechanical findings"
```

- [ ] **Step 4: Run against the dirty fixture — every planted violation must be caught**

Run: `bash .claude/skills/spec-audit/scripts/mechanical-checks.sh "$FIX"; echo "exit=$?"`
Expected: 10 finding lines — two `R1` (models.py:1 import, models.py:3 env read), one `R2` (plan_service.py:1), one `R9` (repo.py:2), one `R27` (repo.py:3), one `R10` (repo.py:4), one `R23` (config.py:1), one `R5` (big_module.py, 201 lines), one `R29` (bad.ts:1), one `R19` (bad.ts:2) — plus NOTE lines for `backend/tests` and `docker-compose.yml`, then `FAIL: 10 mechanical finding(s)` and `exit=1`. If any planted violation is missed or a count differs, fix the script (not the fixture) until this matches.

- [ ] **Step 5: Run against a clean fixture — must pass**

```bash
CLEAN="$SCRATCH/audit-clean"
rm -rf "$CLEAN"
mkdir -p "$CLEAN/backend/src/domain" "$CLEAN/frontend/src"
printf '"""Domain models."""\nfrom __future__ import annotations\n' > "$CLEAN/backend/src/domain/models.py"
printf 'export const ok = 1;\n' > "$CLEAN/frontend/src/ok.ts"
bash .claude/skills/spec-audit/scripts/mechanical-checks.sh "$CLEAN"; echo "exit=$?"
```

Expected: only NOTE lines (missing `backend/tests`, `backend/src/services`, `docker-compose.yml`), then `PASS: no mechanical findings`, `exit=0`.

- [ ] **Step 6: Run against the real (greenfield) repo — must pass with NOTEs**

Run: `bash .claude/skills/spec-audit/scripts/mechanical-checks.sh; echo "exit=$?"`
Expected: NOTE lines for every backend/frontend path, `PASS: no mechanical findings`, `exit=0`.

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/spec-audit/scripts/mechanical-checks.sh
git commit -m "feat: add spec-audit mechanical checks script

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: spec-audit skill

**Files:**
- Create: `.claude/skills/spec-audit/SKILL.md`

**Interfaces:**
- Consumes: the script from Task 1 at `.claude/skills/spec-audit/scripts/mechanical-checks.sh`.
- Produces: the audit procedure + report format (`R# · file:line · violation · suggested fix · severity`, coverage statement). Task 4's reviewer agent and Task 6's workflow reviewers follow this skill.

- [ ] **Step 1: Write the skill**

Create `.claude/skills/spec-audit/SKILL.md` with exactly:

````markdown
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
````

- [ ] **Step 2: Verify frontmatter and script reference**

Run: `head -4 .claude/skills/spec-audit/SKILL.md && grep -c 'mechanical-checks.sh' .claude/skills/spec-audit/SKILL.md`
Expected: frontmatter opens with `---` and `name: spec-audit`; grep count ≥ 1.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/spec-audit/SKILL.md
git commit -m "feat: add spec-audit skill

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: verify-gate skill

**Files:**
- Create: `.claude/skills/verify-gate/SKILL.md`

**Interfaces:**
- Consumes: the mechanical script (gate 7).
- Produces: gate names `backend-lint`, `backend-types`, `backend-tests`, `frontend-types`, `frontend-tests`, `frontend-build`, `mechanical-audit`, `docker-smoke` and statuses `pass|fail|not_present`. Task 4's verifier agent executes this skill; Task 6's workflow routes `frontend-*` gate failures to the frontend builder — **these names must not change**.

- [ ] **Step 1: Write the skill**

Create `.claude/skills/verify-gate/SKILL.md` with exactly:

````markdown
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
````

- [ ] **Step 2: Verify frontmatter and gate names**

Run: `grep -E '^### [0-9]+\. ' .claude/skills/verify-gate/SKILL.md`
Expected: exactly 8 lines, names in order: backend-lint, backend-types, backend-tests, frontend-types, frontend-tests, frontend-build, mechanical-audit, docker-smoke.

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/verify-gate/SKILL.md
git commit -m "feat: add verify-gate skill

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: spec-compliance-reviewer and verifier agents

**Files:**
- Create: `.claude/agents/spec-compliance-reviewer.md`
- Create: `.claude/agents/verifier.md`

**Interfaces:**
- Consumes: `.claude/skills/spec-audit/SKILL.md` (+ its script) and `.claude/skills/verify-gate/SKILL.md` by path.
- Produces: agent types `spec-compliance-reviewer` and `verifier`, referenced by Task 6's workflow via `agentType`. Reviewer reports findings as `R# · file:line · violation · fix · severity`; verifier reports gates with `pass|fail|not_present` and ends `VERIFY: PASS|FAIL`.

- [ ] **Step 1: Write the reviewer agent**

Create `.claude/agents/spec-compliance-reviewer.md` with exactly:

```markdown
---
name: spec-compliance-reviewer
description: Read-only auditor for the Arrived Investment Agent repo. Use to audit changed files, a directory, or the whole tree against the hard rules (R1–R31) of arrived-agent-spec.md — before completing work, after a builder finishes, or during review. It reports findings; it never fixes them.
tools: Read, Grep, Glob, Bash
---

You are a read-only spec-compliance auditor for this repo. `arrived-agent-spec.md` at the repo root is the single source of truth; every finding you report must cite one of its rule IDs (R1–R31) or sections (§). You NEVER edit files — use Bash only for read-only commands (grep, wc, find, ls, cat, git diff/status, and the audit script below).

## Procedure

1. Determine scope: the files, directories, or rule families named in your task. If none given, audit what `git status --short` and `git diff --name-only HEAD` show as changed.
2. Run `bash .claude/skills/spec-audit/scripts/mechanical-checks.sh` from the repo root and include its output in your report.
3. Read `.claude/skills/spec-audit/SKILL.md` and apply the judgment-checklist families relevant to your scope.
4. Read the actual code before reporting: never report a violation you have not confirmed at a specific file and line. Rules that need whole-module context (DuckDB connection ownership, engine invariants) require reading the full module, not a diff hunk.

## Report format

- One line per finding: `R# · file:line · what is violated · suggested fix · severity`.
- `violation` = breaks a MUST/NEVER rule. `concern` = SHOULD/PREFER or a smell worth flagging.
- End with an explicit coverage statement: `Audited families: <list> — N violations, M concerns.` A clean audit says "no violations" — never end in silence. While the repo is greenfield, missing paths are noted, not flagged.
- Stay on spec compliance: do not propose refactors, features, or style changes beyond what a cited rule requires.
```

- [ ] **Step 2: Write the verifier agent**

Create `.claude/agents/verifier.md` with exactly:

```markdown
---
name: verifier
description: Verification runner for the Arrived Investment Agent repo. Use to prove a change or build phase actually works before it is declared done — runs the project's verify-gate procedure and reports evidence. It never edits files and never claims success without command output.
tools: Bash, Read, Grep, Glob
---

You are the verification runner for this repo. Your job is to execute the project's quality gates and report what actually happened. You NEVER edit files.

## Procedure

1. Read `.claude/skills/verify-gate/SKILL.md` and execute its gates in order from the repo root.
2. Run every applicable gate — do not stop at the first failure.
3. For each gate report: the exact command run, the verdict, and pasted evidence (the relevant tail of real output).

## Rules

- A layer whose directory does not exist yet is `not_present` (build phase pending) — not a failure.
- A layer that exists but whose gate cannot run (missing deps, tool crash) is a **fail**, never a skip. Include the error output.
- Never claim a gate passed without having run its command in this session.
- Gate names come from the skill (`backend-lint`, `backend-types`, `backend-tests`, `frontend-types`, `frontend-tests`, `frontend-build`, `mechanical-audit`, `docker-smoke`) — use them verbatim.

## Report format

Per gate: `<name> · pass|fail|not_present · <one-line evidence>`, then the pasted output. Final line, always: `VERIFY: PASS` or `VERIFY: FAIL — <failed gate names>`.
```

- [ ] **Step 3: Verify frontmatter of both files**

Run: `for f in .claude/agents/spec-compliance-reviewer.md .claude/agents/verifier.md; do echo "== $f"; sed -n '1,5p' "$f"; done`
Expected: each opens with `---`, has `name:`, `description:`, `tools:` lines, and no `model:` line.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/spec-compliance-reviewer.md .claude/agents/verifier.md
git commit -m "feat: add spec-compliance-reviewer and verifier agents

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: backend-builder and frontend-builder agents

**Files:**
- Create: `.claude/agents/backend-builder.md`
- Create: `.claude/agents/frontend-builder.md`

**Interfaces:**
- Consumes: `arrived-agent-spec.md` (§ references in prompts).
- Produces: agent types `backend-builder` and `frontend-builder`, referenced by Task 6's workflow via `agentType`. Both end with an exit report containing real tool output.

- [ ] **Step 1: Write the backend builder**

Create `.claude/agents/backend-builder.md` with exactly:

```markdown
---
name: backend-builder
description: Implements backend build phases of the Arrived Investment Agent (spec §15 steps 1–5 and 8) and fixes backend findings. Use for any Python/FastAPI/DuckDB implementation work in this repo. Works test-first and reports ruff/mypy/pytest evidence.
---

You are the backend builder for the Arrived Investment Agent repo. You implement backend work exactly as specified in `arrived-agent-spec.md` — the single source of truth. `CLAUDE.md` is the orientation layer.

## Non-negotiable working rules

1. **Read before you build.** Before writing code, read the spec sections named in your task (at minimum §3, §4, and the sections for your phase). The file map in §4 is fixed: every file goes exactly where §4 says, with exactly that responsibility.
2. **Tests first.** Appendix A test files are canonical — copy them **verbatim** before implementing what they cover, and never edit them to make them pass. Work test-first; run `uv run pytest` (from `backend/`) continuously. A deliverable is done only when its tests pass.
3. **Layering (R1–R4).** `domain/` is pure — no I/O, no SDK or framework imports, no env reads. Services depend only on the Protocols in `domain/ports.py`. Concrete adapters live in `infrastructure/` and are wired only in `app/dependencies.py`. Routers contain zero business logic.
4. **DuckDB (R6–R11).** One process-wide `DuckDBConn`, shared via `cursor()`. All writes are keyed upserts except `plans` (insert/delete only). Explicit column lists — never `SELECT *`. UTC timestamps, `'YYYY-MM'` months. Offering→enrichment joins go through `market_aliases`.
5. **Engine (R12–R14, §6).** Deterministic, ties broken by offering id. Invalid input returns `{"feasible": false, "reason": ...}` — never raises. `score_breakdown` on every position. Momentum is a bounded tilt, never a gate. Money: integer USD, $10 increments, $100 minimum, `total_invested + unallocated == requested`.
6. **Standards (R5, R26–R28, R31).** Every file ≤ 200 lines — split by responsibility before you exceed it. Type hints on public functions; `from __future__ import annotations`; stdlib `logging` key=value, never `print` in `src/`; no swallowed exceptions; docstrings on every module and public class/function.
7. **Scope.** Never build anything from §16 (deferred) or §17 (out of scope). If your task conflicts with the spec, say so and stop instead of improvising.

## Exit report

End with: files created/modified, then the **actual output** of `uv run ruff check .`, `uv run mypy .`, and `uv run pytest` run from `backend/`. If any is red, say so plainly — never claim success without the passing output.
```

- [ ] **Step 2: Write the frontend builder**

Create `.claude/agents/frontend-builder.md` with exactly:

```markdown
---
name: frontend-builder
description: Implements frontend build phases of the Arrived Investment Agent (spec §15 steps 6–7) and fixes frontend findings. Use for any React/TypeScript/Vite implementation work in this repo. Works test-first and reports tsc/vitest/build evidence.
---

You are the frontend builder for the Arrived Investment Agent repo. You implement frontend work exactly as specified in `arrived-agent-spec.md` — the single source of truth. `CLAUDE.md` is the orientation layer.

## Non-negotiable working rules

1. **Read before you build.** Before writing code, read the spec sections named in your task (at minimum §4's frontend map and §9's SSE contract). The file map in §4 is fixed: every file goes exactly where §4 says.
2. **Tests first.** `frontend/src/api/sse.test.ts` from Appendix A is canonical — copy it **verbatim** before implementing the decoder, and never edit it to make it pass. Run `npx vitest run` and `npx tsc --noEmit` (from `frontend/`) continuously.
3. **SSE (R19, R18, §9).** Consume the chat stream with `fetch` + `ReadableStream` through `createSseDecoder` — `EventSource` is GET-only and CANNOT be used. The decoder must reassemble events split across chunk boundaries. Typed `*_result` events render as components; the transcript shows summaries, not restated tables.
4. **Types (R29).** TypeScript strict; never `any` in `src/`. SSE events are a discriminated union in `types/events.ts`, exhaustively switched (a `never`-typed default arm). `types/domain.ts` mirrors the backend models exactly.
5. **Standards (R5, R30).** Every file ≤ 200 lines — split components before you exceed it. The streaming assistant message region has `aria-live="polite"`; below the `md` breakpoint the two-pane layout stacks with the data panel reachable beneath the chat.
6. **Stack.** React 18 + TypeScript strict, Vite, Tailwind CSS, recharts for charts, zustand for state. `VITE_API_URL` defaults to `/api` (nginx proxy) and `http://localhost:8000/api` in local dev.
7. **Scope.** Never build anything from §16 (deferred) or §17 (out of scope). If your task conflicts with the spec, say so and stop instead of improvising.

## Exit report

End with: files created/modified, then the **actual output** of `npx tsc --noEmit`, `npx vitest run`, and `npm run build` run from `frontend/`. If any is red, say so plainly — never claim success without the passing output.
```

- [ ] **Step 3: Verify frontmatter of both files**

Run: `for f in .claude/agents/backend-builder.md .claude/agents/frontend-builder.md; do echo "== $f"; sed -n '1,4p' "$f"; done`
Expected: each opens with `---`, has `name:` and `description:`; builders have no `tools:` line (inherit all) and no `model:` line.

- [ ] **Step 4: Commit**

```bash
git add .claude/agents/backend-builder.md .claude/agents/frontend-builder.md
git commit -m "feat: add backend-builder and frontend-builder agents

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: build-phase workflow

**Files:**
- Create: `.claude/workflows/build-phase.js`

**Interfaces:**
- Consumes: agent types `backend-builder`, `frontend-builder`, `spec-compliance-reviewer`, `verifier` (Tasks 4–5); gate-name prefixes `frontend-*` from verify-gate (Task 3).
- Produces: named workflow `build-phase`, invoked with `args: {phase: 1..9}` or `{phase: "fix", scope: "<paths or note>"}`. Returns `{phase, rounds, open_violations, concerns, unaudited_families, gates, build_report}`.

- [ ] **Step 1: Write the workflow**

Create `.claude/workflows/build-phase.js` with exactly:

```javascript
export const meta = {
  name: 'build-phase',
  description: 'Build one spec §15 phase: builder implements, reviewers audit rule families in parallel, verifier runs the gates, fix loop until green (max 3 rounds)',
  whenToUse: 'Run with args {phase: 1..9} to execute one build-order step of arrived-agent-spec.md, or {phase: "fix", scope: "<paths>"} for an audit+fix round without building.',
  phases: [
    { title: 'Build', detail: 'builder agent implements the phase (TDD)' },
    { title: 'Audit', detail: 'parallel spec-compliance reviewers by rule family' },
    { title: 'Verify', detail: 'verifier runs the quality gates' },
    { title: 'Fix', detail: 'builders fix findings, then re-audit + re-verify' },
  ],
}

const PHASES = {
  1: { builder: 'backend-builder', what: 'Scaffold backend/pyproject.toml (deps + ruff/mypy/pytest config, asyncio_mode = auto) if missing. Copy Appendix A backend tests verbatim: tests/conftest.py, tests/domain/test_planner.py, tests/services/test_agent_service.py. Then implement the domain layer per §6/§7: domain/models.py, ports.py, risk.py, planner.py, market.py. tests/domain/test_planner.py must pass.' },
  2: { builder: 'backend-builder', what: 'Implement infrastructure/duckdb/connection.py, offerings_repo.py, plans_repo.py and infrastructure/seed.py per §5/§10. Write tests/infrastructure/test_repos.py per §12 (upsert idempotency, alias join, plans CRUD, snapshot immutability). All repo tests pass.' },
  3: { builder: 'backend-builder', what: 'Implement services/plan_service.py, market_service.py, tools.py per §8, and tests/services/test_tools.py plus tests/domain/test_market.py per §12. Tests pass.' },
  4: { builder: 'backend-builder', what: 'Implement services/agent_service.py and all app/ modules (main.py with lifespan seed, config.py, dependencies.py, api/routes_*.py, api/sse.py) per §9. Appendix A tests/services/test_agent_service.py and tests/api/test_api.py per §12 pass.' },
  5: { builder: 'backend-builder', what: 'Implement infrastructure/enrichment/zillow.py, fred.py, census.py, refresh.py per §10 and wire routes_admin.py refresh. Per-source isolation (R20); tests use mocked transports (R25). Tests pass.' },
  6: { builder: 'frontend-builder', what: 'Scaffold frontend (package.json, vite.config.ts, tsconfig strict, tailwind). Copy Appendix A src/api/sse.test.ts verbatim, then implement types/domain.ts, types/events.ts, api/sse.ts, api/client.ts, state/chatStore.ts, state/plansStore.ts per §4/§9. vitest + tsc pass.' },
  7: { builder: 'frontend-builder', what: 'Implement all components/ (chat/, data/, plan/, layout/) plus main.tsx and App.tsx two-pane layout per §4, R18, R30. tsc + vitest + vite build pass.' },
  8: { builder: 'backend-builder', what: 'Docker and CI per §11: backend/Dockerfile (multi-stage, non-root, HEALTHCHECK), frontend/Dockerfile + nginx.conf, docker-compose.yml (named volume, healthy-dependency), .github/workflows/ci.yml (offline, R22), backend/.env.example complete.' },
  9: { builder: 'backend-builder', what: 'End-to-end pass: walk every §15 acceptance criterion, fix anything failing, confirm offline operation (R21) via the docker-smoke gate.' },
}

const RULE_FAMILIES = [
  { key: 'layering', rules: 'R1–R4 (domain purity, ports-only services, single composition root, thin routers) and §3 sanctioned patterns' },
  { key: 'data', rules: 'R6–R11 (single DuckDB writer/connection, keyed upserts, explicit columns, UTC timestamps, alias joins) and §5 schema fidelity' },
  { key: 'contracts', rules: 'R12–R19 (engine invariants and §6 money rules, bounded momentum tilt, plan snapshot immutability, history truncation, SSE contract per §9)' },
  { key: 'standards', rules: 'R5 and R20–R31 (line cap, enrichment isolation, offline operation, CI/secrets/pinning, test hygiene, code standards, accessibility) plus §16/§17 scope' },
]

const FINDINGS_SCHEMA = {
  type: 'object',
  required: ['findings', 'audited'],
  properties: {
    audited: { type: 'string', description: 'Coverage statement: families audited, counts' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        required: ['rule', 'file', 'severity', 'description', 'fix'],
        properties: {
          rule: { type: 'string', description: 'Spec rule ID like R7, or section like §6' },
          file: { type: 'string', description: 'Repo-relative path' },
          line: { type: 'integer' },
          severity: { enum: ['violation', 'concern'] },
          description: { type: 'string' },
          fix: { type: 'string' },
        },
      },
    },
  },
}

const GATES_SCHEMA = {
  type: 'object',
  required: ['passed', 'gates'],
  properties: {
    passed: { type: 'boolean' },
    gates: {
      type: 'array',
      items: {
        type: 'object',
        required: ['name', 'status', 'evidence'],
        properties: {
          name: { type: 'string', description: 'Gate name from verify-gate skill, verbatim' },
          status: { enum: ['pass', 'fail', 'not_present'] },
          evidence: { type: 'string' },
        },
      },
    },
  },
}

const phaseKey = args && args.phase
if (phaseKey === undefined || (phaseKey !== 'fix' && !PHASES[phaseKey])) {
  throw new Error('args.phase must be 1-9 or "fix" (got: ' + JSON.stringify(phaseKey) + ')')
}

const auditContext = phaseKey === 'fix'
  ? 'Focus on: ' + ((args && args.scope) || 'files reported changed by git status / git diff.')
  : 'The repo just completed spec §15 build step ' + phaseKey + '.'

phase('Build')
let buildReport
if (phaseKey === 'fix') {
  buildReport = 'fix-only round; scope: ' + ((args && args.scope) || 'whole repo')
  log('Fix-only run — skipping the Build stage')
} else {
  const p = PHASES[phaseKey]
  buildReport = await agent(
    'Implement spec §15 build-order step ' + phaseKey + ' of arrived-agent-spec.md.\n\n' + p.what +
    '\n\nFollow your standing rules (spec sections first, tests first, never touch §16/§17). Finish with your exit report.',
    { agentType: p.builder, label: 'build:' + phaseKey, phase: 'Build' },
  )
  if (buildReport === null) throw new Error('builder agent failed for phase ' + phaseKey)
}

async function audit(round) {
  const runFamily = (f) => agent(
    'Audit the current repo state against ' + f.rules + '. ' + auditContext +
    ' Confirm every finding at a specific file:line before reporting it. Round ' + round + '.',
    { agentType: 'spec-compliance-reviewer', label: 'audit:' + f.key + ':' + round, phase: 'Audit', schema: FINDINGS_SCHEMA },
  )
  const first = await parallel(RULE_FAMILIES.map((f) => () => runFamily(f)))
  const results = await parallel(RULE_FAMILIES.map((f, i) => () =>
    first[i] ? Promise.resolve(first[i]) : runFamily(f)))
  const missing = RULE_FAMILIES.filter((_, i) => !results[i]).map((f) => f.key)
  if (missing.length) log('Audit families failed twice (not audited this round): ' + missing.join(', '))
  return { findings: results.filter(Boolean).flatMap((r) => r.findings || []), missing }
}

async function verify(round) {
  const run = () => agent(
    'Run the verify-gate procedure over the current repo state (round ' + round + '). Return structured gate results using the gate names from the skill verbatim.',
    { agentType: 'verifier', label: 'verify:' + round, phase: 'Verify', schema: GATES_SCHEMA },
  )
  const first = await run()
  if (first) return first
  log('verifier returned nothing; retrying once')
  const second = await run()
  if (second) return second
  return { passed: false, gates: [{ name: 'verifier', status: 'fail', evidence: 'verifier agent failed twice' }] }
}

async function fixRound(round, violations, failedGates) {
  const feViolations = violations.filter((v) => (v.file || '').startsWith('frontend/'))
  const beViolations = violations.filter((v) => !(v.file || '').startsWith('frontend/'))
  const feGates = failedGates.filter((g) => g.name.startsWith('frontend-'))
  const beGates = failedGates.filter((g) => !g.name.startsWith('frontend-'))
  if (beViolations.length || beGates.length) {
    await agent(
      'Fix the following spec violations and failed gates (root causes, not patches). Gates without a frontend- prefix are routed to you even if mixed; fix what lives in your tree and report anything that does not:\n' +
      JSON.stringify({ violations: beViolations, failed_gates: beGates }, null, 2) +
      '\nFollow your standing rules. Finish with your exit report.',
      { agentType: 'backend-builder', label: 'fix:be:' + round, phase: 'Fix' },
    )
  }
  if (feViolations.length || feGates.length) {
    await agent(
      'Fix the following spec violations and failed gates (root causes, not patches):\n' +
      JSON.stringify({ violations: feViolations, failed_gates: feGates }, null, 2) +
      '\nFollow your standing rules. Finish with your exit report.',
      { agentType: 'frontend-builder', label: 'fix:fe:' + round, phase: 'Fix' },
    )
  }
}

phase('Audit')
let auditRes = await audit(1)
phase('Verify')
let gates = await verify(1)

const MAX_ROUNDS = 3
let round = 1
while (true) {
  const violations = auditRes.findings.filter((f) => f.severity === 'violation')
  const failedGates = (gates.gates || []).filter((g) => g.status === 'fail')
  if (!violations.length && !failedGates.length) break
  if (round >= MAX_ROUNDS) {
    log('Round cap reached with open items: ' + violations.length + ' violation(s), ' + failedGates.length + ' failed gate(s)')
    break
  }
  round += 1
  log('Fix round ' + round + ': ' + violations.length + ' violation(s), ' + failedGates.length + ' failed gate(s)')
  phase('Fix')
  await fixRound(round, violations, failedGates)
  auditRes = await audit(round)
  gates = await verify(round)
}

return {
  phase: phaseKey,
  rounds: round,
  open_violations: auditRes.findings.filter((f) => f.severity === 'violation'),
  concerns: auditRes.findings.filter((f) => f.severity === 'concern'),
  unaudited_families: auditRes.missing,
  gates: gates,
  build_report: typeof buildReport === 'string' ? buildReport.slice(-3000) : buildReport,
}
```

- [ ] **Step 2: Validate parse + arg guard without spawning agents**

Invoke the Workflow tool with `{scriptPath: ".claude/workflows/build-phase.js", args: {"phase": 0}}` and wait for completion.
Expected: the run fails fast with `args.phase must be 1-9 or "fix" (got: 0)` and zero agents spawned — proving the script parses, `meta` is valid, and the guard works. (If the Workflow tool is unavailable to you, validate syntax instead by confirming the file has balanced braces and the exact `export const meta` opener: `head -1 .claude/workflows/build-phase.js` → `export const meta = {`.)

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/build-phase.js
git commit -m "feat: add build-phase workflow

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: CLAUDE.md tooling section + end-to-end validation

**Files:**
- Modify: `CLAUDE.md` (append a section at the end)

**Interfaces:**
- Consumes: everything from Tasks 1–6 by name.
- Produces: the documented entry points future sessions will use.

- [ ] **Step 1: Append the tooling section to CLAUDE.md**

Append to the end of `CLAUDE.md` (after the "Hard rules that shape every file" section) exactly:

```markdown

## Project tooling (.claude/)

- **Build a spec phase:** run the `build-phase` workflow with `{phase: 1..9}` (spec §15 steps) — the right builder agent implements, spec-compliance reviewers audit rule families in parallel, the verifier runs the gates, and a fix loop runs until green (max 3 rounds). `{phase: "fix", scope: "..."}` runs an audit+fix round without building.
- **Agents:** `backend-builder` / `frontend-builder` implement phases and fixes; `spec-compliance-reviewer` audits against R1–R31 (read-only); `verifier` runs the gates and reports evidence.
- **Skills:** invoke `spec-audit` before completing any change that touched source (mechanical script + judgment checklist); invoke `verify-gate` before claiming anything complete — a gate that cannot run is a failure, not a skip.
```

- [ ] **Step 2: End-to-end dry run — reviewer**

Dispatch an Agent with `subagent_type: "spec-compliance-reviewer"` and prompt: `Audit the whole repo against all rule families. The repo is greenfield (no backend/ or frontend/ yet) — confirm the tooling behaves correctly in that state.`
Expected: report shows the mechanical script's NOTE lines + PASS, and a coverage statement with 0 violations. (If the new agent type is not yet registered in this session, dispatch a `general-purpose` agent with the prompt: `Read .claude/agents/spec-compliance-reviewer.md and follow it exactly as your instructions for this task: audit the whole repo against all rule families.` — same expectation.)

- [ ] **Step 3: End-to-end dry run — verifier**

Dispatch an Agent with `subagent_type: "verifier"` and prompt: `Run the verify-gate procedure over the current repo state.`
Expected: gates 1–6 and 8 reported `not_present`, `mechanical-audit` reported `pass`, final line `VERIFY: PASS`. (Same general-purpose fallback as Step 2 if needed, reading `.claude/agents/verifier.md`.)

- [ ] **Step 4: Final tree check and commit**

Run: `find .claude -type f | sort`
Expected exactly:

```
.claude/agents/backend-builder.md
.claude/agents/frontend-builder.md
.claude/agents/spec-compliance-reviewer.md
.claude/agents/verifier.md
.claude/skills/spec-audit/SKILL.md
.claude/skills/spec-audit/scripts/mechanical-checks.sh
.claude/skills/verify-gate/SKILL.md
.claude/workflows/build-phase.js
```

```bash
git add CLAUDE.md
git commit -m "docs: point CLAUDE.md at project tooling

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```
