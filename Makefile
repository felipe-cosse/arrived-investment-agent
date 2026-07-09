# Arrived Investment Agent — task shortcuts.
# Commands mirror the project's verification gates; see CLAUDE.md.

.DEFAULT_GOAL := help
.PHONY: help install dev-api dev-web test test-backend test-frontend lint typecheck audit build verify up down logs refresh clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv sync) and frontend (npm install) dependencies
	cd backend && uv sync
	cd frontend && npm install

dev-api: ## Run the API locally with reload on :8000
	cd backend && PYTHONPATH=src uv run uvicorn app.main:app --reload --port 8000

dev-web: ## Run the Vite dev server on :5173 (expects the API on :8000)
	cd frontend && VITE_API_URL=http://localhost:8000/api npm run dev

test: test-backend test-frontend ## Run all test suites

test-backend: ## Backend pytest suite
	cd backend && uv run pytest

test-frontend: ## Frontend vitest suite
	cd frontend && npx vitest run

lint: ## Ruff over the backend
	cd backend && uv run ruff check .

typecheck: ## mypy (backend) + tsc --noEmit (frontend)
	cd backend && uv run mypy .
	cd frontend && npx tsc --noEmit

audit: ## Mechanical spec-rule checks (local .claude tooling; skipped if absent)
	@if [ -f .claude/skills/spec-audit/scripts/mechanical-checks.sh ]; then \
		bash .claude/skills/spec-audit/scripts/mechanical-checks.sh; \
	else \
		echo "spec-audit script not present (local-only tooling); skipped"; \
	fi

build: ## Production frontend build (includes tsc)
	cd frontend && npm run build

verify: lint typecheck test build audit ## Full verification gate

up: ## Build and start the full stack (web :5173, api :8000)
	docker compose up --build -d

down: ## Stop the stack
	docker compose down

logs: ## Tail compose logs
	docker compose logs -f

refresh: ## Enrichment refresh CLI — ONLY while the API is stopped (single-writer rule R6)
	cd backend && PYTHONPATH=src uv run python -m infrastructure.enrichment.refresh

clean: ## Remove build artifacts and caches
	rm -rf frontend/dist backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
