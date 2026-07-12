import { afterEach, describe, expect, it, vi } from "vitest";
import { createSseDecoder, streamChat } from "./sse";

afterEach(() => vi.unstubAllGlobals());

describe("createSseDecoder", () => {
  it("reassembles events split across chunk boundaries", () => {
    const events: unknown[] = [];
    const feed = createSseDecoder((e) => events.push(e));
    feed("event: text_delta\nda");
    feed('ta: {"text":"he');
    feed('llo"}\n\nevent: done\ndata: {"stop_reason":"end_turn"}\n\n');
    expect(events).toEqual([
      { type: "text_delta", text: "hello" },
      { type: "done", stop_reason: "end_turn" },
    ]);
  });

  it("handles multiple events per chunk and ignores comment keep-alives", () => {
    const events: unknown[] = [];
    const feed = createSseDecoder((e) => events.push(e));
    feed(':ka\n\nevent: tool_started\ndata: {"tool":"get_offerings","id":"t1"}\n\n' +
         'event: error\ndata: {"message":"boom"}\n\n');
    expect(events).toEqual([
      { type: "tool_started", tool: "get_offerings", id: "t1" },
      { type: "error", message: "boom" },
    ]);
  });
});

describe("streamChat", () => {
  it("rejects a graceful EOF without done or error", async () => {
    const body = 'event: text_delta\ndata: {"text":"partial"}\n\n';
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));
    const events: unknown[] = [];

    await expect(
      streamChat([{ role: "user", content: "hello" }], (event) => events.push(event)),
    ).rejects.toThrow("chat stream ended before a terminal event");
    expect(events).toEqual([{ type: "text_delta", text: "partial" }]);
  });

  it("ignores frames after the first terminal event", async () => {
    const body =
      'event: done\ndata: {"stop_reason":"end_turn"}\n\n' +
      "event: text_delta\ndata: {malformed after terminal}\n\n";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));
    const events: unknown[] = [];

    await streamChat([{ role: "user", content: "hello" }], (event) => events.push(event));

    expect(events).toEqual([{ type: "done", stop_reason: "end_turn" }]);
  });
});
