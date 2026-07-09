import { describe, expect, it } from "vitest";
import { createSseDecoder } from "./sse";

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
