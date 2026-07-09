/** Live tool-call activity for the in-flight agent turn: one chip per call,
 * pulsing while running, success-tinted when its typed result arrived, and
 * primary-inverted with the error message on failure (R28 surfaced, not hidden).
 */

import type { ReactElement } from "react";
import { useChatStore } from "../../state/chatStore";
import type { ToolActivity } from "../../state/chatStore";
import { humanize } from "../../lib/format";

function chipClass(status: ToolActivity["status"]): string {
  switch (status) {
    case "running":
      return "animate-pulse bg-accent/10 text-accent";
    case "done":
      return "bg-success/10 text-success";
    case "error":
      return "bg-primary text-surface";
  }
}

export default function ToolStatus(): ReactElement | null {
  const activity = useChatStore((s) => s.toolActivity);
  if (activity.length === 0) return null;

  return (
    <ul aria-label="Tool activity" className="flex flex-wrap gap-sm px-lg pb-sm">
      {activity.map((entry) => (
        <li
          key={entry.id}
          title={entry.error}
          className={`rounded-sm px-sm py-sm text-label ${chipClass(entry.status)}`}
        >
          {humanize(entry.tool)}
          {entry.status === "running" && "…"}
          {entry.status === "error" && " — failed"}
        </li>
      ))}
    </ul>
  );
}
