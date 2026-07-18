import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useEventsInWindow } from "../useEventsInWindow";
import { useEventsStore } from "../../store/events";
import { LATEST_N_COUNT, LATEST_N_WINDOW, useUIStore } from "../../store/ui";
import type { Event } from "../../types/api";


function makeEvent(id: string, occurredAt: Date, severity: "high" | "medium" | "low" = "medium"): Event {
  return {
    id,
    classifier: "rule",
    rule_id: "test",
    severity,
    origin_country: "JP",
    origin_lat: 35.68,
    origin_lng: 139.7,
    affected_regions: ["g7"],
    title: `Event ${id}`,
    explanation: null,
    analysis: null,
    occurred_at: occurredAt.toISOString(),
    created_at: occurredAt.toISOString(),
    predictions: [],
  };
}


describe("useEventsInWindow", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-06-12T12:00:00Z"));
    useEventsStore.setState({ events: [], selectedId: null });
    useUIStore.setState({ eventWindowMin: 60 });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("filters out events older than the window", () => {
    const within = makeEvent("a", new Date("2026-06-12T11:30:00Z")); // 30m ago
    const tooOld = makeEvent("b", new Date("2026-06-12T10:00:00Z")); // 2h ago
    useEventsStore.setState({ events: [within, tooOld] });
    useUIStore.setState({ eventWindowMin: 60 });

    const { result } = renderHook(() => useEventsInWindow());
    expect(result.current.map((e) => e.id)).toEqual(["a"]);
  });

  it("returns all events when the window is wide enough", () => {
    const a = makeEvent("a", new Date("2026-06-12T11:55:00Z"));
    const b = makeEvent("b", new Date("2026-06-12T08:00:00Z")); // 4h ago
    useEventsStore.setState({ events: [a, b] });
    useUIStore.setState({ eventWindowMin: 1440 }); // 24h

    const { result } = renderHook(() => useEventsInWindow());
    expect(result.current.map((e) => e.id).sort()).toEqual(["a", "b"]);
  });

  it("returns an empty list when nothing is within the window", () => {
    const old = makeEvent("a", new Date("2026-06-12T10:00:00Z"));
    useEventsStore.setState({ events: [old] });
    useUIStore.setState({ eventWindowMin: 5 });

    const { result } = renderHook(() => useEventsInWindow());
    expect(result.current).toEqual([]);
  });

  describe("latest-N window", () => {
    it("keeps events far older than any time window", () => {
      const ancient = makeEvent("old", new Date("2024-01-01T00:00:00Z"));
      useEventsStore.setState({ events: [ancient] });
      useUIStore.setState({ eventWindowMin: LATEST_N_WINDOW });

      const { result } = renderHook(() => useEventsInWindow());
      expect(result.current.map((e) => e.id)).toEqual(["old"]);
    });

    it(`caps the result at ${LATEST_N_COUNT} and orders newest first`, () => {
      const events = Array.from({ length: LATEST_N_COUNT + 20 }, (_, i) =>
        // i=0 is the oldest; each later event is one minute newer.
        makeEvent(`e${i}`, new Date(Date.UTC(2026, 5, 12, 0, i))),
      );
      useEventsStore.setState({ events });
      useUIStore.setState({ eventWindowMin: LATEST_N_WINDOW });

      const { result } = renderHook(() => useEventsInWindow());
      expect(result.current).toHaveLength(LATEST_N_COUNT);
      expect(result.current[0].id).toBe(`e${LATEST_N_COUNT + 19}`);
      expect(result.current.at(-1)?.id).toBe("e20");
    });

    it("does not mutate the store's array order", () => {
      const a = makeEvent("a", new Date("2026-06-12T09:00:00Z"));
      const b = makeEvent("b", new Date("2026-06-12T11:00:00Z"));
      useEventsStore.setState({ events: [a, b] });
      useUIStore.setState({ eventWindowMin: LATEST_N_WINDOW });

      renderHook(() => useEventsInWindow());
      expect(useEventsStore.getState().events.map((e) => e.id)).toEqual(["a", "b"]);
    });
  });
});
