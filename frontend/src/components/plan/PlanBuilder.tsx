/** Manual plan form: amount, risk profile, and horizon → POST /api/plan, with
 * the result rendered by PlanSummary and a save action that persists an
 * immutable snapshot via POST /api/plans (R16). Infeasible inputs surface the
 * engine's reason, never an exception (R12).
 */

import { useState } from "react";
import type { ReactElement } from "react";
import { buildPlan, errorMessage, savePlan } from "../../api/client";
import { usePlansStore } from "../../state/plansStore";
import type { Plan, RiskProfile } from "../../types/domain";
import PlanSummary from "./PlanSummary";

const RISK_PROFILES: readonly RiskProfile[] = ["conservative", "balanced", "aggressive"];

const FIELD_CLASS =
  "rounded-md border border-secondary/20 bg-surface px-sm py-sm text-body text-primary focus:border-accent focus:outline-none";

const BUTTON_PRIMARY =
  "rounded-md bg-accent px-md py-sm text-body font-medium text-surface shadow-sm transition-opacity disabled:opacity-50";

export default function PlanBuilder(): ReactElement {
  const [amount, setAmount] = useState("2000");
  const [risk, setRisk] = useState<RiskProfile>("balanced");
  const [horizon, setHorizon] = useState("5");
  const [name, setName] = useState("");
  const [plan, setPlan] = useState<Plan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAs, setSavedAs] = useState<string | null>(null);
  const ingestRecord = usePlansStore((s) => s.ingestRecord);

  const request = {
    amount: Number(amount),
    risk_profile: risk,
    horizon_years: Number(horizon),
  };

  const build = async (): Promise<void> => {
    setBusy(true);
    setError(null);
    setSavedAs(null);
    try {
      setPlan(await buildPlan(request));
    } catch (err) {
      setError(errorMessage(err));
    }
    setBusy(false);
  };

  const save = async (): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      const record = await savePlan({ ...request, name: name.trim() || undefined });
      ingestRecord(record);
      setSavedAs(record.name ?? record.id);
    } catch (err) {
      setError(errorMessage(err));
    }
    setBusy(false);
  };

  return (
    <div className="flex flex-col gap-lg">
      <form
        className="flex flex-wrap items-end gap-md rounded-lg bg-surface p-lg shadow-sm"
        onSubmit={(event) => {
          event.preventDefault();
          void build();
        }}
      >
        <label className="flex flex-col gap-sm text-label text-secondary">
          Amount (USD)
          <input type="number" min={100} step={10} required value={amount} onChange={(e) => setAmount(e.target.value)} className={`${FIELD_CLASS} w-32`} />
        </label>
        <label className="flex flex-col gap-sm text-label text-secondary">
          Risk profile
          <select
            value={risk}
            onChange={(e) => {
              const value = RISK_PROFILES.find((p) => p === e.target.value);
              if (value !== undefined) setRisk(value);
            }}
            className={FIELD_CLASS}
          >
            {RISK_PROFILES.map((profile) => (
              <option key={profile} value={profile}>
                {profile}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-sm text-label text-secondary">
          Horizon (years)
          <input type="number" min={1} max={30} required value={horizon} onChange={(e) => setHorizon(e.target.value)} className={`${FIELD_CLASS} w-24`} />
        </label>
        <button type="submit" disabled={busy} className={BUTTON_PRIMARY}>
          Build plan
        </button>
      </form>
      {error !== null && (
        <p role="alert" className="rounded-md bg-primary px-md py-sm text-label text-surface">
          {error}
        </p>
      )}
      {plan !== null && plan.feasible && (
        <div className="flex flex-wrap items-end gap-md rounded-lg bg-surface p-lg shadow-sm">
          <label className="flex min-w-0 flex-1 flex-col gap-sm text-label text-secondary">
            Snapshot name (optional)
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Balanced $2k" className={FIELD_CLASS} />
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
      {plan !== null && <PlanSummary plan={plan} />}
    </div>
  );
}
