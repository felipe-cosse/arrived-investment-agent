/** zustand chat store: transcript, in-flight streaming text, tool activity, and
 * the data-panel content (§4). Every SSE event is applied through one
 * exhaustive switch (R29); typed `*_result` events become panel content the UI
 * renders as components while the transcript keeps only prose (R18).
 */

import { create } from "zustand";
import { streamChat } from "../api/sse";
import { errorMessage } from "../api/client";
import { formatPlanAttachment, toPlanAttachment } from "../components/chat/attachment";
import type { PlanAttachment } from "../components/chat/attachment";
import { usePlansStore } from "./plansStore";
import type { PlanRecord } from "../types/domain";
import type { ChatTurn, ResultEvent, SseEvent } from "../types/events";

export type ToolStatus = "running" | "done" | "error";

/** A transcript turn as stored: wire `content` may embed an attachment block,
 * while the UI renders the chip plus `display` (the typed text) instead.
 */
export interface ChatMessage extends ChatTurn {
  attachment?: PlanAttachment;
  display?: string;
}

/** Asked on behalf of the user when a plan is attached with no typed text. */
const DEFAULT_ATTACHMENT_QUESTION = "What do you think of this plan?";

/** One tool call's lifecycle, shown by ToolStatus while the agent works. */
export interface ToolActivity {
  id: string;
  tool: string;
  status: ToolStatus;
  error?: string;
}

interface ChatState {
  messages: ChatMessage[];
  streamingText: string;
  isStreaming: boolean;
  toolActivity: ToolActivity[];
  panelContent: ResultEvent | null;
  pendingAttachment: (PlanAttachment & { block: string }) | null;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  attachPlan: (record: PlanRecord) => void;
  clearAttachment: () => void;
  showResult: (result: ResultEvent) => void;
  clearError: () => void;
}

/** Mark the most recent running call of `tool` settled; result events carry the
 * tool name, not the tool_use id, so recency is the §9 correlation rule.
 */
function settle(
  activity: ToolActivity[],
  tool: string,
  status: ToolStatus,
  error?: string,
): ToolActivity[] {
  for (let i = activity.length - 1; i >= 0; i -= 1) {
    const entry = activity[i];
    if (entry.tool === tool && entry.status === "running") {
      const next = [...activity];
      next[i] = error === undefined ? { ...entry, status } : { ...entry, status, error };
      return next;
    }
  }
  return activity;
}

/** Keep the saved-plans store in sync with what the agent just did. */
function syncPlans(event: ResultEvent): void {
  if (event.type === "saved_plans_result") {
    usePlansStore.getState().setPlans(event.result.plans);
  } else if (event.type === "plan_saved_result" && !("feasible" in event.result)) {
    usePlansStore.getState().ingestRecord(event.result);
  }
}

/** Exhaustiveness backstop: a new SseEvent variant fails compilation here (R29). */
function assertNever(event: never): never {
  throw new Error(`unhandled SSE event: ${JSON.stringify(event)}`);
}

export const useChatStore = create<ChatState>()((set, get) => {
  /** Fold the streamed text into the transcript and unlock the composer. */
  const finalize = (error: string | null): void => {
    set((s) => ({
      messages: s.streamingText
        ? [...s.messages, { role: "assistant" as const, content: s.streamingText }]
        : s.messages,
      streamingText: "",
      isStreaming: false,
      error: error ?? s.error,
    }));
  };

  const apply = (event: SseEvent): void => {
    switch (event.type) {
      case "text_delta":
        set((s) => ({ streamingText: s.streamingText + event.text }));
        break;
      case "tool_started":
        set((s) => ({
          toolActivity: [...s.toolActivity, { id: event.id, tool: event.tool, status: "running" }],
        }));
        break;
      case "offerings_result":
      case "offering_details_result":
      case "returns_result":
      case "market_context_result":
      case "plan_result":
      case "plan_saved_result":
      case "saved_plans_result":
        set((s) => ({ toolActivity: settle(s.toolActivity, event.tool, "done"), panelContent: event }));
        syncPlans(event);
        break;
      case "tool_error":
        set((s) => ({ toolActivity: settle(s.toolActivity, event.tool, "error", event.error) }));
        break;
      case "done":
        finalize(null);
        break;
      case "error":
        finalize(event.message);
        break;
      default:
        assertNever(event);
    }
  };

  return {
    messages: [],
    streamingText: "",
    isStreaming: false,
    toolActivity: [],
    panelContent: null,
    pendingAttachment: null,
    error: null,

    sendMessage: async (text: string): Promise<void> => {
      const typed = text.trim();
      const pending = get().pendingAttachment;
      if ((typed === "" && pending === null) || get().isStreaming) return;
      const display = typed === "" ? DEFAULT_ATTACHMENT_QUESTION : typed;
      // With an attachment the wire content carries the context block; the
      // transcript renders the chip + display text instead (never the block).
      const turn: ChatMessage =
        pending === null
          ? { role: "user", content: display }
          : {
              role: "user",
              content: `${pending.block}\n\n${display}`,
              display,
              attachment: { id: pending.id, name: pending.name },
            };
      const messages: ChatMessage[] = [...get().messages, turn];
      set({
        messages,
        pendingAttachment: null,
        streamingText: "",
        isStreaming: true,
        toolActivity: [],
        error: null,
      });
      try {
        await streamChat(messages.map(({ role, content }) => ({ role, content })), apply);
      } catch (err) {
        finalize(errorMessage(err));
      }
      // A stream that ends without a terminal event still unlocks the UI.
      if (get().isStreaming) finalize(null);
    },

    attachPlan: (record: PlanRecord): void =>
      set({ pendingAttachment: { ...toPlanAttachment(record), block: formatPlanAttachment(record) } }),

    clearAttachment: (): void => set({ pendingAttachment: null }),

    showResult: (result: ResultEvent): void => set({ panelContent: result }),

    clearError: (): void => set({ error: null }),
  };
});
