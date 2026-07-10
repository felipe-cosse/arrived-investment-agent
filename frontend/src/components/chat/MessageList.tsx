/** Chat transcript: user/assistant turns, the in-flight streaming assistant
 * message in an `aria-live="polite"` region (R30), an empty-state with
 * suggested prompts, and auto-scroll pinned to the newest content.
 */

import { useEffect, useRef } from "react";
import type { ReactElement } from "react";
import { useChatStore } from "../../state/chatStore";
import type { ChatMessage } from "../../state/chatStore";

const SUGGESTIONS = [
  "Compare Nashville vs Tucson, then invest $2,000 balanced",
  "Which offerings have the highest dividend yield?",
  "Build a $5,000 conservative plan over 10 years",
] as const;

function Bubble({ turn }: { turn: ChatMessage }): ReactElement {
  if (turn.role === "user") {
    // An attached plan renders as a chip + the typed text — never the raw block.
    return (
      <div className="ml-xl flex flex-col items-end gap-sm self-end">
        {turn.attachment !== undefined && (
          <span className="rounded-sm bg-accent/10 px-sm text-label text-accent">
            📎 {turn.attachment.name}
          </span>
        )}
        <div className="rounded-md bg-accent px-md py-sm text-body text-surface shadow-sm">
          {turn.display ?? turn.content}
        </div>
      </div>
    );
  }
  return (
    <div className="mr-xl self-start whitespace-pre-wrap rounded-md bg-background px-md py-sm text-body text-primary">
      {turn.content}
    </div>
  );
}

function EmptyState({ onPick }: { onPick: (prompt: string) => void }): ReactElement {
  return (
    <div className="flex flex-col gap-sm">
      <p className="text-body text-secondary">
        Explore fractional real-estate offerings and build hypothetical investment plans. Try:
      </p>
      {SUGGESTIONS.map((prompt) => (
        <button
          key={prompt}
          type="button"
          onClick={() => onPick(prompt)}
          className="rounded-md border border-secondary/20 bg-surface px-md py-sm text-left text-label text-secondary transition-colors hover:border-accent hover:text-accent"
        >
          {prompt}
        </button>
      ))}
    </div>
  );
}

export default function MessageList(): ReactElement {
  const messages = useChatStore((s) => s.messages);
  const streamingText = useChatStore((s) => s.streamingText);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, streamingText]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-sm overflow-y-auto p-lg" role="log">
      {messages.length === 0 && !isStreaming && (
        <EmptyState onPick={(prompt) => void sendMessage(prompt)} />
      )}
      {messages.map((turn, i) => (
        <Bubble key={`${i}-${turn.role}`} turn={turn} />
      ))}
      <div aria-live="polite" className="flex flex-col">
        {streamingText !== "" && (
          <div className="mr-xl self-start whitespace-pre-wrap rounded-md bg-background px-md py-sm text-body text-primary">
            {streamingText}
          </div>
        )}
        {isStreaming && streamingText === "" && (
          <span className="animate-pulse self-start px-md text-label text-secondary">
            Thinking…
          </span>
        )}
      </div>
      <div ref={endRef} />
    </div>
  );
}
