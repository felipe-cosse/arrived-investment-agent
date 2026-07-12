/** Typed REST client for the /api endpoints: offerings, plan, plans CRUD, meta,
 * admin refresh (§4). The chat SSE stream lives in `sse.ts`.
 */

import type {
  Meta,
  Offering,
  Plan,
  PlanRecord,
  RefreshReport,
  RegionInfo,
  ReturnRecord,
  SavedPlanSummary,
} from "../types/domain";

/** Base URL: nginx proxies `/api` in Docker; local dev overrides via env (§13). */
export const API_URL: string = import.meta.env.VITE_API_URL ?? "/api";

/** GET /api/offerings query filters (§9). */
export interface OfferingFilters {
  market?: string;
  property_type?: string;
  min_dividend_yield?: number;
  limit?: number;
}

export interface OfferingsResponse {
  count: number;
  offerings: Offering[];
}

export interface OfferingDetails {
  offering: Offering;
  history: ReturnRecord[];
}

/** One already-held position, in the shape POST /api/plan accepts. */
export interface ExistingPositionInput {
  offering_id: string;
  amount_usd: number;
}

/** POST /api/plan body (§9). */
export interface PlanRequest {
  amount: number;
  risk_profile?: string;
  horizon_years?: number;
  existing_positions?: ExistingPositionInput[];
}

/** Non-2xx API response, carrying the HTTP status and the server's detail. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/** Absolute URL for an API path — shared with the SSE reader in `sse.ts`. */
export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

/** Human-readable message for any thrown value (fetch rejections are unknown). */
export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

/** Extract FastAPI's `{"detail": ...}` from an error response, if present. */
export async function responseDetail(response: Response): Promise<string> {
  const fallback = `HTTP ${response.status} ${response.statusText}`.trim();
  try {
    const body = (await response.json()) as { detail?: unknown };
    return typeof body.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) throw new ApiError(response.status, await responseDetail(response));
  return (await response.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

/** Filtered offering list. */
export function fetchOfferings(filters: OfferingFilters = {}): Promise<OfferingsResponse> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined) params.set(key, String(value));
  }
  const query = params.toString();
  return request(`/offerings${query ? `?${query}` : ""}`);
}

/** One offering plus its recent monthly history; 404 → ApiError. */
export function fetchOffering(id: string): Promise<OfferingDetails> {
  return request(`/offerings/${encodeURIComponent(id)}`);
}

/** Stored Zillow/FRED/Census observations for an offering's mapped metro area. */
export function fetchRegionInfo(id: string): Promise<RegionInfo> {
  return request(`/offerings/${encodeURIComponent(id)}/region-info`);
}

/** Run the deterministic planner; infeasible inputs return a Plan, not an error (R12). */
export function buildPlan(body: PlanRequest): Promise<Plan> {
  return request("/plan", jsonInit("POST", body));
}

/** Re-run the engine and persist an immutable snapshot (R16); 201 with the record. */
export function savePlan(body: PlanRequest & { name?: string }): Promise<PlanRecord> {
  return request("/plans", jsonInit("POST", body));
}

/** Saved-snapshot summaries, newest first. */
export function fetchPlans(): Promise<{ plans: SavedPlanSummary[] }> {
  return request("/plans");
}

/** One full snapshot by id; 404 → ApiError. */
export function fetchPlan(id: string): Promise<PlanRecord> {
  return request(`/plans/${encodeURIComponent(id)}`);
}

/** Delete a snapshot; resolves on 204, throws ApiError otherwise. */
export async function deletePlan(id: string): Promise<void> {
  const response = await fetch(apiUrl(`/plans/${encodeURIComponent(id)}`), { method: "DELETE" });
  if (!response.ok) throw new ApiError(response.status, await responseDetail(response));
}

/** Row counts and data freshness for the StalenessBadge (§9). */
export function fetchMeta(): Promise<Meta> {
  return request("/meta");
}

/** Run the enrichment sources inside the API process; per-source status (R20). */
export function refreshMarketData(): Promise<RefreshReport> {
  return request("/admin/refresh-market-data", { method: "POST" });
}

/** POST /api/admin/refresh-offerings success report: rows written per table. */
export interface OfferingsUpsertedReport {
  status: "upserted";
  offerings: number;
  returns: number;
  aliases: number;
  seeds_purged: number;
  share_price_failures: number;
  detail_failures: number;
}

/** POST /api/admin/refresh-offerings failure report (HTTP 200; `status` carries it). */
export interface OfferingsRefreshErrorReport {
  status: "error";
  detail: string;
}

/** Refresh-offerings run report, discriminated on `status`. */
export type OfferingsRefreshReport = OfferingsUpsertedReport | OfferingsRefreshErrorReport;

/** Pull buyable offerings from Arrived's public catalogue (manual trigger). */
export function refreshOfferings(): Promise<OfferingsRefreshReport> {
  return request("/admin/refresh-offerings", { method: "POST" });
}
