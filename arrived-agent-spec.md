# Arrived Investment Agent — Build Specification (v3)

Single source of truth for building this app. Written to be executed by Claude Code. Also usable as the repo's `CLAUDE.md`: rules use **MUST / NEVER** (hard) and **SHOULD / PREFER** (preference) so compliance is auditable. Appendix A contains canonical test files — copy them **verbatim** and build until they pass.

v3 changes: saved-plan snapshots · existing-holdings-aware allocation · per-position score breakdowns · leverage-aware scoring · property-type share caps · seed windows relative to today · per-source region maps · server-side history truncation · `/api/meta` staleness · canonical SSE-decoder test · CI workflow. §16 lists deferred items — do not build those.

## 1. What we are building

A web app that explores fractional real-estate offerings (modeled on Arrived, arrived.com) and helps a user build a hypothetical investment plan for a defined dollar amount.

- **Chat agent** (Claude via Anthropic API, tool use) answers questions about offerings and builds plans by calling tools — it never invents data or does allocation math itself.
- **Data explorer UI** shows offerings with filters; **plan views** render allocations and projections as charts.
- **Deterministic planner** does all allocation math in pure Python. Same inputs → same plan, always. Every position carries a **score breakdown** so "why is X ranked above Y?" is answered with data.
- **Existing holdings**: the planner accepts current positions and allocates *new* money around them — caps, market limits, and the fund floor account for what's already held.
- **Saved plans** are immutable snapshots (inputs + full output + data `as_of`), because enrichment refreshes change future runs; a compare view sits beside the explorer.
- **Market enrichment layer** joins offerings with external data (home-value/rent indexes, employment, demographics), feeding an agent tool and a bounded planner tilt.
- Arrived has **no public API**. The database is seeded with realistic mock data behind the same schema a future scraper will fill. Live scraping is out of scope; live *enrichment* fetchers are in scope but optional at runtime (§10).
- Educational/research tool. Every plan output MUST carry a "hypothetical projection, not investment advice" disclaimer, and the agent MUST repeat that briefly when presenting a plan.

## 2. Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn, Anthropic Python SDK (async), DuckDB, httpx, pydantic v2 + pydantic-settings |
| Frontend | React 18 + TypeScript (strict), Vite, Tailwind CSS, recharts, zustand |
| Infra | Docker (multi-stage), docker-compose, nginx (serves frontend, proxies `/api`), GitHub Actions CI |
| Tooling | ruff, mypy, pytest + pytest-asyncio, vitest |

Default model: `claude-sonnet-5` (env-overridable). API key only ever read from environment.

## 3. Architecture and layering

Layered, ports-and-adapters style. Dependencies point inward only:

```
api (FastAPI routers, SSE)  →  services (orchestration, agent loop, tools)
                            →  domain (entities, risk strategies, engine, market math)  ← pure
infrastructure (DuckDB repos, Anthropic adapter, enrichment fetchers, seeder) implements domain ports
```

**Hard layering rules**

- R1. `domain/` MUST be pure: no I/O, no SDK imports, no framework imports, no env reads.
- R2. Services MUST depend on the `Protocol` ports in `domain/ports.py`, never directly on DuckDB, httpx, or the Anthropic SDK (Dependency Inversion).
- R3. Concrete adapters live only in `infrastructure/` and are wired in `app/dependencies.py` via FastAPI `Depends` (single composition root).
- R4. Routers MUST contain no business logic — parse/validate, call a service, shape the response.

**Ports (`domain/ports.py`)** — small on purpose (ISP):

- `OfferingReader`: `list_offerings(...)`, `get_offering(id)`, `get_returns(id, months)`, `get_market_metrics(metro, months)`, `get_metro_for_market(raw_market)`, `stats()`
- `OfferingWriter`: `upsert_offerings(rows)`, `upsert_returns(rows)`, `upsert_market_metrics(rows)`, `upsert_market_aliases(rows)`
- `PlanStore`: `save(record) -> str`, `list_plans()`, `get_plan(id)`, `delete_plan(id)`, `stats()`
- `MarketDataSource`: `name: str`, `fetch(metros: list[str]) -> list[MetricRow]` — one implementation per external provider
- `LLMClient`: structurally mirrors the Anthropic SDK — `stream(*, model, max_tokens, system, messages, tools)` returns an async context manager that is async-iterable over events (`content_block_start`, `content_block_delta`, …) and exposes `await get_final_message()` (`.stop_reason`, `.content`). The fake in Appendix A is the contract.

**SOLID, applied concretely**

- SRP: one responsibility per module/class; enforced by the file map in §4 and the 200-line cap.
- OCP: risk profiles are Strategy objects in a registry (`domain/risk.py`); enrichment providers implement `MarketDataSource`. Adding a profile or source = one class + registry entry, zero engine/service edits.
- LSP: any implementation of a port MUST satisfy the contracts the tests assert.
- DIP: the agent loop takes an `LLMClient`; tests inject a scripted fake, never the network.

**Patterns to use (and no more):** Repository, Strategy (risk), Adapter (Anthropic SDK, each enrichment provider), Dependency Injection, App Factory (`create_app()`). NEVER add patterns speculatively.

## 4. Repository layout

Every file's responsibility is fixed. **R5. Every source file (backend and frontend, tests included) MUST be ≤ 200 lines.** If a file wants to grow past that, split by responsibility.

