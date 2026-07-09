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
  ':[[:space:]]*any([^[:alnum:]_]|$)|(^|[^[:alnum:]_])as[[:space:]]+any([^[:alnum:]_]|$)|<any>' \
  frontend/src --include='*.ts' --include='*.tsx'

# R19 — SSE is consumed via fetch + ReadableStream, never EventSource
scan R19 "use fetch + ReadableStream via createSseDecoder, never EventSource" \
  'new[[:space:]]+EventSource' \
  frontend/src --include='*.ts' --include='*.tsx'

# R10 — timestamps must be UTC-aware
scan R10 "naive datetime (use datetime.now(UTC))" \
  'datetime\.now\(\)|\.utcnow\(' \
  backend/src --include='*.py'

# R23 — no secret literals in committed trees (.env is local-only, skip it)
for p in backend frontend docker-compose.yml; do
  scan R23 "possible secret literal committed" \
    'sk-ant-|API_KEY[[:space:]]*=[[:space:]]*"[A-Za-z0-9]' \
    "$p" --exclude='.env' --exclude-dir='tests'
done

if [ "$findings" -gt 0 ]; then
  printf 'FAIL: %d mechanical finding(s)\n' "$findings"
  exit 1
fi
echo "PASS: no mechanical findings"
