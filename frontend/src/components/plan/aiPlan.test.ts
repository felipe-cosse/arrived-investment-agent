import { describe, expect, it } from "vitest";
import type { Plan } from "../../types/domain";
import type { SseEvent } from "../../types/events";
import {
  INITIAL_AI_PLAN_STATE,
  buildGoalMessage,
  planInputToRequest,
  reduceAiPlanEvent,
} from "./aiPlan";

/** InfeasiblePlan is the smallest valid Plan — the reducer never inspects fields. */
const PLAN: Plan = { feasible: false, reason: "fixture" };
const INPUT = { amount: 2000, risk_profile: "balanced", horizon_years: 5 };

function reduceAll(events: SseEvent[]) {
  return events.reduce(reduceAiPlanEvent, INITIAL_AI_PLAN_STATE);
}

describe("buildGoalMessage", () => {
  it("returns a single user turn containing the goal verbatim", () => {
    const messages = buildGoalMessage("$5k, steady income, ~5 years");
    expect(messages).toHaveLength(1);
    expect(messages[0].role).toBe("user");
    expect(messages[0].content).toContain("$5k, steady income, ~5 years");
    expect(messages[0].content).toContain("build_investment_plan");
  });
});

describe("reduceAiPlanEvent", () => {
  it("accumulates text_delta into narrative", () => {
    const state = reduceAll([
      { type: "text_delta", text: "I read this " },
      { type: "text_delta", text: "as balanced." },
    ]);
    expect(state.narrative).toBe("I read this as balanced.");
  });

  it("captures plan and planInput from plan_result", () => {
    const state = reduceAll([
      { type: "plan_result", tool: "build_investment_plan", input: INPUT, result: PLAN },
    ]);
    expect(state.plan).toEqual(PLAN);
    expect(state.planInput).toEqual({ amount: 2000, risk_profile: "balanced", horizon_years: 5 });
  });

  it("records tool_error and error events", () => {
    expect(reduceAll([{ type: "tool_error", tool: "build_investment_plan", error: "boom" }]).error)
      .toContain("boom");
    expect(reduceAll([{ type: "error", message: "no key" }]).error).toBe("no key");
  });

  it("marks done and leaves plan null when the agent only asked a question", () => {
    const state = reduceAll([
      { type: "text_delta", text: "How much would you like to invest?" },
      { type: "done", stop_reason: "end_turn" },
    ]);
    expect(state.done).toBe(true);
    expect(state.plan).toBeNull();
    expect(state.error).toBeNull();
  });

  it("ignores unrelated result events", () => {
    const state = reduceAll([
      { type: "tool_started", tool: "get_offerings", id: "t1" },
      { type: "offerings_result", tool: "get_offerings", input: {}, result: { count: 0, offerings: [] } },
    ]);
    expect(state).toEqual(INITIAL_AI_PLAN_STATE);
  });
});

describe("planInputToRequest", () => {
  it("builds a PlanRequest from valid tool input", () => {
    expect(planInputToRequest(INPUT)).toEqual({
      amount: 2000,
      risk_profile: "balanced",
      horizon_years: 5,
    });
  });

  it("passes existing_positions through when present", () => {
    const positions = [{ offering_id: "sfr-meridian", amount_usd: 300 }];
    expect(planInputToRequest({ amount: 1000, existing_positions: positions }))
      .toEqual({ amount: 1000, existing_positions: positions });
  });

  it("returns null without a numeric amount", () => {
    expect(planInputToRequest({})).toBeNull();
    expect(planInputToRequest({ amount: "lots" })).toBeNull();
  });
});