```
/
├── docker-compose.yml
├── SPEC.md                          # this file (also serves as CLAUDE.md)
├── .github/workflows/ci.yml         # §11
├── backend/
│   ├── Dockerfile                   # multi-stage, non-root
│   ├── pyproject.toml               # deps + ruff/mypy/pytest config
│   ├── uv.lock                      # lockfile committed (uv preferred)
│   ├── .env.example
│   ├── src/
│   │   ├── app/
│   │   │   ├── main.py              # create_app(), lifespan (init + seed if empty), router mounting
│   │   │   ├── config.py            # pydantic-settings Settings
│   │   │   ├── dependencies.py      # composition root: conn, repos, llm, services, dispatcher
│   │   │   └── api/
│   │   │       ├── routes_offerings.py  # GET /api/offerings, /api/offerings/{id}
│   │   │       ├── routes_plan.py       # POST /api/plan
│   │   │       ├── routes_plans.py      # saved plans CRUD (§9)
│   │   │       ├── routes_chat.py       # POST /api/chat (SSE)
│   │   │       ├── routes_admin.py      # POST /api/admin/refresh-market-data
│   │   │       ├── routes_meta.py       # GET /api/meta (staleness)
│   │   │       └── sse.py               # event formatting helper
│   │   ├── domain/
│   │   │   ├── models.py            # Offering, ReturnRecord, MetricRow, Position, Plan, PlanRecord (pydantic, frozen)
│   │   │   ├── ports.py             # Protocols above
│   │   │   ├── risk.py              # RiskStrategy + RISK_STRATEGIES registry
│   │   │   ├── planner.py           # AllocationEngine — deterministic core (§6)
│   │   │   └── market.py            # pure market math: YoY, momentum, MarketContext (§7)
│   │   ├── services/
│   │   │   ├── plan_service.py      # PlanService(reader, store): strategy + momentum → engine; save/list snapshots
│   │   │   ├── market_service.py    # MarketService(reader): metrics → MarketContext for a market
│   │   │   ├── tools.py             # ToolDispatcher(reader, plan_service, market_service): schemas + dispatch (§8)
│   │   │   └── agent_service.py     # AgentService(llm, tools): truncate history → tool loop → SSE (§9)
│   │   └── infrastructure/
│   │       ├── duckdb/
│   │       │   ├── connection.py    # DuckDBConn(db_path): the process's ONE connection, cursor() helper, schema init
│   │       │   ├── offerings_repo.py# OfferingsRepo(conn) → OfferingReader/Writer
│   │       │   └── plans_repo.py    # PlansRepo(conn) → PlanStore
│   │       ├── anthropic_client.py  # thin factory: AsyncAnthropic satisfies LLMClient structurally
│   │       ├── seed.py              # seed_all(writer): offerings, returns, metrics, aliases (§10)
│   │       └── enrichment/
│   │           ├── zillow.py        # ZHVI + ZORI research CSVs (no key) + its REGION_MAP
│   │           ├── fred.py          # metro unemployment (FRED_API_KEY) + its series map
│   │           ├── census.py        # ACS population + median income (key optional) + its geo map
│   │           └── refresh.py       # run enabled sources → upserts; also `python -m` entrypoint
│   └── tests/                       # §12 + Appendix A — mirrors src structure
├── frontend/
│   ├── Dockerfile                   # node build stage → nginx runtime
│   ├── nginx.conf                   # serve static; proxy /api/ → api:8000
│   ├── package.json, vite.config.ts, tsconfig.json, tailwind.config.*
│   └── src/
│       ├── main.tsx, App.tsx        # two-pane layout: chat left, data panel right; stacks below `md`
│       ├── api/client.ts            # REST calls (offerings, plan, plans CRUD, meta, admin refresh)
│       ├── api/sse.ts               # createSseDecoder + POST ReadableStream reader (NOT EventSource — §9)
│       ├── types/domain.ts          # Offering, Plan, MarketContext, PlanRecord (mirror backend)
│       ├── types/events.ts          # discriminated union of SSE events
│       ├── state/chatStore.ts       # zustand: messages, streaming text, panel content
│       ├── state/plansStore.ts      # zustand: saved plans, compare selection
│       └── components/
│           ├── chat/    ChatPanel.tsx, MessageList.tsx, Composer.tsx, ToolStatus.tsx
│           ├── data/    OfferingExplorer.tsx, OfferingCard.tsx, Filters.tsx, ReturnsChart.tsx, MarketContextCard.tsx
│           ├── plan/    PlanBuilder.tsx, PlanSummary.tsx, AllocationDonut.tsx, CashflowChart.tsx, SavedPlans.tsx, PlanCompare.tsx
│           └── layout/  TwoPane.tsx, StalenessBadge.tsx
```

## 5. Data layer — DuckDB

File DB at `DB_PATH` (default `data/arrived.duckdb`), persisted via a compose volume.

