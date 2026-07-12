import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchMeta } from "../api/client";
import type { Meta } from "../types/domain";
import { useMetaStore } from "./metaStore";

vi.mock("../api/client", () => ({ fetchMeta: vi.fn() }));

const META: Meta = {
  offerings: { rows: 12, latest_as_of: "2026-07-11" },
  historical_returns: { rows: 100, latest_month: "2026-06" },
  market_metrics: { rows: 4, latest_as_of: "2026-07-10" },
  plans: { rows: 2 },
};

const fetchMetaMock = vi.mocked(fetchMeta);

beforeEach(() => {
  fetchMetaMock.mockReset();
  useMetaStore.setState({ meta: null, isLoading: false, failed: false });
});

describe("metadata loading", () => {
  it("publishes a refreshed metadata snapshot", async () => {
    fetchMetaMock.mockResolvedValue(META);

    await useMetaStore.getState().loadMeta();

    expect(useMetaStore.getState()).toMatchObject({
      meta: META,
      isLoading: false,
      failed: false,
    });
  });

  it("retains the last snapshot when a refresh fails", async () => {
    useMetaStore.setState({ meta: META });
    fetchMetaMock.mockRejectedValue(new Error("offline"));

    await useMetaStore.getState().loadMeta();

    expect(useMetaStore.getState()).toMatchObject({
      meta: META,
      isLoading: false,
      failed: true,
    });
  });
});
