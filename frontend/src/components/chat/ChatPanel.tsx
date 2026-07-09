/** Left-pane chat surface (§4): header, scrolling transcript, live tool
 * activity, a dismissible stream-error banner, and the composer — one elevated
 * card per the DESIGN.md surface/shadow rules.
 */

import type { ReactElement } from "react";
import { useChatStore } from "../../state/chatStore";
import Composer from "./Composer";
import MessageList from "./MessageList";
import ToolStatus from "./ToolStatus";

export default function ChatPanel(): ReactElement {
  const error = useChatStore((s) => s.error);
  const clearError = useChatStore((s) => s.clearError);

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg bg-surface shadow-md">
      <header className="border-b border-secondary/20 px-lg py-md">
        <h2 className="text-h2 font-semibold text-primary">Investment agent</h2>
        <p className="text-label text-secondary">
          Hypothetical projections — not investment advice
        </p>
      </header>
      <MessageList />
      <ToolStatus />
      {error !== null && (
        <div
          role="alert"
          className="mx-lg mb-sm flex items-start justify-between gap-sm rounded-md bg-primary px-md py-sm text-label text-surface"
        >
          <span>{error}</span>
          <button
            type="button"
            onClick={clearError}
            aria-label="Dismiss error"
            className="font-semibold"
          >
            ×
          </button>
        </div>
      )}
      <Composer />
    </div>
  );
}
