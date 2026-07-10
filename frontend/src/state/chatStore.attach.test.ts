/** Covers chatStore attachment flows: pending lifecycle, wire block vs display text, defaults. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "../api/sse";
import type { PlanRecord } from "../types/domain";
import { useChatStore } from "./chatStore";

vi.mock("../api/sse", () => ({ streamChat: vi.fn() }));

/** InfeasiblePlan is the smallest valid Plan — block content is pinned elsewhere. */
const RECORD: PlanRecord = {
  id: "plan-9",
  name: "Income tilt",
  created_at: "2026-07-09T12:00:00Z",
  data_as_of: "2026-07-01",
  inputs: { amount: 1500, risk_profile: "balanced", horizon_years: 5, existing_positions: {} },
  output: { feasible: false, reason: "fixture" },
};

const streamChatMock = vi.mocked(streamChat);

beforeEach(() => {
  streamChatMock.mockReset();
  streamChatMock.mockResolvedValue(undefined);
  useChatStore.setState({
    messages: [],
    streamingText: "",
    isStreaming: false,
    toolActivity: [],
    panelContent: null,
    error: null,
    pendingAttachment: null,
  });
});

describe("attachPlan / clearAttachment", () => {
  it("stores the pending attachment with its formatted block", () => {
    useChatStore.getState().attachPlan(RECORD);
    const pending = useChatStore.getState().pendingAttachment;
    expect(pending?.id).toBe("plan-9");
    expect(pending?.name).toBe("Income tilt");
    expect(pending?.block).toContain("[ATTACHED PLAN: Income tilt]");
    expect(pending?.block).toContain("[/ATTACHED PLAN]");
  });

  it("clearAttachment removes the pending attachment", () => {
    useChatStore.getState().attachPlan(RECORD);
    useChatStore.getState().clearAttachment();
    expect(useChatStore.getState().pendingAttachment).toBeNull();
  });
});

describe("sendMessage with an attachment", () => {
  it("sends block + typed text on the wire while display keeps only the text", async () => {
    useChatStore.getState().attachPlan(RECORD);
    const block = useChatStore.getState().pendingAttachment?.block ?? "";
    await useChatStore.getState().sendMessage("Why is this ranked first?");

    expect(streamChatMock).toHaveBeenCalledTimes(1);
    const wire = streamChatMock.mock.calls[0][0];
    expect(wire[wire.length - 1].content).toBe(`${block}\n\nWhy is this ranked first?`);

    const message = useChatStore.getState().messages[0];
    expect(message.display).toBe("Why is this ranked first?");
    expect(message.attachment).toEqual({ id: "plan-9", name: "Income tilt" });
  });

  it("strips wire messages down to role and content only", async () => {
    useChatStore.getState().attachPlan(RECORD);
    await useChatStore.getState().sendMessage("Compare with a 10y horizon");
    const wire = streamChatMock.mock.calls[0][0];
    for (const turn of wire) {
      expect(Object.keys(turn).sort()).toEqual(["content", "role"]);
    }
  });

  it("clears the pending attachment once sent", async () => {
    useChatStore.getState().attachPlan(RECORD);
    await useChatStore.getState().sendMessage("thoughts?");
    expect(useChatStore.getState().pendingAttachment).toBeNull();
  });

  it("substitutes the default question when the typed text is empty", async () => {
    useChatStore.getState().attachPlan(RECORD);
    await useChatStore.getState().sendMessage("  ");
    const wire = streamChatMock.mock.calls[0][0];
    expect(wire[0].content.endsWith("\n\nWhat do you think of this plan?")).toBe(true);
    expect(useChatStore.getState().messages[0].display).toBe("What do you think of this plan?");
  });
});

describe("sendMessage without an attachment", () => {
  it("still no-ops on empty text", async () => {
    await useChatStore.getState().sendMessage("   ");
    expect(streamChatMock).not.toHaveBeenCalled();
    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("sends plain text with no attachment metadata", async () => {
    await useChatStore.getState().sendMessage("List offerings in Tucson");
    const wire = streamChatMock.mock.calls[0][0];
    expect(wire[0]).toEqual({ role: "user", content: "List offerings in Tucson" });
    const message = useChatStore.getState().messages[0];
    expect(message.attachment).toBeUndefined();
    expect(message.display).toBeUndefined();
  });
});
