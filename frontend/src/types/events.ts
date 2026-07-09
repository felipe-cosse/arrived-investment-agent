/** Discriminated union of the SSE events streamed by POST /api/chat (§9, R29).
 *
 * `type` carries the SSE `event:` name; the payload fields mirror the backend's
 * frame data exactly. Consumers switch exhaustively over `SseEvent` — a
 * never-typed default arm keeps the union and the handling code in lockstep.
 */

import type {
  InfeasiblePlan,
  MarketContext,
  Offering,
  Plan,
  PlanRecord,
  ReturnRecord,
  SavedPlanSummary,
} from "./domain";

/** One transcript turn; the client sends the full visible transcript (§9). */
export interface ChatTurn {
  role: "user" | "assistant";
  content: string;
}

/** Streamed assistant prose, appended to the in-flight message. */
export interface TextDeltaEvent {
  type: "text_delta";
  text: string;
}

/** Emitted at `content_block_start` when the model begins a tool call. */
export interface ToolStartedEvent {
  type: "tool_started";
  tool: string;
  id: string;
}

/** Shared shape of every typed `*_result` event: tool name, args, result (§8). */
interface ToolResultBase {
  tool: string;
  input: Record<string, unknown>;
}

export interface OfferingsResultEvent extends ToolResultBase {
  type: "offerings_result";
  result: { count: number; offerings: Offering[] };
}

export interface OfferingDetailsResultEvent extends ToolResultBase {
  type: "offering_details_result";
  result: { offering: Offering; history: ReturnRecord[] };
}

export interface ReturnsResultEvent extends ToolResultBase {
  type: "returns_result";
  result: { offering_id: string; months: number; returns: ReturnRecord[] };
}

export interface MarketContextResultEvent extends ToolResultBase {
  type: "market_context_result";
  result: { market: string } & MarketContext;
}

export interface PlanResultEvent extends ToolResultBase {
  type: "plan_result";
  result: Plan;
}

/** Saving re-runs the engine, so an infeasible request yields no record (R12). */
export interface PlanSavedResultEvent extends ToolResultBase {
  type: "plan_saved_result";
  result: PlanRecord | InfeasiblePlan;
}

export interface SavedPlansResultEvent extends ToolResultBase {
  type: "saved_plans_result";
  result: { plans: SavedPlanSummary[] };
}

/** A tool call failed; the agent loop reported it and keeps going (R28). */
export interface ToolErrorEvent {
  type: "tool_error";
  tool: string;
  error: string;
}

export type StopReason = "end_turn" | "max_tokens" | "max_turns";

/** Terminal event of a successful stream. */
export interface DoneEvent {
  type: "done";
  stop_reason: StopReason;
}

/** Terminal event of a failed stream (R28). */
export interface StreamErrorEvent {
  type: "error";
  message: string;
}

/** The typed tool results the data panel renders as components (R18). */
export type ResultEvent =
  | OfferingsResultEvent
  | OfferingDetailsResultEvent
  | ReturnsResultEvent
  | MarketContextResultEvent
  | PlanResultEvent
  | PlanSavedResultEvent
  | SavedPlansResultEvent;

export type SseEvent =
  | TextDeltaEvent
  | ToolStartedEvent
  | ResultEvent
  | ToolErrorEvent
  | DoneEvent
  | StreamErrorEvent;
