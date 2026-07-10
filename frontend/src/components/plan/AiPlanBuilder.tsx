/** Natural-language plan building: the agent interprets a goal, calls the
 * deterministic planner tool over the chat SSE stream (R19), and its
 * reasoning streams next to the rendered plan. Component-local state only —
 * the chat panel's transcript is untouched.
 */

import { useState } from "react";
import type { ReactElement } from "react";
import { errorMessage, savePlan } from "../../api/client";
import { streamChat } from "../../api/sse";
import { usePlansStore } from "../../state/plansStore";
import Markdown from "../Markdown";
import {
  INITIAL_AI_PLAN_STATE,
  buildGoalMessage,
  reduceAiPlanEvent,
} from "./aiPlan";
import type { AiPlanState } from "./aiPlan";
import PlanSummary from "./PlanSummary";

const FIELD_CLASS =
  "rounded-md border border-secondary/20 bg-surface px-sm py-sm text-body text-primary focus:border-accent focus:outline-none";

const BUTTON_PRIMARY =
  "rounded-md bg-accent px-md py-sm text-body font-medium text-surface shadow-sm transition-opacity disabled:opacity-50";

export default function AiPlanBuilder(): ReactElement {
  const [goal, setGoal] = useState("");
  const [state, setState] = useState<AiPlanState>(INITIAL_AI_PLAN_STATE);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [savedAs, setSavedAs] = useState<string | null>(null);
  const ingestRecord = usePlansStore((s) => s.ingestRecord);

  const build = async (): Promise<void> => {
    setBusy(true);
    setSavedAs(null);
    setState(INITIAL_AI_PLAN_STATE);
    try {
      await streamChat(buildGoalMessage(goal), (event) =>
        setState((prev) => reduceAiPlanEvent(prev, event)),
      );
    } catch (err) {
      setState((prev) => ({ ...prev, error: errorMessage(err) }));
    }
    setBusy(false);
  };

  const save = async (): Promise<void> => {
    if (state.planInput === null) return;
    setBusy(true);
    try {
      const record = await savePlan({ ...state.planInput, name: name.trim() || undefined });
      ingestRecord(record);
      setSavedAs(record.name ?? record.id);
    } catch (err) {
      setState((prev) => ({ ...prev, error: errorMessage(err) }));
    }
    setBusy(false);
  };

  return (
    <div className="flex flex-col gap-lg">
      <form
        className="flex flex-col gap-md rounded-lg bg-surface p-lg shadow-sm"
        onSubmit={(event) => {
          event.preventDefault();
          void build();
        }}
      >
        <label className="flex flex-col gap-sm text-label text-secondary">
          Describe your goal
          <textarea
            required
            rows={2}
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="e.g. $5k for steady income, fairly cautious, around 5 years"
            className={FIELD_CLASS}
          />
        </label>
        <button type="submit" disabled={busy || goal.trim() === ""} className={`${BUTTON_PRIMARY} self-start`}>
          ✨ Build with AI
        </button>
      </form>
      {state.error !== null && (
        <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
          {state.error} — the deterministic form above works on already-loaded data.
        </p>
      )}
      <div aria-live="polite">
        {state.narrative !== "" && (
          <div className="rounded-lg bg-surface p-lg text-body text-primary shadow-sm">
            <Markdown text={state.narrative} />
          </div>
        )}
      </div>
      {state.plan !== null && state.plan.feasible && state.planInput !== null && (
        <div className="flex flex-wrap items-end gap-md rounded-lg bg-surface p-lg shadow-sm">
          <label className="flex min-w-0 flex-1 flex-col gap-sm text-label text-secondary">
            Snapshot name (optional)
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. AI balanced $5k" className={FIELD_CLASS} />
          </label>
          <button type="button" disabled={busy} onClick={() => void save()} className={BUTTON_PRIMARY}>
            Save plan
          </button>
          {savedAs !== null && (
            <span className="rounded-sm bg-success/10 px-sm py-sm text-label text-success">
              Saved “{savedAs}” — see Saved plans
            </span>
          )}
        </div>
      )}
      {state.plan !== null && <PlanSummary plan={state.plan} />}
    </div>
  );
}
