/** Saved-plan snapshots (§9): newest-first list with view, compare-selection
 * (two at a time), and delete. Snapshots are immutable (R16) — viewing loads
 * the stored output, never a re-run. Two selections render PlanCompare.
 */

import { useEffect, useState } from "react";
import type { ReactElement } from "react";
import { shortDate, usd } from "../../lib/format";
import { COMPARE_LIMIT, usePlansStore } from "../../state/plansStore";
import type { PlanRecord, SavedPlanSummary } from "../../types/domain";
import PlanCompare from "./PlanCompare";
import PlanSummary from "./PlanSummary";

function Row({ plan, expanded, onToggle }: {
  plan: SavedPlanSummary;
  expanded: boolean;
  onToggle: () => void;
}): ReactElement {
  const compareSelection = usePlansStore((s) => s.compareSelection);
  const toggleCompare = usePlansStore((s) => s.toggleCompare);
  const removePlan = usePlansStore((s) => s.removePlan);
  const selected = compareSelection.includes(plan.id);
  return (
    <li className="rounded-lg bg-surface p-lg shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-md">
        <div>
          <h3 className="text-body font-semibold text-primary">{plan.name ?? "Untitled plan"}</h3>
          <p className="text-label text-secondary">
            {usd(plan.inputs.amount)} · {plan.inputs.risk_profile} · {plan.inputs.horizon_years}y
            {" — saved "}
            {shortDate(plan.created_at)} · data as of {shortDate(plan.data_as_of)}
          </p>
        </div>
        <div className="flex gap-sm">
          <button
            type="button"
            onClick={onToggle}
            className="rounded-md px-sm py-sm text-label font-medium text-accent hover:bg-accent/10"
          >
            {expanded ? "Hide" : "View"}
          </button>
          <button
            type="button"
            aria-pressed={selected}
            onClick={() => toggleCompare(plan.id)}
            className={`rounded-md px-sm py-sm text-label font-medium ${
              selected ? "bg-accent text-surface" : "text-accent hover:bg-accent/10"
            }`}
          >
            Compare
          </button>
          <button
            type="button"
            onClick={() => void removePlan(plan.id)}
            className="rounded-md px-sm py-sm text-label font-medium text-secondary hover:bg-secondary/10"
          >
            Delete
          </button>
        </div>
      </div>
    </li>
  );
}

function Expanded({ id }: { id: string }): ReactElement {
  const record: PlanRecord | undefined = usePlansStore((s) => s.records[id]);
  if (record === undefined) {
    return <p className="text-body text-secondary">Loading snapshot…</p>;
  }
  return <PlanSummary plan={record.output} />;
}

export default function SavedPlans(): ReactElement {
  const plans = usePlansStore((s) => s.plans);
  const isLoading = usePlansStore((s) => s.isLoading);
  const error = usePlansStore((s) => s.error);
  const compareSelection = usePlansStore((s) => s.compareSelection);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    void usePlansStore.getState().loadPlans();
  }, []);

  const toggle = (id: string): void => {
    const next = expandedId === id ? null : id;
    setExpandedId(next);
    if (next !== null) void usePlansStore.getState().loadPlan(next);
  };

  return (
    <div className="flex flex-col gap-lg">
      <h2 className="text-h2 font-semibold text-primary">Saved plans</h2>
      {error !== null && (
        <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
          {error}
        </p>
      )}
      {isLoading && plans.length === 0 ? (
        <p className="text-body text-secondary">Loading saved plans…</p>
      ) : plans.length === 0 ? (
        <p className="text-body text-secondary">
          No saved plans yet — build one here or ask the agent to save one.
        </p>
      ) : (
        <ul className="flex flex-col gap-md">
          {plans.map((plan) => (
            <Row
              key={plan.id}
              plan={plan}
              expanded={expandedId === plan.id}
              onToggle={() => toggle(plan.id)}
            />
          ))}
        </ul>
      )}
      {expandedId !== null && <Expanded id={expandedId} />}
      {compareSelection.length === COMPARE_LIMIT && <PlanCompare />}
    </div>
  );
}
