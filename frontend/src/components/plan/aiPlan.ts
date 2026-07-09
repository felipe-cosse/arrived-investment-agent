/** Pure helpers for the AI plan builder: the one-shot prompt sent to
 * /api/chat and the reducer that folds its SSE events into view state.
 * The model only picks parameters — every plan comes from the engine (§1).
 */

import type { ExistingPositionInput, PlanRequest } from "../../api/client";
import type { Plan } from "../../types/domain";
import type { ChatTurn, SseEvent } from "../../types/events";

export interface AiPlanState {
  narrative: string;
  plan: Plan | null;
  planInput: PlanRequest | null;
  error: string | null;
  done: boolean;
}

export const INITIAL_AI_PLAN_STATE: AiPlanState = {
  narrative: "",
  plan: null,
  planInput: null,
  error: null,
  done: false,
};

const PREAMBLE =
  "Build an investment plan for the goal below. First state briefly how you " +
  "interpret it (amount, risk profile, horizon in years), then call " +
  "build_investment_plan with those parameters. If the goal does not state " +
  "an amount, ask for it instead of guessing.";

/** One user turn: fixed preamble plus the verbatim goal (server owns the system prompt). */
export function buildGoalMessage(goal: string): ChatTurn[] {
  return [{ role: "user", content: `${PREAMBLE}\n\nGoal: ${goal}` }];
}

function isPositionList(value: unknown): value is ExistingPositionInput[] {
  return (
    Array.isArray(value) &&
    value.every(
      (row) =>
        typeof row === "object" &&
        row !== null &&
        typeof (row as { offering_id?: unknown }).offering_id === "string" &&
        typeof (row as { amount_usd?: unknown }).amount_usd === "number",
    )
  );
}

/** Narrow the tool call's raw input into the shape POST /api/plans accepts. */
export function planInputToRequest(input: Record<string, unknown>): PlanRequest | null {
  const { amount, risk_profile, horizon_years, existing_positions } = input;
  if (typeof amount !== "number" || !Number.isFinite(amount)) return null;
  const request: PlanRequest = { amount };
  if (typeof risk_profile === "string") request.risk_profile = risk_profile;
  if (typeof horizon_years === "number") request.horizon_years = horizon_years;
  if (isPositionList(existing_positions)) request.existing_positions = existing_positions;
  return request;
}

/** Fold one SSE event into the view state (exhaustive over the §9 union, R29). */
export function reduceAiPlanEvent(state: AiPlanState, event: SseEvent): AiPlanState {
  switch (event.type) {
    case "text_delta":
      return { ...state, narrative: state.narrative + event.text };
    case "plan_result":
      return { ...state, plan: event.result, planInput: planInputToRequest(event.input) };
    case "tool_error":
      return { ...state, error: `${event.tool}: ${event.error}` };
    case "error":
      return { ...state, error: event.message };
    case "done":
      return { ...state, done: true };
    case "tool_started":
    case "offerings_result":
    case "offering_details_result":
    case "returns_result":
    case "market_context_result":
    case "plan_saved_result":
    case "saved_plans_result":
      return state;
    default: {
      const exhaustive: never = event;
      return exhaustive;
    }
  }
}