```sql
CREATE TABLE IF NOT EXISTS offerings (
    id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, market VARCHAR NOT NULL,
    property_type VARCHAR NOT NULL CHECK (property_type IN ('single_family','vacation_rental','fund')),
    status VARCHAR NOT NULL DEFAULT 'available' CHECK (status IN ('available','funded','closed')),
    share_price_usd DOUBLE NOT NULL, min_investment_usd DOUBLE NOT NULL,
    projected_dividend_yield DOUBLE NOT NULL,   -- annual decimal, 0.045 = 4.5%
    projected_appreciation DOUBLE NOT NULL,     -- annual decimal
    funded_pct DOUBLE,                          -- display-only (funding progress bar); not used in scoring
    property_value_usd DOUBLE,
    leverage_pct DOUBLE,                        -- used in scoring (§6); NULL treated as 0
    as_of TIMESTAMP NOT NULL                    -- UTC
);
CREATE TABLE IF NOT EXISTS historical_returns (
    offering_id VARCHAR NOT NULL, month VARCHAR NOT NULL,          -- 'YYYY-MM'
    dividend_per_share DOUBLE, share_value_usd DOUBLE,
    PRIMARY KEY (offering_id, month)
);
CREATE TABLE IF NOT EXISTS market_metrics (          -- tall/long enrichment table
    metro VARCHAR NOT NULL, month VARCHAR NOT NULL,  -- canonical slug; 'YYYY-MM'
    source VARCHAR NOT NULL,                         -- 'zillow_zhvi'|'zillow_zori'|'fred'|'census_acs'|'seed'
    metric VARCHAR NOT NULL,                         -- 'home_value_index'|'rent_index'|'unemployment_rate'|'population'|'median_income'
    value DOUBLE NOT NULL, as_of TIMESTAMP NOT NULL,
    PRIMARY KEY (metro, month, source, metric)
);
CREATE TABLE IF NOT EXISTS market_aliases (          -- entity resolution: raw market → canonical metro
    raw_market VARCHAR PRIMARY KEY,                  -- 'Nashville, TN' as it appears in offerings
    metro VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS plans (                   -- immutable snapshots (§9)
    id VARCHAR PRIMARY KEY,                          -- uuid4 hex
    name VARCHAR,
    created_at TIMESTAMP NOT NULL,                   -- UTC
    inputs VARCHAR NOT NULL,                         -- JSON text: {amount, risk_profile, horizon_years, existing_positions}
    output VARCHAR NOT NULL,                         -- JSON text: full engine output at save time
    data_as_of TIMESTAMP NOT NULL                    -- max(as_of) across offerings + market_metrics at save time
);
```

**DuckDB rules**

- R6. DuckDB allows one writer process. The API process is the sole owner of the file: seeding runs in app startup (lifespan) and enrichment refresh runs **inside the API process** (`/api/admin/refresh-market-data`). NEVER a separate concurrent writer container. The `python -m infrastructure.enrichment.refresh` CLI is for use only while the API is stopped.
- R7. `DuckDBConn` is the process's **single** connection, created once in the composition root and shared by `OfferingsRepo` and `PlansRepo`; every operation uses `connection.cursor()` (thread-safe). NEVER open a second `read_write` connection to the same file.
- R8. All writes are keyed upserts (`INSERT ... ON CONFLICT DO UPDATE`) — idempotent, safe to re-run. Exception: `plans` is insert/delete only (R16).
- R9. Explicit column lists everywhere. NEVER `SELECT *` outside ad-hoc debugging.
- R10. Timestamps are UTC (`datetime.now(UTC)`); months are `'YYYY-MM'` strings.
- R11. Every offering→enrichment join goes through `market_aliases` to a canonical metro slug. Each enrichment adapter additionally owns its **per-source region map** (slug → that provider's region key, e.g. Zillow's "Nashville-Davidson--Murfreesboro--Franklin, TN"). NEVER string-match raw market names against provider region names inline.
- Plans JSON is stored as VARCHAR and (de)serialized in `PlansRepo` — avoids depending on the DuckDB JSON extension.

Why DuckDB: enrichment CSVs can be ingested natively (`read_csv` over https via httpfs), and a future scraper can drop Parquet that DuckDB reads directly — zero schema churn.

## 6. Domain — risk strategies and the allocation engine

Money rule: position sizes are **integer USD**, `INCREMENT_USD = 10`, `MIN_POSITION_USD = 100`, `MAX_POSITIONS_PER_MARKET = 2` (funds exempt; their market is `"Diversified"`), `TYPE_SHARE_CAPS = {"vacation_rental": 0.50}` (all other types 1.0).

| Profile | yield_weight | appreciation_weight | market_weight | leverage_weight | max_position_pct | fund_floor_pct |
|---|---|---|---|---|---|---|
| conservative | 0.8 | 0.2 | 0.005 | 0.010 | 0.15 | 0.30 |
| balanced | 0.5 | 0.5 | 0.010 | 0.005 | 0.25 | 0.15 |
| aggressive | 0.3 | 0.7 | 0.020 | 0.000 | 0.35 | 0.00 |

`AllocationEngine().build(amount_usd, strategy, horizon_years, *, offerings, momentum_by_market=None, existing_positions=None)` — deterministic, ties broken by offering id. `existing_positions: dict[offering_id, float] | None` is money already invested.

1. Validate: floor budget to increment (`usable`); infeasible if `usable < MIN_POSITION_USD`, horizon outside 1–30, no available offerings, or any `existing_positions` id not present in `offerings` (reason MUST name the unknown ids).
2. Score every available offering: `yield_weight·dividend_yield + appreciation_weight·appreciation + market_weight·(momentum − 0.5) − leverage_weight·leverage_pct` (missing momentum → neutral 0.5; missing leverage → 0). Sort descending, tie-break by id ascending. Record the four components per offering.
3. `portfolio_base = usable + Σ existing_positions.values()`. Per-offering total-exposure cap `= max(MIN_POSITION_USD, floor_to_increment(portfolio_base · max_position_pct))`; new money room for an offering `= cap − existing.get(id, 0)` (floored at 0). Type-share caps apply to `(existing + new)` of that type vs `portfolio_base`.
4. Fund floor: target `= min(max(MIN_POSITION_USD, floor(portfolio_base · fund_floor_pct)), cap)`. If existing fund exposure already ≥ target, skip; else allocate the shortfall (subject to room and MIN) to the best-scored fund.
5. Greedy fill down the ranking: `take = min(room, type_room, remaining)`; skip if `take < MIN_POSITION_USD` **unless** the offering is already held (top-ups below MIN are allowed in increments). Market cap counts **distinct** positions (existing ∪ new) per market — topping up a held offering never counts as a new position; new distinct offerings in a saturated market are skipped.
6. Top-up pass: distribute leftover in $10 increments to allocated-or-held positions with room, best-scored first.
7. Remainder is `unallocated_cash_usd` — NEVER silently dropped, NEVER over-invested. Invariant: `total_invested + unallocated == requested` (±$0.01), where `total_invested` counts **new money only**.

