/** Composer attachment row: 📎 toggle opening a saved-plans picker, and the
 * pending-attachment chip with its remove ×. Picking loads the full snapshot
 * (immutable, cached — R16) and attaches it; a failed load renders an inline
 * alert inside the picker (R28) and attaches nothing.
 */

import { useState } from "react";
import type { ReactElement } from "react";
import { usd } from "../../lib/format";
import { useChatStore } from "../../state/chatStore";
import { usePlansStore } from "../../state/plansStore";
import type { SavedPlanSummary } from "../../types/domain";

function PlanOption({ plan, onPick }: {
  plan: SavedPlanSummary;
  onPick: (id: string) => void;
}): ReactElement {
  return (
    <li>
      <button
        type="button"
        onClick={() => onPick(plan.id)}
        className="w-full rounded-md px-sm py-sm text-left hover:bg-accent/10"
      >
        <span className="block text-label font-medium text-primary">
          {plan.name ?? "Untitled plan"}
        </span>
        <span className="block text-label text-secondary">
          {usd(plan.inputs.amount)} · {plan.inputs.risk_profile} · {plan.inputs.horizon_years}y
        </span>
      </button>
    </li>
  );
}

export default function AttachmentPicker(): ReactElement {
  const [open, setOpen] = useState(false);
  const [pickError, setPickError] = useState<string | null>(null);
  const pending = useChatStore((s) => s.pendingAttachment);
  const clearAttachment = useChatStore((s) => s.clearAttachment);
  const plans = usePlansStore((s) => s.plans);
  const isLoading = usePlansStore((s) => s.isLoading);

  const toggle = (): void => {
    setPickError(null);
    setOpen(!open);
    if (!open && usePlansStore.getState().plans.length === 0) {
      void usePlansStore.getState().loadPlans();
    }
  };

  // On failure the picker stays open so the alert is visible where the user
  // just clicked (R28); it only closes once a snapshot is actually attached.
  const pick = async (id: string): Promise<void> => {
    setPickError(null);
    await usePlansStore.getState().loadPlan(id);
    const record = usePlansStore.getState().records[id];
    if (record === undefined) {
      setPickError(usePlansStore.getState().error ?? "Could not load that plan.");
      return;
    }
    useChatStore.getState().attachPlan(record);
    setOpen(false);
  };

  return (
    <div className="flex flex-col gap-sm">
      {open && (
        <div className="flex flex-col gap-sm rounded-md border border-secondary/20 bg-surface p-sm shadow-md">
          {pickError !== null && (
            <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
              {pickError}
            </p>
          )}
          {plans.length === 0 ? (
            <p className="px-sm py-sm text-label text-secondary">
              {isLoading ? "Loading saved plans…" : "No saved plans yet — build and save one first."}
            </p>
          ) : (
            <ul className="flex max-h-48 flex-col gap-sm overflow-y-auto">
              {plans.map((plan) => (
                <PlanOption key={plan.id} plan={plan} onPick={(id) => void pick(id)} />
              ))}
            </ul>
          )}
        </div>
      )}
      <div className="flex items-center gap-sm">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          aria-label="Attach a saved plan"
          className="rounded-md px-sm py-sm text-label font-medium text-accent hover:bg-accent/10"
        >
          📎 Attach plan
        </button>
        {pending !== null && (
          <span className="flex items-center gap-sm rounded-sm bg-accent/10 px-sm text-label text-accent">
            📎 {pending.name}
            <button
              type="button"
              onClick={clearAttachment}
              aria-label="Remove attachment"
              className="font-semibold"
            >
              ×
            </button>
          </span>
        )}
      </div>
    </div>
  );
}
