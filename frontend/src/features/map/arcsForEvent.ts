/** Build deck.gl ArcLayer source/target pairs for one event.
 *
 * Source = the event's origin lat/lng. Each target is a unique country in
 * the predictions list (mapped via the assets master). Predictions whose
 * asset has no country / lat / lng get skipped.
 */

import type { Event } from "../../types/api";
import type { Asset } from "../../types/api";

export interface ArcDatum {
  source: [number, number];
  target: [number, number];
  asset_id: string;
  direction: "up" | "down" | "neutral";
}

export function buildArcsForEvent(
  event: Event | null,
  assetsById: Record<string, Asset>,
): ArcDatum[] {
  if (!event || event.origin_lat == null || event.origin_lng == null) return [];
  const source: [number, number] = [event.origin_lng, event.origin_lat];

  const seenTargets = new Set<string>();
  const out: ArcDatum[] = [];
  for (const p of event.predictions) {
    const a = assetsById[p.asset_id];
    if (!a || a.lat == null || a.lng == null) continue;
    // Don't draw an arc into the origin itself.
    if (a.lat === event.origin_lat && a.lng === event.origin_lng) continue;
    const key = `${a.lng},${a.lat}`;
    if (seenTargets.has(key)) continue;
    seenTargets.add(key);
    out.push({
      source,
      target: [a.lng, a.lat],
      asset_id: p.asset_id,
      direction: p.direction,
    });
  }
  return out;
}
