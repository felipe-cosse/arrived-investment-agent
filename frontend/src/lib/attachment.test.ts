/** Pins the [ATTACHED PLAN] block: delimiters, verbatim inputs and score breakdowns, compact display numbers. */

import { describe, expect, it } from "vitest";
import type { PlanRecord } from "../types/domain";
import { formatPlanAttachment, toPlanAttachment } from "./attachment";

const RECORD: PlanRecord = {
  id: "plan-123",
  name: "Sunbelt income",
  created_at: "2026-07-09T12:00:00Z",
  data_as_of: "2026-07-01",
  inputs: {
    amount: 2000.4,
    risk_profile: "balanced",
    horizon_years: 5,
    existing_positions: { "sfr-oakview": 300.6 },
  },
  output: {
    feasible: true,
    risk_profile: "balanced",
    horizon_years: 5,
    positions: [
      {
        offering_id: "sfr-meridian",
        name: "Meridian House",
        market: "Nashville",
        property_type: "single_family",
        amount_usd: 1000.49,
        weight_pct: 0.500049,
        projected_dividend_yield: 0.045678,
        projected_appreciation: 0.031234,
        est_annual_dividend_usd: 45.7,
        score_breakdown: {
          yield: 0.91239,
          appreciation: 0.6,
          momentum: 0.5,
          leverage: 0.7,
          total: 0.712345,
        },
      },
    ],
    summary: {
      requested_usd: 2000.4,
      total_invested_usd: 2000,
      unallocated_cash_usd: 0.4,
      existing_portfolio_usd: 300.6,
      portfolio_total_usd: 2301,
      position_count: 1,
      blended_dividend_yield: 0.045678,
      projected_annual_dividends_usd: 91.36,
      projected_value_at_horizon_usd: 2650.5,
      projected_cumulative_dividends_usd: 470.2,
      projected_total_at_horizon_usd: 3120.7,
    },
    assumptions: ["seed data"],
    disclaimer: "Hypothetical projections — not investment advice.",
  },
};

/** The shape the block's compact JSON is expected to parse back into. */
interface ParsedBlock {
  id: string;
  name: string | null;
  created_at: string;
  data_as_of: string;
  inputs: {
    amount: number;
    risk_profile: string;
    horizon_years: number;
    existing_positions: Record<string, number>;
  };
  output: {
    risk_profile: string;
    horizon_years: number;
    summary: Record<string, number>;
    positions: Array<{
      offering_id: string;
      amount_usd: number;
      weight_pct: number;
      projected_dividend_yield: number;
      projected_appreciation: number;
      est_annual_dividend_usd: number;
      score_breakdown: Record<string, number>;
    }>;
    reason?: string;
  };
}

function parseBlock(block: string): ParsedBlock {
  const lines = block.split("\n");
  return JSON.parse(lines.slice(1, -1).join("\n")) as ParsedBlock;
}

describe("formatPlanAttachment", () => {
  it("wraps one compact JSON line in ATTACHED PLAN delimiters headed by the name", () => {
    const lines = formatPlanAttachment(RECORD).split("\n");
    expect(lines[0]).toBe("[ATTACHED PLAN: Sunbelt income]");
    expect(lines[lines.length - 1]).toBe("[/ATTACHED PLAN]");
    expect(lines).toHaveLength(3);
  });

  it("falls back to the id in the header when the name is null", () => {
    const block = formatPlanAttachment({ ...RECORD, name: null });
    expect(block.split("\n")[0]).toBe("[ATTACHED PLAN: plan-123]");
  });

  it("carries id, name, dates, inputs, and positions with full score_breakdown", () => {
    const parsed = parseBlock(formatPlanAttachment(RECORD));
    expect(parsed.id).toBe("plan-123");
    expect(parsed.name).toBe("Sunbelt income");
    expect(parsed.created_at).toBe("2026-07-09T12:00:00Z");
    expect(parsed.data_as_of).toBe("2026-07-01");
    expect(parsed.inputs.risk_profile).toBe("balanced");
    expect(parsed.inputs.horizon_years).toBe(5);
    expect(parsed.output.risk_profile).toBe("balanced");
    expect(parsed.output.horizon_years).toBe(5);
    expect(parsed.output.positions).toHaveLength(1);
    expect(parsed.output.positions[0].offering_id).toBe("sfr-meridian");
    expect(Object.keys(parsed.output.positions[0].score_breakdown).sort()).toEqual([
      "appreciation", "leverage", "momentum", "total", "yield",
    ]);
  });

  it("keeps inputs and score breakdowns verbatim while compacting other display numbers", () => {
    const parsed = parseBlock(formatPlanAttachment(RECORD));
    expect(parsed.inputs.amount).toBe(2000.4);
    expect(parsed.inputs.existing_positions["sfr-oakview"]).toBe(300.6);
    const position = parsed.output.positions[0];
    expect(position.score_breakdown.yield).toBe(0.91239);
    expect(position.score_breakdown.total).toBe(0.712345);
    expect(position.amount_usd).toBe(1000);
    expect(position.est_annual_dividend_usd).toBe(46);
    expect(position.weight_pct).toBe(0.5);
    expect(position.projected_dividend_yield).toBe(0.0457);
    expect(position.projected_appreciation).toBe(0.0312);
    expect(parsed.output.summary.requested_usd).toBe(2000);
    expect(parsed.output.summary.unallocated_cash_usd).toBe(0);
    expect(parsed.output.summary.blended_dividend_yield).toBe(0.0457);
    expect(parsed.output.summary.projected_annual_dividends_usd).toBe(91);
  });

  it("represents an infeasible output by its reason", () => {
    const record: PlanRecord = { ...RECORD, output: { feasible: false, reason: "amount too low" } };
    const parsed = parseBlock(formatPlanAttachment(record));
    expect(parsed.output.reason).toBe("amount too low");
  });
});

describe("toPlanAttachment", () => {
  it("exposes id and name, with the name falling back to the id", () => {
    expect(toPlanAttachment(RECORD)).toEqual({ id: "plan-123", name: "Sunbelt income" });
    expect(toPlanAttachment({ ...RECORD, name: null })).toEqual({ id: "plan-123", name: "plan-123" });
  });
});
