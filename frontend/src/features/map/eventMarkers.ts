/** Pure transforms for event-marker rendering. */

import type { Event } from "../../types/api";
import type { RGBA } from "./countryStyle";

export interface EventMarker {
  eventId: string;
  lng: number;
  lat: number;
  severity: "low" | "medium" | "high";
}

const BASE_RADIUS: Record<EventMarker["severity"], number> = {
  high: 12,
  medium: 8,
  low: 6,
};

export const MARKER_COLOR: Record<EventMarker["severity"], RGBA> = {
  high: [248, 113, 113, 220],   // red
  medium: [250, 204, 21, 220],  // yellow/amber
  low: [74, 222, 128, 220],     // green
};

export function markersFromEvents(events: Event[]): EventMarker[] {
  const out: EventMarker[] = [];
  for (const e of events) {
    if (e.origin_lat == null || e.origin_lng == null) continue;
    out.push({
      eventId: e.id,
      lng: e.origin_lng,
      lat: e.origin_lat,
      severity: e.severity,
    });
  }
  return out;
}

/** Radius in pixels. `phaseSeconds` is a monotonic timer used to make
 *  high-severity markers pulse at ~1 Hz. */
export function radiusFor(m: EventMarker, phaseSeconds: number): number {
  const base = BASE_RADIUS[m.severity];
  if (m.severity !== "high") return base;
  // Simple sin pulse 9 → 15 → 9 px at 1 Hz; offset by event hash so
  // a cluster of markers doesn't pulse in lockstep.
  const offset = hashOffset(m.eventId);
  return base + Math.sin((phaseSeconds + offset) * Math.PI * 2) * 3;
}

function hashOffset(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
  // Map to [0, 1).
  return (Math.abs(h) % 1000) / 1000;
}
