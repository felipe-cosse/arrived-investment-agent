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
  4: { builder: 'backend-builder', what: 'Implement services/agent_service.py and all app/ modules (main.py with lifespan seed, config.py, dependencies.py, infrastructure/anthropic_client.py (thin AsyncAnthropic factory), api/routes_*.py, api/sse.py) per §9. Appendix A tests/services/test_agent_service.py and tests/api/test_api.py per §12 pass.' },
  5: { builder: 'backend-builder', what: 'Implement infrastructure/enrichment/zillow.py, fred.py, census.py, refresh.py per §10 and wire routes_admin.py refresh. Per-source isolation (R20); tests use mocked transports (R25). Tests pass.' },
  6: { builder: 'frontend-builder', what: 'Scaffold frontend (package.json, vite.config.ts, tsconfig strict, tailwind — encode the DESIGN.md tokens in the Tailwind config: colors, Inter typography, spacing, rounding). Copy Appendix A src/api/sse.test.ts verbatim, then implement types/domain.ts, types/events.ts, api/sse.ts, api/client.ts, state/chatStore.ts, state/plansStore.ts per §4/§9. vitest + tsc pass.' },
  7: { builder: 'frontend-builder', what: 'Implement all components/ (chat/, data/, plan/, layout/) plus main.tsx and App.tsx two-pane layout per §4, R18, R30, styled strictly per DESIGN.md (card/button-primary tokens, accent+success charts, success for positive yields, shadow elevation). tsc + vitest + vite build pass.' },
  8: { builder: 'backend-builder', what: 'Docker and CI per §11: backend/Dockerfile (multi-stage, non-root, HEALTHCHECK), frontend/Dockerfile + nginx.conf, docker-compose.yml (named volume, healthy-dependency), .github/workflows/ci.yml (offline, R22), backend/.env.example complete.' },
  9: { builder: 'backend-builder', what: 'End-to-end pass: walk every §15 acceptance criterion, fix anything failing, confirm offline operation (R21) via the docker-smoke gate.' },
}

const RULE_FAMILIES = [
  { key: 'layering', rules: 'R1–R4 (domain purity, ports-only services, single composition root, thin routers) and §3 sanctioned patterns' },
  { key: 'data', rules: 'R6–R11 (single DuckDB writer/connection, keyed upserts, explicit columns, UTC timestamps, alias joins) and §5 schema fidelity' },
  { key: 'contracts', rules: 'R12–R19 (engine invariants and §6 money rules, bounded momentum tilt, plan snapshot immutability, history truncation, SSE contract per §9)' },
  { key: 'standards', rules: 'R5 and R20–R31 (line cap, enrichment isolation, offline operation, CI/secrets/pinning, test hygiene, code standards, accessibility) plus §16/§17 scope, plus the DESIGN.md visual identity for frontend code (tokens, component rules, layout)' },
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

let input = args
if (typeof input === 'string') {
  try { input = JSON.parse(input) } catch (e) {
    throw new Error('args must be JSON like {"phase": 1}; got unparseable string: ' + input)
  }
}
input = input || {}
const phaseKey = input.phase
if (phaseKey === undefined || (phaseKey !== 'fix' && !PHASES[phaseKey])) {
  throw new Error('args.phase must be 1-9 or "fix" (got: ' + JSON.stringify(phaseKey) + ')')
}

const auditContext = phaseKey === 'fix'
  ? 'Focus on: ' + (input.scope || 'files reported changed by git status / git diff.')
  : 'The repo just completed spec §15 build step ' + phaseKey + '.'

phase('Build')
let buildReport
if (phaseKey === 'fix') {
  buildReport = 'fix-only round; scope: ' + (input.scope || 'whole repo')
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
  return { passed: false, synthetic: true, gates: [{ name: 'verifier', status: 'fail', evidence: 'verifier agent failed twice' }] }
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
  if (gates.synthetic) {
    log('verifier unavailable after retries; stopping fix loop — gates unknown')
    break
  }
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