Output (JSON-serializable dict): `feasible`, `risk_profile`, `horizon_years`, `positions[]` — new-money allocations only — (offering_id, name, market, property_type, amount_usd, weight_pct of new money, projected_dividend_yield, projected_appreciation, est_annual_dividend_usd, `score_breakdown` = {"yield","appreciation","momentum","leverage","total"} rounded to 6 dp), `summary` (requested_usd, total_invested_usd, unallocated_cash_usd, existing_portfolio_usd, portfolio_total_usd, position_count, blended_dividend_yield, projected_annual_dividends_usd, projected_value_at_horizon_usd = Σ amt·(1+appr)^h over new money, projected_cumulative_dividends_usd = annual·h, projected_total_at_horizon_usd), `assumptions[]` (MUST note market-signal usage, the leverage penalty, type caps, and whether existing holdings were considered), `disclaimer`.

- R12. Invalid input MUST return `{"feasible": false, "reason": "..."}` — not raise — so the agent relays it conversationally. Unknown risk-profile names are checked in `PlanService`.
- R13. `score_breakdown` MUST be emitted for every position; it is the agent's only sanctioned way to explain rankings.

## 7. Domain — market enrichment math (`domain/market.py`, pure)

- `yoy(series) -> float | None`: latest month vs 12 back for the same metric; None if either missing. When both a live source and `seed` provide a metric, PREFER the live source.
- `norm(x, lo, hi) = clamp((x − lo) / (hi − lo), 0, 1)`; `momentum(hv_yoy, rent_yoy)`: mean of `norm(v, −0.05, 0.10)` over whichever is present; `0.5` if neither.
- `MarketContext`: metro, home_value_yoy, rent_yoy, unemployment_rate, population, median_income, momentum — built by `MarketService`; `PlanService` builds `momentum_by_market` for all offering markets the same way.
- R14. Momentum MUST be a bounded *tilt*, never a gate: ≤ `market_weight` of score, and offerings are never excluded for missing market data.

## 8. Agent — tools

`ToolDispatcher` owns the Anthropic tool JSON schemas (`.definitions`) and `.dispatch(name, args) -> dict` (raises `KeyError` on unknown tool).

| Tool | Purpose | Params (\*required) | SSE result event |
|---|---|---|---|
| `get_offerings` | filtered list | market, property_type, min_dividend_yield, limit | `offerings_result` |
| `get_offering_details` | one offering + 12 mo history | offering_id\* | `offering_details_result` |
| `get_historical_returns` | monthly dividend/value series | offering_id\*, months (1–60) | `returns_result` |
| `get_market_context` | enrichment view of one market | market\* (raw name) | `market_context_result` |
| `build_investment_plan` | run the engine (momentum applied automatically) | amount\*, risk_profile, horizon_years, existing_positions [{offering_id, amount_usd}] | `plan_result` |
| `save_plan` | re-run engine and persist an immutable snapshot | amount\*, risk_profile, horizon_years, existing_positions, name | `plan_saved_result` |
| `list_saved_plans` | summaries of saved snapshots | — | `saved_plans_result` |

System prompt MUST instruct: all data and math via tools — never invent offerings, market statistics, or allocations (always call `build_investment_plan`); use `score_breakdown` when asked *why* something is ranked where it is, and `get_market_context` for market questions/comparisons; ask for the amount if missing; if the user implies current holdings, ask for them and pass `existing_positions`; default risk to balanced and say so; after presenting a plan, offer to save it (use `save_plan` only on user confirmation); the UI renders tool results as components, so summarize rather than restate rows; briefly state that projections are hypothetical, not financial advice; offerings are seeded demo data while market metrics may mix seeded and live sources — say so if asked about freshness.

## 9. HTTP + SSE contract

REST (all under `/api`):

- `GET /api/health` · `GET /api/offerings` (filters: market, property_type, min_dividend_yield, limit) · `GET /api/offerings/{id}` (404 if missing) · `POST /api/plan {amount, risk_profile, horizon_years, existing_positions?}`.
- Saved plans: `POST /api/plans` (same body + optional `name`; server re-runs the engine and stores the snapshot; 201 with the record) · `GET /api/plans` (summaries, newest first) · `GET /api/plans/{id}` (full record; 404) · `DELETE /api/plans/{id}` (204). R16. Snapshots are immutable: no update endpoint; `data_as_of = max(as_of)` across offerings and market_metrics at save time; a later enrichment refresh MUST NOT change a saved plan.
- `GET /api/meta` → `{"offerings": {"rows": n, "latest_as_of": ts}, "historical_returns": {...}, "market_metrics": {...}, "plans": {"rows": n}}` — powers the `StalenessBadge` ("data as of …").
- `POST /api/admin/refresh-market-data` → per-source `{status: upserted|skipped_no_key|error, rows}` (no auth — deliberate gap, §16).

`POST /api/chat {"messages":[{"role":"user"|"assistant","content":"..."}]}` → `text/event-stream`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`. 503 with a clear message if `ANTHROPIC_API_KEY` is unset. Stateless: the client sends the full visible transcript; R17. the server MUST truncate to the most recent `MAX_HISTORY_MESSAGES` (default 40) before the first model call. Loop: stream turn → if `stop_reason == "tool_use"`, run each tool via `asyncio.to_thread`, emit its typed event, append `tool_result` blocks (`is_error` on failure), repeat; cap `MAX_AGENT_TURNS = 8` → `done {stop_reason:"max_turns"}`.

```
event: text_delta      data: {"text": "..."}
event: tool_started    data: {"tool": "...", "id": "toolu_..."}     # at content_block_start
event: offerings_result | offering_details_result | returns_result |
       market_context_result | plan_result | plan_saved_result | saved_plans_result
                       data: {"tool": "...", "input": {...}, "result": {...}}
