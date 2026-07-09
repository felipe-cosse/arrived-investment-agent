/** zustand chat store: transcript, in-flight streaming text, tool activity, and
 * the data-panel content (§4). Every SSE event is applied through one
 * exhaustive switch (R29); typed `*_result` events become panel content the UI
 * renders as components while the transcript keeps only prose (R18).
 */

import { create } from "zustand";
import { streamChat } from "../api/sse";
import { errorMessage } from "../api/client";
import { usePlansStore } from "./plansStore";
import type { ChatTurn, ResultEvent, SseEvent } from "../types/events";

export type ToolStatus = "running" | "done" | "error";

/** One tool call's lifecycle, shown by ToolStatus while the agent works. */
export interface ToolActivity {
  id: string;
  tool: string;
  status: ToolStatus;
  error?: string;
}

interface ChatState {
  messages: ChatTurn[];
  streamingText: string;
  isStreaming: boolean;
  toolActivity: ToolActivity[];
  panelContent: ResultEvent | null;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
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
    error: null,

    sendMessage: async (text: string): Promise<void> => {
      const content = text.trim();
      if (content === "" || get().isStreaming) return;
      const messages: ChatTurn[] = [...get().messages, { role: "user", content }];
      set({ messages, streamingText: "", isStreaming: true, toolActivity: [], error: null });
      try {
        await streamChat(messages, apply);
      } catch (err) {
        finalize(errorMessage(err));
      }
      // A stream that ends without a terminal event still unlocks the UI.
      if (get().isStreaming) finalize(null);
    },

    showResult: (result: ResultEvent): void => set({ panelContent: result }),

    clearError: (): void => set({ error: null }),
  };
});
