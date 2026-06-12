import { describe, expect, it } from "vitest";

import {
  MARKER_COLOR,
  markersFromEvents,
  radiusFor,
} from "../eventMarkers";
import type { Event } from "../../../types/api";


function ev(id: string, lat: number | null, lng: number | null, sev: "high" | "medium" | "low" = "high"): Event {
  return {
    id, classifier: "rule", rule_id: "test", severity: sev,
    origin_country: "JP", origin_lat: lat, origin_lng: lng,
    affected_regions: ["g7"], title: id, explanation: null,
    occurred_at: "2026-06-12T12:00:00Z", created_at: "2026-06-12T12:00:00Z",
    predictions: [],
  };
}


describe("markersFromEvents", () => {
  it("skips events without coordinates", () => {
    const m = markersFromEvents([
      ev("a", 35, 139),
      ev("b", null, null),
      ev("c", 0, 0),     // valid, equator/prime meridian
      ev("d", 40, null),
    ]);
    expect(m.map((x) => x.eventId).sort()).toEqual(["a", "c"]);
  });

  it("propagates severity for color lookup", () => {
    const m = markersFromEvents([ev("a", 1, 2, "low")]);
    expect(m[0].severity).toBe("low");
    expect(MARKER_COLOR.low[0]).toBe(74);   // R of green
    expect(MARKER_COLOR.high[0]).toBe(248); // R of red
  });
});


describe("radiusFor", () => {
  it("returns the constant base for low/medium regardless of phase", () => {
    const low = { eventId: "x", lat: 0, lng: 0, severity: "low" as const };
    const med = { eventId: "x", lat: 0, lng: 0, severity: "medium" as const };
    expect(radiusFor(low, 0)).toBe(6);
    expect(radiusFor(low, 1.234)).toBe(6);
    expect(radiusFor(med, 0)).toBe(8);
    expect(radiusFor(med, 99)).toBe(8);
  });

  it("pulses high severity within [9, 15] px", () => {
    const high = { eventId: "x", lat: 0, lng: 0, severity: "high" as const };
    // sample over a full cycle
    let min = Infinity, max = -Infinity;
    for (let i = 0; i < 60; i++) {
      const r = radiusFor(high, i / 60);
      if (r < min) min = r;
      if (r > max) max = r;
    }
    expect(min).toBeGreaterThanOrEqual(8.99);
    expect(max).toBeLessThanOrEqual(15.01);
    expect(max - min).toBeGreaterThan(3); // actually pulses
  });

  it("different event ids have phase-offset pulses", () => {
    const a = { eventId: "aaa", lat: 0, lng: 0, severity: "high" as const };
    const b = { eventId: "zzz", lat: 0, lng: 0, severity: "high" as const };
    // At t=0 they should generally not be equal (offset by hash).
    expect(radiusFor(a, 0)).not.toBeCloseTo(radiusFor(b, 0), 3);
  });
});