event: tool_error      data: {"tool": "...", "error": "..."}
event: done            data: {"stop_reason": "end_turn"|"max_tokens"|"max_turns"}
event: error           data: {"message": "..."}                     # terminal
```

- R18. The typed `*_result` events are the product: the frontend renders them as components — the model is told not to restate tables in prose.
- R19. Frontend MUST consume SSE with `fetch` + `ReadableStream` through `createSseDecoder` (Appendix A pins its contract, including events split across chunk boundaries). `EventSource` is GET-only and CANNOT be used.

## 10. Seed data and enrichment sources

**Windows are relative to today** (UTC at seed time): offering returns cover the 12 most recent *complete* months; seeded market metrics cover the 24 most recent complete months. NEVER hard-code absolute month ranges.

**Offerings** (deterministic, RNG seed 42; all `share_price_usd 10.0`, `min_investment_usd 100`; monthly dividends = price·yield/12 ±15% noise, values drift at appreciation/12 ±0.2%):

| id | name | market | type | yield | appr | leverage |
|---|---|---|---|---|---|---|
| sfr-meridian | The Meridian | Nashville, TN | single_family | 0.041 | 0.042 | 0.55 |
| sfr-cedarbrook | The Cedarbrook | Chattanooga, TN | single_family | 0.048 | 0.035 | 0.60 |
| sfr-saguaro | The Saguaro | Tucson, AZ | single_family | 0.052 | 0.028 | 0.62 |
| sfr-fairview | The Fairview | Fayetteville, AR | single_family | 0.055 | 0.025 | 0.58 |
| sfr-larkspur | The Larkspur | Colorado Springs, CO | single_family | 0.037 | 0.045 | 0.50 |
| sfr-juniper | The Juniper | Boise, ID | single_family | 0.039 | 0.044 | 0.52 |
| vac-roadrunner | The Roadrunner | Joshua Tree, CA | vacation_rental | 0.061 | 0.030 | 0.45 |
| vac-summit | The Summit Chalet | Gatlinburg, TN | vacation_rental | 0.067 | 0.028 | 0.48 |
| vac-driftwood | The Driftwood | Gulf Shores, AL | vacation_rental | 0.058 | 0.033 | 0.40 |
| fund-sfr | Single Family Residential Fund | Diversified | fund | 0.042 | 0.031 | 0.35 |
| fund-credit | Private Credit Fund | Diversified | fund | 0.081 | 0.000 | 0.00 |

**Market aliases**: one row per market above (except "Diversified"), mapping to slugs like `nashville-tn`.

**Seeded market metrics** (`source='seed'`): per metro, `home_value_index` and `rent_index` starting at 100.0, growing monthly at the market's offering appreciation (hv) and appreciation + 0.5pp (rent) with ±0.1% RNG-42 noise — so YoY and momentum compute offline and deterministically.

**Live sources** (Adapters implementing `MarketDataSource`; all upsert into `market_metrics`; each owns its region map per R11):

- `zillow.py` — Zillow Research public CSVs (ZHVI + ZORI, metro-level; no key; URLs env-overridable). Filter to mapped metros. PREFER DuckDB `read_csv` via httpfs; httpx + csv acceptable. Attribute "Data: Zillow Research" in the UI footer.
- `fred.py` — FRED metro unemployment (`FRED_API_KEY`; status `skipped_no_key` when absent).
- `census.py` — Census ACS 5-year population + median household income (key optional; skip on missing/failed).

R20. Enrichment failures MUST be isolated per source: one provider failing returns `{status:"error"}` for it and MUST NOT abort the others or crash the app.
R21. The app MUST be fully functional offline using seed data alone — live enrichment only improves it.

## 11. Docker, compose, CI

- Backend Dockerfile: multi-stage (deps build → slim `python:3.12-slim` runtime), non-root user, `.dockerignore`, `HEALTHCHECK` on `/api/health`, CMD uvicorn on 8000.
- Frontend Dockerfile: `node:22-alpine` build → `nginx:alpine` serving `dist/`; nginx proxies `/api/` → `http://api:8000/api/`.
- `docker-compose.yml`: `api` (port 8000, `env_file: backend/.env`, named volume `duckdb_data:/app/data`) and `web` (5173→80, `depends_on: api: condition: service_healthy`).
- Local non-Docker dev: uvicorn on 8000 + vite on 5173 with `VITE_API_URL=http://localhost:8000/api`, CORS allowing `http://localhost:5173`.
- CI (`.github/workflows/ci.yml`), required green: backend job (ruff, mypy, pytest), frontend job (`tsc --noEmit`, vitest, `vite build`), docker job (build both images). R22. CI MUST run offline (no keys, no network beyond package installs).
- R23. Secrets NEVER in code, images, Dockerfiles, or compose — env only. `.env` gitignored; `.env.example` committed and complete.
- R24. Pin base images by major tag; commit a dependency lockfile.

## 12. Testing (pytest `asyncio_mode = auto`; vitest)

