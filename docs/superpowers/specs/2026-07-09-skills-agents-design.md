# Claude Code Skills & Agents for the Arrived Investment Agent — Design

**Date:** 2026-07-09
**Status:** Approved
**Goal:** Give future Claude Code sessions the tooling to *build* the app from `arrived-agent-spec.md` and to *enforce* the spec's rules on every change — 4 agents, 2 skills, 1 orchestration workflow, all project-local and committed.

## Context

The repo is greenfield: `arrived-agent-spec.md` (v3 build spec, single source of truth) and `CLAUDE.md` (orientation layer). Nothing is built. The spec has 31 auditable hard rules (R1–R31), a fixed file map (§4), canonical tests (Appendix A, copy verbatim), and a 9-step build order (§15). The tooling below encodes *procedure and enforcement*; it never duplicates spec content — it references sections and rule IDs.

## Deliverables

```text
.claude/
├── agents/
│   ├── backend-builder.md
│   ├── frontend-builder.md
│   ├── spec-compliance-reviewer.md
│   └── verifier.md
├── skills/
│   ├── spec-audit/
│   │   ├── SKILL.md
│   │   └── scripts/mechanical-checks.sh
│   └── verify-gate/
│       └── SKILL.md
└── workflows/
    └── build-phase.js
```

Plus: `git init` + initial commit (spec, CLAUDE.md, this doc, `.claude/`), and a short "Project tooling" section appended to `CLAUDE.md` pointing at these artifacts.

## Agents

All agent files: YAML frontmatter (`name`, `description`, `tools`) + system prompt in the body. No `model` field — agents inherit the session model. Descriptions must state *when to use* so the main session dispatches correctly.

### backend-builder

- **Tools:** all (Read, Write, Edit, Bash, Grep, Glob).
- **Use when:** implementing backend build phases (spec §15 steps 1–5) or fixing backend findings.
- **Prompt encodes:**
  - Spec is the source of truth; read the relevant § before writing code. File responsibilities are fixed by §4 — create files exactly there.
  - TDD: Appendix A tests are copied verbatim *before* implementation; `uv run pytest` continuously; a task is done only when relevant tests pass.
  - Hard constraints restated with rule IDs: R1–R4 (pure domain, ports-only services, single composition root, thin routers), R5 (≤200 lines/file), R6–R11 (single DuckDB connection, keyed upserts, explicit columns, UTC, alias joins), R12–R14 (engine returns `{"feasible": false, ...}` on bad input, score_breakdown per position, momentum is a bounded tilt), R26–R28 (type hints, structured logging, fail loud).
  - Never build §16 (deferred) or §17 (out of scope) items.
  - Exit report must include actual `ruff` / `mypy` / `pytest` output.

### frontend-builder

- **Tools:** all.
- **Use when:** implementing frontend build phases (spec §15 steps 6–7) or fixing frontend findings.
- **Prompt encodes:** TS strict, no `any` in `src/` (R29); SSE events as a discriminated union, exhaustively switched; `fetch` + `ReadableStream` through `createSseDecoder`, never `EventSource` (R19); `sse.test.ts` from Appendix A verbatim before implementing the decoder; types in `types/domain.ts` mirror backend models; R5 line cap; R30 accessibility (aria-live on streaming region, responsive stacking below `md`); typed `*_result` events render as components (R18). Exit report includes `tsc --noEmit` + `vitest run` output.

### spec-compliance-reviewer

