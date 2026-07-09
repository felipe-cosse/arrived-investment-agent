/** Chat input: textarea with Enter-to-send (Shift+Enter for a newline) and a
 * button-primary send action; locked while a response is streaming.
 */

import { useState } from "react";
import type { ReactElement } from "react";
import { useChatStore } from "../../state/chatStore";

export default function Composer(): ReactElement {
  const [draft, setDraft] = useState("");
  const isStreaming = useChatStore((s) => s.isStreaming);
  const sendMessage = useChatStore((s) => s.sendMessage);

  const submit = (): void => {
    const text = draft.trim();
    if (text === "" || isStreaming) return;
    setDraft("");
    void sendMessage(text);
  };

  return (
    <form
      className="flex items-end gap-sm border-t border-secondary/20 p-md"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <label className="sr-only" htmlFor="chat-input">
        Message the investment agent
      </label>
      <textarea
        id="chat-input"
        rows={2}
        value={draft}
        placeholder="Ask about offerings, markets, or a plan…"
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        className="flex-1 resize-none rounded-md border border-secondary/20 bg-surface px-md py-sm text-body text-primary placeholder:text-secondary focus:border-accent focus:outline-none"
      />
      <button
        type="submit"
        disabled={isStreaming || draft.trim() === ""}
        className="rounded-md bg-accent px-md py-sm text-body font-medium text-surface shadow-sm transition-opacity disabled:opacity-50"
      >
        Send
      </button>
    </form>
  );
}