- **Appendix A files are canonical**: `tests/conftest.py`, `tests/domain/test_planner.py`, `tests/services/test_agent_service.py`, `frontend/src/api/sse.test.ts`. Copy verbatim; they pin constructor signatures, the engine's behavior, and both ends of the SSE contract. Build until green.
- Behavioral suites to implement: `tests/domain/test_market.py` (yoy/norm/momentum incl. missing-data neutrality); `tests/services/test_tools.py` (every tool dispatches against a seeded tmp DB, results `json.dumps`-able, unknown tool raises); `tests/infrastructure/test_repos.py` (upsert idempotency — run twice, same counts; alias join; plans save/list/get/delete; snapshot immutability: save plan → upsert new metrics → stored output unchanged); `tests/api/test_api.py` (offerings list/filter/404; `/api/plan` happy + 422; plans CRUD; `/api/meta` shape; `/api/chat` 503 without key; history truncation observed by a fake LLM; admin refresh with sources mocked/skipped).
- R25. Tests NEVER touch the network; enrichment adapters use mocked transports or skipped-by-key paths. Fixtures point the repo at a tmp file.

## 13. Configuration

| Var | Default | Notes |
|---|---|---|
| ANTHROPIC_API_KEY | — | required for /api/chat only |
| ANTHROPIC_MODEL / MAX_TOKENS / MAX_AGENT_TURNS | claude-sonnet-4-6 / 4096 / 8 | |
| MAX_HISTORY_MESSAGES | 40 | server-side truncation (R17) |
| DB_PATH | data/arrived.duckdb | volume-mounted in compose |
| CORS_ORIGINS | http://localhost:5173 | comma-separated; dev only |
| FRED_API_KEY / CENSUS_API_KEY | — | optional; sources skip cleanly when absent |
| ZILLOW_ZHVI_URL / ZILLOW_ZORI_URL | research CSV defaults | overridable for pinning/testing |
| VITE_API_URL | /api | `http://localhost:8000/api` in local dev |

## 14. Code standards

- R26. Python: type hints on all public functions; `from __future__ import annotations`; ruff + mypy configured in `pyproject.toml` and clean.
- R27. Structured logging via stdlib `logging` (key=value). NEVER `print` in `src/`.
- R28. Fail loud: no swallowed exceptions. Tool failures → `tool_error` + `is_error` result; per-source enrichment failures → per-source status; unexpected stream failures → terminal `error` event.
- R29. TypeScript strict; NEVER `any` in `src/`; SSE events are a discriminated union, exhaustively switched.
- R30. Accessibility/responsive: the streaming assistant message region uses `aria-live="polite"`; below the `md` breakpoint the two-pane layout stacks with the data panel reachable beneath the chat.
- R31. Docstrings on every module and public class/function stating its single responsibility.
- PREFER small pure functions and composition over inheritance; comments explain *why*, not *what*.

## 15. Build order and acceptance criteria

Copy Appendix A tests first, then build in order, keeping tests green: (1) domain models + risk + engine + market math → (2) DuckDB conn/repos + seeder → (3) services + dispatcher → (4) agent loop + API routes (incl. plans, meta) → (5) enrichment adapters + admin refresh → (6) frontend types + SSE decoder + client → (7) chat UI + explorer + plan/saved/compare views → (8) Docker/compose/nginx/CI → (9) end-to-end pass.

**Done means:**

- [ ] `docker compose up --build` → web on :5173, api healthy on :8000, DuckDB persisted — fully working offline (R21)
- [ ] `GET /api/offerings` returns 11 seeded offerings with a fresh (relative) data window; filters work; unknown id → 404
- [ ] `POST /api/plan` is deterministic, honors every §6 invariant, and returns `score_breakdown` per position
- [ ] Plans with `existing_positions` respect total-exposure caps, market saturation, type shares, and the fund floor
- [ ] Chat: "Compare Nashville vs Tucson, then invest $2,000 balanced" → market cards + rendered plan; "save it" → `plan_saved_result` and it appears in Saved Plans; compare view renders two snapshots side by side
- [ ] `GET /api/meta` powers a visible "data as of …" badge; saved snapshots survive an enrichment refresh unchanged
- [ ] Plan responses and agent replies include the not-financial-advice disclaimer
- [ ] All tests pass offline, Appendix A verbatim; ruff + mypy + `tsc --noEmit` clean; CI workflow present and green; every source file ≤ 200 lines
- [ ] No secrets anywhere but env; `.env.example` documents every variable

## 16. Deferred to a later iteration — do NOT build now

Fee modeling (one-time sourcing % + annual AUM bps haircut on projections) · DCA/recurring contributions · `ingest_runs` provenance table for enrichment · in-process nightly auto-refresh scheduler · Hypothesis property-based tests on engine invariants · `/api/admin/export` Parquet snapshots · auth on admin routes.

## 17. Out of scope permanently

Live scraping of arrived.com · multi-user accounts · MCP server (the dispatcher is designed so a FastMCP wrapper drops in later) · paid data providers (ATTOM, AirDNA, ClimateCheck) · property-level enrichment (flood/crime per address) · payments/brokerage of any kind.

---

## Appendix A — canonical test files (copy verbatim)

### `backend/tests/conftest.py`

```python
from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.duckdb.connection import DuckDBConn
from infrastructure.duckdb.offerings_repo import OfferingsRepo
from infrastructure.duckdb.plans_repo import PlansRepo
from infrastructure.seed import seed_all


@pytest.fixture()
def conn(tmp_path: Path) -> DuckDBConn:
    """One connection per test, per R7. Tests never touch the network."""
    return DuckDBConn(tmp_path / "test.duckdb")


@pytest.fixture()
def repo(conn: DuckDBConn) -> OfferingsRepo:
    r = OfferingsRepo(conn)
    seed_all(r)
    return r


@pytest.fixture()
def plans(conn: DuckDBConn) -> PlansRepo:
    return PlansRepo(conn)
```

