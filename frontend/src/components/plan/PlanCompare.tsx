/** Side-by-side comparison of two immutable saved snapshots (§15): each column
 * shows the snapshot's inputs and freshness header above its stored output —
 * a later enrichment refresh never changes what is rendered here (R16).
 */

import { useEffect } from "react";
import type { ReactElement } from "react";
import { shortDate, usd } from "../../lib/format";
import { usePlansStore } from "../../state/plansStore";
import type { PlanRecord } from "../../types/domain";
import PlanSummary from "./PlanSummary";

function Column({ id }: { id: string }): ReactElement {
  const record: PlanRecord | undefined = usePlansStore((s) => s.records[id]);
  if (record === undefined) {
    return (
      <div className="rounded-lg bg-surface p-lg shadow-sm">
        <p className="text-body text-secondary">Loading snapshot…</p>
      </div>
    );
  }
  return (
    <div className="flex min-w-0 flex-col gap-lg">
      <div className="rounded-lg bg-surface p-lg shadow-sm">
        <h4 className="text-body font-semibold text-primary">{record.name ?? "Untitled plan"}</h4>
        <p className="mt-sm text-label text-secondary">
          {usd(record.inputs.amount)} · {record.inputs.risk_profile} ·{" "}
          {record.inputs.horizon_years}y — saved {shortDate(record.created_at)} · data as of{" "}
          {shortDate(record.data_as_of)}
        </p>
      </div>
      <PlanSummary plan={record.output} />
    </div>
  );
}

export default function PlanCompare(): ReactElement | null {
  const selection = usePlansStore((s) => s.compareSelection);
  const loadPlan = usePlansStore((s) => s.loadPlan);

  useEffect(() => {
    for (const id of selection) void loadPlan(id);
  }, [selection, loadPlan]);

  if (selection.length < 2) return null;
  return (
    <section aria-label="Plan comparison" className="flex flex-col gap-md">
      <h2 className="text-h2 font-semibold text-primary">Compare snapshots</h2>
      <div className="grid gap-lg xl:grid-cols-2">
        {selection.map((id) => (
          <Column key={id} id={id} />
        ))}
      </div>
    </section>
  );
}
