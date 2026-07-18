/** Snapshot loading: store fan-out, retry-on-failure, refetch on WS reconnect. */

import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useAssetsStore } from "../../store/assets";
import { useEventsStore } from "../../store/events";
import { usePricesStore } from "../../store/prices";
import { useUIStore } from "../../store/ui";
import { api } from "../api";
import { loadSnapshot, useBootstrap } from "../useBootstrap";

/** Mirrors RETRY_BASE_MS in useBootstrap — kept local so the test asserts
 *  the contract (first retry lands at 2s) rather than reading the impl. */
const RETRY_BASE_MS = 2_000;

/** Captures the options the hook hands to WSClient so we can drive onOpen. */
const wsInstances: { opts: ConstructorParameters<typeof import("../ws").WSClient>[0] }[] = [];

vi.mock("../ws", () => ({
  WSClient: class {
    opts: unknown;
    constructor(opts: unknown) {
      this.opts = opts;
      wsInstances.push({ opts } as never);
    }
    start() {}
    stop() {}
  },
}));

vi.mock("../api", () => ({
  api: {
    listAssets: vi.fn(),
    listRegions: vi.fn(),
    listEvents: vi.fn(),
    latestPrices: vi.fn(),
  },
}));

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function makeEvent(id: string) {
  return {
    id,
    classifier: "rule" as const,
    rule_id: null,
    severity: "low" as const,
    origin_country: null,
    origin_lat: null,
    origin_lng: null,
    affected_regions: null,
    title: id,
    explanation: null,
    analysis: null,
    occurred_at: "2026-06-12T11:00:00Z",
    created_at: "2026-06-12T11:00:00Z",
    predictions: [],
  };
}

function resolveAll() {
  mocked.listAssets.mockResolvedValue([]);
  mocked.listRegions.mockResolvedValue([]);
  mocked.listEvents.mockResolvedValue([makeEvent("a")]);
  mocked.latestPrices.mockResolvedValue([]);
}

beforeEach(() => {
  vi.useFakeTimers();
  wsInstances.length = 0;
  vi.clearAllMocks();
  useEventsStore.setState({ events: [], selectedId: null });
  useUIStore.setState({ snapshotStatus: "loading", connected: false });
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("loadSnapshot", () => {
  it("fans the four responses out into their stores", async () => {
    mocked.listAssets.mockResolvedValue([]);
    mocked.listRegions.mockResolvedValue([]);
    mocked.listEvents.mockResolvedValue([makeEvent("a"), makeEvent("b")]);
    mocked.latestPrices.mockResolvedValue([]);

    await loadSnapshot(200);

    expect(useEventsStore.getState().events).toHaveLength(2);
    expect(useAssetsStore.getState().byId).toBeDefined();
    expect(usePricesStore.getState()).toBeDefined();
  });

  it("rejects if any of the four calls rejects", async () => {
    mocked.listAssets.mockResolvedValue([]);
    mocked.listRegions.mockRejectedValue(new Error("boom"));
    mocked.listEvents.mockResolvedValue([]);
    mocked.latestPrices.mockResolvedValue([]);

    await expect(loadSnapshot(200)).rejects.toThrow("boom");
  });
});

describe("useBootstrap", () => {
  it("marks the snapshot ready once the first load lands", async () => {
    resolveAll();
    renderHook(() => useBootstrap());
    await vi.runOnlyPendingTimersAsync();

    expect(useUIStore.getState().snapshotStatus).toBe("ready");
    expect(useEventsStore.getState().events).toHaveLength(1);
  });

  it("flags failure and retries with backoff until it succeeds", async () => {
    mocked.listAssets.mockRejectedValue(new Error("backend down"));
    mocked.listRegions.mockRejectedValue(new Error("backend down"));
    mocked.listEvents.mockRejectedValue(new Error("backend down"));
    mocked.latestPrices.mockRejectedValue(new Error("backend down"));

    renderHook(() => useBootstrap());
    await vi.advanceTimersByTimeAsync(0);
    expect(useUIStore.getState().snapshotStatus).toBe("failed");
    expect(mocked.listEvents).toHaveBeenCalledTimes(1);

    // Backend comes back; the pending 2s retry should pick it up.
    resolveAll();
    await vi.advanceTimersByTimeAsync(RETRY_BASE_MS);

    expect(mocked.listEvents).toHaveBeenCalledTimes(2);
    expect(useUIStore.getState().snapshotStatus).toBe("ready");
    expect(useEventsStore.getState().events).toHaveLength(1);
  });

  it("does not refetch on the first WS open", async () => {
    resolveAll();
    renderHook(() => useBootstrap());
    await vi.advanceTimersByTimeAsync(0);
    expect(mocked.listEvents).toHaveBeenCalledTimes(1);

    wsInstances[0].opts.onOpen?.();
    await vi.advanceTimersByTimeAsync(0);

    expect(mocked.listEvents).toHaveBeenCalledTimes(1);
  });

  it("refetches on a WS reconnect to fill the gap left by the outage", async () => {
    resolveAll();
    renderHook(() => useBootstrap());
    await vi.advanceTimersByTimeAsync(0);

    const { onOpen, onClose } = wsInstances[0].opts;
    onOpen?.(); // first connection
    onClose?.();
    onOpen?.(); // reconnect
    await vi.advanceTimersByTimeAsync(0);

    expect(mocked.listEvents).toHaveBeenCalledTimes(2);
  });

  it("stops retrying after unmount", async () => {
    mocked.listAssets.mockRejectedValue(new Error("down"));
    mocked.listRegions.mockRejectedValue(new Error("down"));
    mocked.listEvents.mockRejectedValue(new Error("down"));
    mocked.latestPrices.mockRejectedValue(new Error("down"));

    const { unmount } = renderHook(() => useBootstrap());
    await vi.advanceTimersByTimeAsync(0);
    expect(mocked.listEvents).toHaveBeenCalledTimes(1);

    unmount();
    await vi.advanceTimersByTimeAsync(60_000);

    expect(mocked.listEvents).toHaveBeenCalledTimes(1);
  });
});