### `backend/tests/domain/test_planner.py`

```python
from __future__ import annotations

from typing import Any

import pytest

from domain.planner import INCREMENT_USD, MIN_POSITION_USD, AllocationEngine
from domain.risk import RISK_STRATEGIES

BREAKDOWN_KEYS = {"yield", "appreciation", "momentum", "leverage", "total"}


def _offering(oid: str, market: str, ptype: str = "single_family", dy: float = 0.05,
              appr: float = 0.03, leverage: float | None = None) -> dict[str, Any]:
    return {"id": oid, "name": oid.title(), "market": market, "property_type": ptype,
            "status": "available", "projected_dividend_yield": dy,
            "projected_appreciation": appr, "leverage_pct": leverage}


@pytest.fixture()
def offerings() -> list[dict[str, Any]]:
    return [
        _offering("a1", "Nashville, TN", dy=0.050, appr=0.030),
        _offering("a2", "Nashville, TN", dy=0.048, appr=0.032),
        _offering("a3", "Nashville, TN", dy=0.046, appr=0.031),
        _offering("b1", "Tucson, AZ", dy=0.055, appr=0.025),
        _offering("c1", "Boise, ID", dy=0.038, appr=0.045),
        _offering("f1", "Diversified", ptype="fund", dy=0.042, appr=0.031),
        _offering("f2", "Diversified", ptype="fund", dy=0.081, appr=0.000),
    ]


ENGINE = AllocationEngine()
BAL = RISK_STRATEGIES["balanced"]


@pytest.mark.parametrize("profile", sorted(RISK_STRATEGIES))
@pytest.mark.parametrize("amount", [100, 250, 1_000, 5_000, 12_345.67])
def test_budget_conservation_increments_breakdown(offerings, profile: str, amount: float) -> None:
    plan = ENGINE.build(amount, RISK_STRATEGIES[profile], 5, offerings=offerings)
    assert plan["feasible"], plan
    s = plan["summary"]
    assert s["total_invested_usd"] + s["unallocated_cash_usd"] == pytest.approx(amount, abs=0.01)
    for pos in plan["positions"]:
        assert pos["amount_usd"] >= MIN_POSITION_USD
        assert pos["amount_usd"] % INCREMENT_USD == 0
        assert set(pos["score_breakdown"]) == BREAKDOWN_KEYS


def test_position_cap_and_market_diversification(offerings) -> None:
    for name, strategy in RISK_STRATEGIES.items():
        plan = ENGINE.build(10_000, strategy, 5, offerings=offerings)
        cap = max(MIN_POSITION_USD, int(10_000 * strategy.max_position_pct))
        assert all(p["amount_usd"] <= cap for p in plan["positions"]), name
        nash = [p for p in plan["positions"]
                if p["market"] == "Nashville, TN" and p["property_type"] != "fund"]
        assert len(nash) <= 2


def test_conservative_fund_floor_bounded_by_cap(offerings) -> None:
    plan = ENGINE.build(1_000, RISK_STRATEGIES["conservative"], 5, offerings=offerings)
    funds = [p for p in plan["positions"] if p["property_type"] == "fund"]
    assert funds and funds[0]["amount_usd"] == 150  # min(30% floor, 15% cap) of 1000


def test_vacation_rental_type_share_cap() -> None:
    vacs = [_offering(f"v{i}", f"V{i}, XX", ptype="vacation_rental", dy=0.09, appr=0.05)
            for i in range(4)]
    sfrs = [_offering(f"s{i}", f"S{i}, YY", dy=0.030, appr=0.020) for i in range(4)]
    plan = ENGINE.build(1_000, BAL, 5, offerings=vacs + sfrs)
    vac_total = sum(p["amount_usd"] for p in plan["positions"]
                    if p["property_type"] == "vacation_rental")
    assert vac_total <= 500  # TYPE_SHARE_CAPS['vacation_rental'] = 0.50 of usable


def test_leverage_penalty_tilts_ranking() -> None:
    twins = [_offering("hi-lev", "A, XX", leverage=0.70),
             _offering("no-lev", "B, YY", leverage=0.00)]
    plan = ENGINE.build(300, RISK_STRATEGIES["conservative"], 5, offerings=twins)
    assert plan["positions"][0]["offering_id"] == "no-lev"


def test_momentum_tilts_ranking_deterministically() -> None:
    twins = [_offering("m1", "Boise, ID"), _offering("m2", "Tucson, AZ")]
    hot = ENGINE.build(300, BAL, 5, offerings=twins,
                       momentum_by_market={"Boise, ID": 1.0, "Tucson, AZ": 0.0})
    assert hot["positions"][0]["offering_id"] == "m1"
    neutral = ENGINE.build(300, BAL, 5, offerings=twins)
    assert neutral["positions"][0]["offering_id"] == "m1"  # tie → id order


def test_existing_positions_respect_caps_and_markets(offerings) -> None:
    held_at_cap = {"b1": 2_500}  # cap = 25% of (7_500 + 2_500)
    plan = ENGINE.build(7_500, BAL, 5, offerings=offerings, existing_positions=held_at_cap)
    assert plan["feasible"]
    assert all(p["offering_id"] != "b1" for p in plan["positions"])
    assert plan["summary"]["existing_portfolio_usd"] == 2_500
    assert plan["summary"]["portfolio_total_usd"] == pytest.approx(
        2_500 + plan["summary"]["total_invested_usd"])

    two_nash = {"a1": 300.0, "a2": 300.0}  # market saturated by held positions
    plan2 = ENGINE.build(2_000, BAL, 5, offerings=offerings, existing_positions=two_nash)
    new_ids = {p["offering_id"] for p in plan2["positions"]}
    assert "a3" not in new_ids  # top-ups of a1/a2 allowed; new Nashville names are not


def test_unknown_existing_id_is_infeasible(offerings) -> None:
    plan = ENGINE.build(1_000, BAL, 5, offerings=offerings,
                        existing_positions={"ghost": 100.0})
    assert plan["feasible"] is False and "ghost" in plan["reason"]


def test_determinism(offerings) -> None:
    a = ENGINE.build(3_210, BAL, 7, offerings=offerings)
    b = ENGINE.build(3_210, BAL, 7, offerings=offerings)
    assert a == b


@pytest.mark.parametrize("amount,horizon,offs", [(60, 5, None), (1_000, 0, None), (1_000, 5, [])])
def test_infeasible_inputs_return_reason(offerings, amount, horizon, offs) -> None:
    plan = ENGINE.build(amount, BAL, horizon,
                        offerings=offerings if offs is None else offs)
    assert plan["feasible"] is False and plan["reason"]
```

