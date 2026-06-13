import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useEventsInWindow } from "../useEventsInWindow";
import { useEventsStore } from "../../store/events";
import { useUIStore } from "../../store/ui";
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
});