- **Tools:** Read, Grep, Glob, Bash (read-only usage: grep/wc/find — never edits files).
- **Use when:** auditing changed files or a directory against the spec before completing work or merging.
- **Prompt encodes:** run the `spec-audit` skill's mechanical script first, then apply the judgment checklist for the rules in scope. Report each finding as `rule ID · file:line · what's violated · suggested fix`, with severity (violation vs. concern). No finding without a rule ID or spec section. Explicitly told: absence of findings must be stated as "audited rules X–Y, no violations", never silence.

### verifier

- **Tools:** Bash, Read, Grep, Glob (never edits files).
- **Use when:** proving a phase/change works before it is declared done.
- **Prompt encodes:** execute the `verify-gate` skill's gates in order; paste real command output per gate; a gate that cannot run is a **failure**, not a skip (except layers that don't exist yet — reported as "not present"); never assert success without having run the command.

## Skills

Skill format: `.claude/skills/<name>/SKILL.md` with frontmatter (`name`, `description` stating when to use) + procedure body. Bundled scripts live beside the skill.

### spec-audit

- **When to use:** before completing any task that touched source files; after a builder agent finishes; on demand via `/spec-audit`.
- **Layer 1 — mechanical script** (`scripts/mechanical-checks.sh`, bash, exits non-zero on findings, prints `file:line rule-id message`):
  - R5: any file under `backend/src`, `backend/tests`, `frontend/src` over 200 lines.
  - R1: forbidden imports in `backend/src/domain/` — `fastapi`, `duckdb`, `httpx`, `anthropic`, `pydantic_settings`, `os.environ`/`os.getenv`.
  - R9: `SELECT *` in `backend/src`.
  - R27: `print(` in `backend/src`.
  - R29: `: any`, `as any`, `<any>` in `frontend/src`.
  - R19: `EventSource` in `frontend/src`.
  - R10: `datetime.now()` without `UTC`/`timezone.utc` in `backend/src`.
  - R23: obvious secret patterns (`sk-ant-`, `api_key = "` literals) anywhere tracked.
  - Paths that don't exist yet are skipped with a notice (greenfield-safe).
- **Layer 2 — judgment checklist** (rules a script can't verify), grouped for auditability: layering & DI (R2–R4), DuckDB semantics (R6–R8, R11), engine invariants (R12–R14, §6 money rules), API/SSE contract (R16–R19), enrichment isolation & offline (R20–R21), infra (R22, R24), standards (R25–R26, R28, R30–R31). Each entry: what to look at, what "violated" looks like.
- **Output contract:** findings table with rule IDs; "no violations in scope" stated explicitly.

### verify-gate

- **When to use:** before claiming any task complete, fixed, or passing; the project-level procedure the built-in `/verify` skill bootstraps to.
- **Gates, in order** (stop-on-red within a layer is not allowed — run all, report all):
  1. Backend static: `cd backend && uv run ruff check . && uv run mypy .`
  2. Backend tests: `uv run pytest` (single test syntax documented for targeted reruns).
  3. Frontend static: `cd frontend && npx tsc --noEmit`
  4. Frontend tests + build: `npx vitest run && npm run build`
  5. Mechanical spec audit: run `spec-audit`'s script.
  6. (When Docker phase exists / on request) `docker compose up --build` with **no API keys in env**, then smoke: `GET /api/health`, `GET /api/offerings` returns 11, `POST /api/plan` deterministic across two identical calls — pinning R21 offline operation.
- **Rules:** each gate's verdict comes with pasted output; a missing layer is "not present (repo phase N)", but an existing layer failing to run is a hard fail; final line is an explicit PASS/FAIL summary.

## Workflow

### `.claude/workflows/build-phase.js`

- **Input:** `args = { phase: <1–9> }` mapping to spec §15 build order steps. Also accepts `{ phase: "fix", scope: "<paths>" }` for a fix-only round.
- **meta.phases:** Build → Audit → Verify → Fix.
- **Flow:**
  1. **Build:** one builder agent (`agentType: 'backend-builder'` for phases 1–5 and 8-backend, `'frontend-builder'` for 6–7; phase 8/9 may use both sequentially). Sequential — builders never run in parallel (shared files, no worktree overhead).
  2. **Audit:** parallel `spec-compliance-reviewer` agents, rule families split across 3–4 reviewers (layering/purity · data/DuckDB · contracts (engine+API/SSE) · standards), each returning structured findings (JSON schema: rule_id, file, line, severity, description, fix).
  3. **Verify:** one `verifier` agent returning `{gates: [{name, passed, evidence}], passed}`.
  4. **Fix loop:** while (findings with severity=violation OR failed gates) and rounds < 3: builder fixes → re-audit only affected rule families → re-verify. `log()` what remains if rounds exhaust.
  5. **Return:** phase report `{phase, built, findings_open, gates, rounds}`.

## Housekeeping

- `git init`; initial commit: `arrived-agent-spec.md`, `CLAUDE.md`, this design doc. The `.claude/**` tooling is committed as it is built. `.gitignore` seeded with the obvious (`.env`, `data/`, `node_modules/`, `__pycache__/`, `dist/`).
- `CLAUDE.md` gains a short **Project tooling** section: which agent/skill/workflow to reach for at each moment (build phase → workflow; ad-hoc change → spec-audit + verify-gate; review → spec-compliance-reviewer).

## Error handling

- Mechanical script: missing directories are notices, not errors; grep exit codes handled so "no match" ≠ failure.
- Workflow: builder/reviewer agent returning null (skipped/errored) is retried once, then surfaced in the phase report — never silently dropped.
- Verifier: distinguishes "gate failed" from "gate could not run"; both block completion.

## Testing the tooling itself

- Mechanical script gets a self-test: run against a scratch fixture tree containing one planted violation per check; assert each is caught and clean files pass. (Run manually at creation time; fixture lives in the scratchpad, not the repo.)
- Agents/skills are validated by a dry run: reviewer audits the spec repo as-is (expect "no source present" notices), verifier reports all layers "not present" — proving greenfield-safe behavior before the build starts.

## Out of scope

- No CI wiring for these tools (the spec's §11 CI covers the app; tooling runs locally).
- No auto-trigger hooks (e.g., PostToolUse audit) — can be added later via settings if wanted.
- No MCP servers, no additional workflows beyond build-phase.
