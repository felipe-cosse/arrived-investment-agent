/** Domain types mirroring the backend pydantic models and API payloads (§4).
 *
 * Field names and optionality match `backend/src/domain/models.py` and the §6/§9
 * JSON contracts exactly; timestamps arrive as ISO-8601 strings, months as
 * 'YYYY-MM' strings.
 */

export type PropertyType = "single_family" | "vacation_rental" | "fund";
export type OfferingStatus = "available" | "funded" | "closed";
export type RiskProfile = "conservative" | "balanced" | "aggressive";

/** One fractional real-estate offering as listed in the explorer. */
export interface Offering {
  id: string;
  name: string;
  market: string;
  property_type: PropertyType;
  status: OfferingStatus;
  share_price_usd: number;
  min_investment_usd: number;
  projected_dividend_yield: number;
  projected_appreciation: number;
  funded_pct: number | null;
  property_value_usd: number | null;
  leverage_pct: number | null;
  as_of: string;
}

/** One month of dividend and share-value history for an offering. */
export interface ReturnRecord {
  offering_id: string;
  month: string;
  dividend_per_share: number | null;
  share_value_usd: number | null;
}

/** Enrichment snapshot of one metro (§7); momentum is neutral 0.5 without data. */
export interface MarketContext {
  metro: string;
  home_value_yoy: number | null;
  rent_yoy: number | null;
  unemployment_rate: number | null;
  population: number | null;
  median_income: number | null;
  momentum: number;
}

/** Per-position score components — the sanctioned way to explain rankings (R13). */
export interface ScoreBreakdown {
  yield: number;
  appreciation: number;
  momentum: number;
  leverage: number;
  total: number;
}

/** One new-money allocation inside a plan (§6 output). */
export interface Position {
  offering_id: string;
  name: string;
  market: string;
  property_type: PropertyType;
  amount_usd: number;
  weight_pct: number;
  projected_dividend_yield: number;
  projected_appreciation: number;
  est_annual_dividend_usd: number;
  score_breakdown: ScoreBreakdown;
}

/** The §6 summary block: budget conservation and horizon projections. */
export interface PlanSummary {
  requested_usd: number;
  total_invested_usd: number;
  unallocated_cash_usd: number;
  existing_portfolio_usd: number;
  portfolio_total_usd: number;
  position_count: number;
  blended_dividend_yield: number;
  projected_annual_dividends_usd: number;
  projected_value_at_horizon_usd: number;
  projected_cumulative_dividends_usd: number;
  projected_total_at_horizon_usd: number;
}

/** A feasible engine result: positions, summary, assumptions, disclaimer (§6). */
export interface FeasiblePlan {
  feasible: true;
  risk_profile: string;
  horizon_years: number;
  positions: Position[];
  summary: PlanSummary;
  assumptions: string[];
  disclaimer: string;
}

/** Invalid input comes back as a reason, never an exception (R12). */
export interface InfeasiblePlan {
  feasible: false;
  reason: string;
}

export type Plan = FeasiblePlan | InfeasiblePlan;

/** The inputs half of a saved snapshot: what the engine was asked to do. */
export interface PlanInputs {
  amount: number;
  risk_profile: string;
  horizon_years: number;
  existing_positions: Record<string, number>;
}

/** Immutable saved-plan snapshot: inputs + full output + data freshness (R16). */
export interface PlanRecord {
  id: string;
  name: string | null;
  created_at: string;
  inputs: PlanInputs;
  output: Plan;
  data_as_of: string;
}

/** GET /api/plans row: everything in the record except the full output. */
export interface SavedPlanSummary {
  id: string;
  name: string | null;
  created_at: string;
  inputs: PlanInputs;
  data_as_of: string;
}

/** GET /api/meta: row counts and freshness powering the StalenessBadge (§9). */
export interface Meta {
  offerings: { rows: number; latest_as_of: string | null };
  historical_returns: { rows: number; latest_month: string | null };
  market_metrics: { rows: number; latest_as_of: string | null };
  plans: { rows: number };
}

/** POST /api/admin/refresh-market-data: one §9 status entry per source (R20). */
export interface SourceRefreshStatus {
  status: "upserted" | "skipped_no_key" | "error";
  rows: number;
}

export type RefreshReport = Record<string, SourceRefreshStatus>;