### `backend/tests/services/test_agent_service.py`

```python
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from services.agent_service import AgentService
from services.market_service import MarketService
from services.plan_service import PlanService
from services.tools import ToolDispatcher


class _FakeStream:
    def __init__(self, events: list[Any], final: Any) -> None:
        self._events, self._final = events, final
    async def __aenter__(self): return self
    async def __aexit__(self, *exc: Any) -> bool: return False
    def __aiter__(self):
        self._it = iter(self._events); return self
    async def __anext__(self):
        try: return next(self._it)
        except StopIteration as e: raise StopAsyncIteration from e
    async def get_final_message(self): return self._final


class FakeLLM:
    """Scripted LLMClient; records kwargs of every call."""
    def __init__(self, turns: list[tuple[list[Any], Any]]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []
    def stream(self, **kwargs: Any) -> _FakeStream:
        self.calls.append(kwargs)
        events, final = self._turns.pop(0)
        return _FakeStream(events, final)


def _parse(chunks: list[str]) -> list[tuple[str, dict[str, Any]]]:
    out = []
    for c in chunks:
        lines = c.strip().split("\n")
        out.append((lines[0].removeprefix("event: "),
                    json.loads(lines[1].removeprefix("data: "))))
    return out


def _service(repo, plans, llm: FakeLLM) -> AgentService:
    plan_service = PlanService(repo, plans)
    dispatcher = ToolDispatcher(repo, plan_service, MarketService(repo))
    return AgentService(llm=llm, tools=dispatcher)


@pytest.fixture()
def scripted(repo, plans) -> tuple[AgentService, FakeLLM]:
    tool_block = SimpleNamespace(type="tool_use", name="build_investment_plan",
                                 id="toolu_1", input={"amount": 1000})
    turn1 = ([SimpleNamespace(type="content_block_start", content_block=tool_block)],
             SimpleNamespace(stop_reason="tool_use", content=[tool_block]))
    turn2 = ([SimpleNamespace(type="content_block_delta",
                              delta=SimpleNamespace(type="text_delta", text="Done."))],
             SimpleNamespace(stop_reason="end_turn", content=[]))
    llm = FakeLLM([turn1, turn2])
    return _service(repo, plans, llm), llm


async def test_event_sequence_and_tool_feedback(scripted) -> None:
    agent, llm = scripted
    chunks = [c async for c in agent.run([{"role": "user", "content": "Invest $1000"}])]
    events = _parse(chunks)
    assert [e for e, _ in events] == ["tool_started", "plan_result", "text_delta", "done"]
    plan = dict(events)["plan_result"]
    assert plan["tool"] == "build_investment_plan"
    assert plan["result"]["feasible"] is True
    assert plan["result"]["summary"]["total_invested_usd"] <= 1000
    assert dict(events)["done"] == {"stop_reason": "end_turn"}
    followup = llm.calls[1]["messages"][-1]
    assert followup["role"] == "user"
    assert followup["content"][0]["type"] == "tool_result"
    assert followup["content"][0]["tool_use_id"] == "toolu_1"


async def test_history_is_truncated_server_side(repo, plans) -> None:
    llm = FakeLLM([([], SimpleNamespace(stop_reason="end_turn", content=[]))])
    agent = _service(repo, plans, llm)
    history = [{"role": "user", "content": f"m{i}"} for i in range(120)]
    _ = [c async for c in agent.run(history)]
    sent = llm.calls[0]["messages"]
    assert len(sent) <= 40                      # MAX_HISTORY_MESSAGES default
    assert sent[-1]["content"] == "m119"        # most recent kept
```

### `frontend/src/api/sse.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { createSseDecoder } from "./sse";

describe("createSseDecoder", () => {
  it("reassembles events split across chunk boundaries", () => {
    const events: unknown[] = [];
    const feed = createSseDecoder((e) => events.push(e));
    feed("event: text_delta\nda");
    feed('ta: {"text":"he');
    feed('llo"}\n\nevent: done\ndata: {"stop_reason":"end_turn"}\n\n');
    expect(events).toEqual([
      { type: "text_delta", text: "hello" },
      { type: "done", stop_reason: "end_turn" },
    ]);
  });

  it("handles multiple events per chunk and ignores comment keep-alives", () => {
    const events: unknown[] = [];
    const feed = createSseDecoder((e) => events.push(e));
    feed(':ka\n\nevent: tool_started\ndata: {"tool":"get_offerings","id":"t1"}\n\n' +
         'event: error\ndata: {"message":"boom"}\n\n');
    expect(events).toEqual([
      { type: "tool_started", tool: "get_offerings", id: "t1" },
      { type: "error", message: "boom" },
    ]);
  });
});
```
