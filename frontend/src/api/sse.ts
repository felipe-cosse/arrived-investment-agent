/** SSE decoding for POST /api/chat: `createSseDecoder` plus the fetch-based
 * stream reader (§9). `EventSource` is GET-only and CANNOT be used (R19), so
 * the chat stream is consumed via `fetch` + `ReadableStream` and fed through
 * the decoder, which reassembles events split across chunk boundaries.
 */

import { apiUrl, responseDetail } from "./client";
import type { ChatTurn, SseEvent } from "../types/events";

export type SseListener = (event: SseEvent) => void;

/** Parse one complete SSE frame; comment-only keep-alives (`:ka`) yield null. */
function parseFrame(frame: string): SseEvent | null {
  let name = "";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    if (line.startsWith("event:")) name = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) data.push(line.slice("data:".length).trimStart());
  }
  if (name === "" || data.length === 0) return null;
  const payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
  // The wire's `event:` name becomes the union discriminant; the payload is
  // trusted to match the §9 contract pinned by the backend's canonical tests.
  return { ...payload, type: name } as unknown as SseEvent;
}

/** Stateful decoder: feed it raw text chunks, it emits complete typed events.
 *
 * Buffers across calls so events split anywhere — even mid-`data:` keyword —
 * are reassembled exactly once (Appendix A pins this contract).
 */
export function createSseDecoder(onEvent: SseListener): (chunk: string) => void {
  let buffer = "";
  let terminal = false;
  return (chunk: string): void => {
    if (terminal) return;
    buffer += chunk;
    for (let end = buffer.indexOf("\n\n"); end !== -1; end = buffer.indexOf("\n\n")) {
      const frame = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = parseFrame(frame);
      if (event !== null) {
        onEvent(event);
        terminal = event.type === "done" || event.type === "error";
        if (terminal) return;
      }
    }
  };
}

/** POST the transcript to /api/chat and pump the SSE body through the decoder.
 *
 * HTTP failures (e.g. 503 without ANTHROPIC_API_KEY) surface as a terminal
 * `error` event so callers handle one event stream, not two error channels.
 * Network-level rejections propagate to the caller (R28: fail loud).
 */
export async function streamChat(
  messages: ChatTurn[],
  onEvent: SseListener,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(apiUrl("/chat"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
    signal,
  });
  if (!response.ok) {
    onEvent({ type: "error", message: await responseDetail(response) });
    return;
  }
  if (response.body === null) {
    onEvent({ type: "error", message: "chat response has no readable body" });
    return;
  }
  let terminal = false;
  const feed = createSseDecoder((event) => {
    if (terminal) return;
    onEvent(event);
    terminal = event.type === "done" || event.type === "error";
  });
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    feed(decoder.decode(value, { stream: true }));
    if (terminal) {
      await reader.cancel();
      return;
    }
  }
  feed(decoder.decode());
  if (!terminal) throw new Error("chat stream ended before a terminal event");
}
