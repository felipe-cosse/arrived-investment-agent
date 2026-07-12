/** Shared catalogue metadata. Refresh actions reload this store so every
 * freshness consumer observes the same current snapshot.
 */

import { create } from "zustand";
import { fetchMeta } from "../api/client";
import type { Meta } from "../types/domain";

interface MetaState {
  meta: Meta | null;
  isLoading: boolean;
  failed: boolean;
  loadMeta: () => Promise<void>;
}

let latestRequest = 0;

export const useMetaStore = create<MetaState>()((set) => ({
  meta: null,
  isLoading: false,
  failed: false,

  loadMeta: async (): Promise<void> => {
    const request = ++latestRequest;
    set({ isLoading: true, failed: false });
    try {
      const meta = await fetchMeta();
      if (request === latestRequest) set({ meta, isLoading: false });
    } catch {
      if (request === latestRequest) set({ isLoading: false, failed: true });
    }
  },
}));
