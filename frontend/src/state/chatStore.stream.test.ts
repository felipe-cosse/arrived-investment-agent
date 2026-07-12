/** Covers request isolation, terminal behavior, and ordered data-panel results. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import { streamChat } from "../api/sse";
import type { SseListener } from "../api/sse";
import type { ResultEvent } from "../types/events";
import { useChatStore } from "./chatStore";

vi.mock("../api/sse", () => ({ streamChat: vi.fn() }));

const OFFERINGS: ResultEvent = {
  type: "offerings_result",
  tool: "get_offerings",
  input: {},
  result: { count: 0, offerings: [] },
};
const RETURNS: ResultEvent = {
  type: "returns_result",
  tool: "get_returns",
  input: { offering_id: "arrived-1" },
  result: { offering_id: "arrived-1", months: 12, returns: [] },
};

const streamChatMock = vi.mocked(streamChat);

function deferred(): { promise: Promise<void>; resolve: () => void } {
  let resolve = (): void => undefined;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  streamChatMock.mockReset();
  useChatStore.setState({
    messages: [],
    streamingText: "",
    isStreaming: false,
    toolActivity: [],
    panelResults: [],
    pendingAttachment: null,
    error: null,
  });
});

describe("chat result collection", () => {
  it("clears old results and appends each streamed result in order", async () => {
    useChatStore.getState().showResult(RETURNS);
    streamChatMock.mockImplementation(async (_messages, onEvent) => {
      onEvent({ type: "tool_started", tool: "get_offerings", id: "tool-1" });
      onEvent(OFFERINGS);
      onEvent({ type: "tool_started", tool: "get_returns", id: "tool-2" });
      onEvent(RETURNS);
      onEvent({ type: "done", stop_reason: "end_turn" });
    });

    await useChatStore.getState().sendMessage("compare them");

    expect(useChatStore.getState().panelResults).toEqual([OFFERINGS, RETURNS]);
    expect(useChatStore.getState().toolActivity.map(({ status }) => status)).toEqual([
      "done",
      "done",
    ]);
  });
});

describe("chat request isolation", () => {
  it("ignores late events and completion from an older request", async () => {
    const first = deferred();
    const second = deferred();
    let firstListener: SseListener = () => undefined;
    let secondListener: SseListener = () => undefined;
    streamChatMock
      .mockImplementationOnce(async (_messages, onEvent) => {
        firstListener = onEvent;
        onEvent({ type: "done", stop_reason: "end_turn" });
        await first.promise;
      })
      .mockImplementationOnce(async (_messages, onEvent) => {
        secondListener = onEvent;
        await second.promise;
      });

    const firstSend = useChatStore.getState().sendMessage("first");
    const secondSend = useChatStore.getState().sendMessage("second");
    firstListener({ type: "text_delta", text: "stale" });
    firstListener(OFFERINGS);
    firstListener({ type: "error", message: "stale failure" });
    secondListener({ type: "text_delta", text: "current" });
    secondListener(RETURNS);
    secondListener({ type: "done", stop_reason: "end_turn" });
    second.resolve();
    await secondSend;
    first.resolve();
    await firstSend;

    const state = useChatStore.getState();
    expect(state.messages.at(-1)).toEqual({ role: "assistant", content: "current" });
    expect(state.panelResults).toEqual([RETURNS]);
    expect(state.error).toBeNull();
    expect(state.isStreaming).toBe(false);
  });

  it("reports a mocked stream that resolves without a terminal event", async () => {
    streamChatMock.mockResolvedValue(undefined);

    await useChatStore.getState().sendMessage("hello");

    expect(useChatStore.getState().error).toBe("chat stream ended before a terminal event");
    expect(useChatStore.getState().isStreaming).toBe(false);
  });
});
