/** zustand store for saved plans: snapshot summaries, cached full records, and
 * the compare-view selection (§4). Snapshots are immutable (R16), so records
 * are cached by id and only ever inserted or removed.
 */

import { create } from "zustand";
import { deletePlan, errorMessage, fetchPlan, fetchPlans } from "../api/client";
import type { PlanRecord, SavedPlanSummary } from "../types/domain";

/** The compare view renders exactly two snapshots side by side (§15). */
export const COMPARE_LIMIT = 2;

interface PlansState {
  plans: SavedPlanSummary[];
  records: Record<string, PlanRecord>;
  compareSelection: string[];
  isLoading: boolean;
  error: string | null;
  loadPlans: () => Promise<void>;
  loadPlan: (id: string) => Promise<void>;
  removePlan: (id: string) => Promise<void>;
  toggleCompare: (id: string) => void;
  setPlans: (plans: SavedPlanSummary[]) => void;
  ingestRecord: (record: PlanRecord) => void;
}

/** Everything in a record except the full output — the GET /api/plans row shape. */
function toSummary(record: PlanRecord): SavedPlanSummary {
  return {
    id: record.id,
    name: record.name,
    created_at: record.created_at,
    inputs: record.inputs,
    data_as_of: record.data_as_of,
  };
}

function without(records: Record<string, PlanRecord>, id: string): Record<string, PlanRecord> {
  const next = { ...records };
  delete next[id];
  return next;
}

export const usePlansStore = create<PlansState>()((set, get) => ({
  plans: [],
  records: {},
  compareSelection: [],
  isLoading: false,
  error: null,

  loadPlans: async (): Promise<void> => {
    set({ isLoading: true, error: null });
    try {
      const { plans } = await fetchPlans();
      set({ plans, isLoading: false });
    } catch (err) {
      set({ error: errorMessage(err), isLoading: false });
    }
  },

  loadPlan: async (id: string): Promise<void> => {
    if (id in get().records) return; // immutable snapshot, cache is authoritative
    try {
      const record = await fetchPlan(id);
      set((s) => ({ records: { ...s.records, [id]: record } }));
    } catch (err) {
      set({ error: errorMessage(err) });
    }
  },

  removePlan: async (id: string): Promise<void> => {
    try {
      await deletePlan(id);
    } catch (err) {
      set({ error: errorMessage(err) });
      return;
    }
    set((s) => ({
      plans: s.plans.filter((p) => p.id !== id),
      records: without(s.records, id),
      compareSelection: s.compareSelection.filter((c) => c !== id),
    }));
  },

  toggleCompare: (id: string): void => {
    set((s) => ({
      compareSelection: s.compareSelection.includes(id)
        ? s.compareSelection.filter((c) => c !== id)
        : [...s.compareSelection, id].slice(-COMPARE_LIMIT),
    }));
  },

  setPlans: (plans: SavedPlanSummary[]): void => set({ plans }),

  ingestRecord: (record: PlanRecord): void => {
    set((s) => ({
      records: { ...s.records, [record.id]: record },
      plans: [toSummary(record), ...s.plans.filter((p) => p.id !== record.id)],
    }));
  },
}));
