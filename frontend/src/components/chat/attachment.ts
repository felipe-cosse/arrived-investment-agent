/** Pure plan-attachment formatting: a saved snapshot becomes a delimited
 * `[ATTACHED PLAN: …]` context block prepended to the wire message, so the
 * agent can answer ranking/why questions and build modified plans from it.
 * No API changes — client-side context injection only (design 2026-07-09).
 */

import type { Plan, PlanRecord, PlanSummary, Position, ScoreBreakdown } from "../../types/domain";

/** Chip metadata for an attached plan, stored on the chat message. */
export interface PlanAttachment {
  id: string;
  name: string;
}

/** Attachment metadata for a record; the display name falls back to the id. */
export function toPlanAttachment(record: PlanRecord): PlanAttachment {
  return { id: record.id, name: record.name ?? record.id };
}

/** Rates and scores keep 4 decimal places in the compact JSON. */
function rate(value: number): number {
  return Math.round(value * 10_000) / 10_000;
}

/** USD amounts are whole dollars in the compact JSON. */
function usd(value: number): number {
  return Math.round(value);
}

function compactBreakdown(b: ScoreBreakdown): ScoreBreakdown {
  return {
    yield: rate(b.yield),
    appreciation: rate(b.appreciation),
    momentum: rate(b.momentum),
    leverage: rate(b.leverage),
    total: rate(b.total),
  };
}

function compactPosition(p: Position): Position {
  return {
    offering_id: p.offering_id,
    name: p.name,
    market: p.market,
    property_type: p.property_type,
    amount_usd: usd(p.amount_usd),
    weight_pct: rate(p.weight_pct),
    projected_dividend_yield: rate(p.projected_dividend_yield),
    projected_appreciation: rate(p.projected_appreciation),
    est_annual_dividend_usd: usd(p.est_annual_dividend_usd),
    score_breakdown: compactBreakdown(p.score_breakdown),
  };
}

function compactSummary(s: PlanSummary): PlanSummary {
  return {
    requested_usd: usd(s.requested_usd),
    total_invested_usd: usd(s.total_invested_usd),
    unallocated_cash_usd: usd(s.unallocated_cash_usd),
    existing_portfolio_usd: usd(s.existing_portfolio_usd),
    portfolio_total_usd: usd(s.portfolio_total_usd),
    position_count: s.position_count,
    blended_dividend_yield: rate(s.blended_dividend_yield),
    projected_annual_dividends_usd: usd(s.projected_annual_dividends_usd),
    projected_value_at_horizon_usd: usd(s.projected_value_at_horizon_usd),
    projected_cumulative_dividends_usd: usd(s.projected_cumulative_dividends_usd),
    projected_total_at_horizon_usd: usd(s.projected_total_at_horizon_usd),
  };
}

/** The output fields the design keeps: summary, positions (with score
 * breakdowns), risk_profile, horizon_years. Saved snapshots are always
 * feasible (R12), but the type admits infeasible — keep just its reason.
 */
function compactOutput(output: Plan): Record<string, unknown> {
  if (!output.feasible) return { feasible: false, reason: output.reason };
  return {
    risk_profile: output.risk_profile,
    horizon_years: output.horizon_years,
    summary: compactSummary(output.summary),
    positions: output.positions.map(compactPosition),
  };
}

/** The delimited context block: header (name or id), one line of compact
 * JSON (USD whole, rates/scores 4 dp), closing delimiter.
 */
export function formatPlanAttachment(record: PlanRecord): string {
  const payload = {
    id: record.id,
    name: record.name,
    created_at: record.created_at,
    data_as_of: record.data_as_of,
    inputs: {
      amount: usd(record.inputs.amount),
      risk_profile: record.inputs.risk_profile,
      horizon_years: record.inputs.horizon_years,
      existing_positions: Object.fromEntries(
        Object.entries(record.inputs.existing_positions).map(([id, amount]) => [id, usd(amount)]),
      ),
    },
    output: compactOutput(record.output),
  };
  return `[ATTACHED PLAN: ${toPlanAttachment(record).name}]\n${JSON.stringify(payload)}\n[/ATTACHED PLAN]`;
}
