/** Pure event-matching for landmark hover tooltips.
 *
 *  An event is considered relevant to a landmark if ANY of the
 *  landmark's matcher fields (countries / asset_ids / keywords)
 *  matches a corresponding facet of the event. Keyword match is
 *  case-insensitive substring against `title` + `explanation`.
 */

import type { Event } from "../../types/api";
import type { Landmark } from "./landmarks";

const SEVERITY_RANK: Record<Event["severity"], number> = {
  high: 3,
  medium: 2,
  low: 1,
};

export function isEventRelevant(event: Event, lm: Landmark): boolean {
  if (lm.countries && event.origin_country && lm.countries.includes(event.origin_country)) {
    return true;
  }
  if (lm.asset_ids && event.predictions.some((p) => lm.asset_ids!.includes(p.asset_id))) {
    return true;
  }
  if (lm.keywords && lm.keywords.length > 0) {
    const hay = `${event.title} ${event.explanation ?? ""}`.toLowerCase();
    if (lm.keywords.some((k) => hay.includes(k.toLowerCase()))) return true;
  }
  return false;
}

export function eventsForLandmark(
  events: Event[],
  lm: Landmark,
  limit = 5,
): Event[] {
  return events
    .filter((e) => isEventRelevant(e, lm))
    .sort((a, b) => {
      const sevDelta = SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity];
      if (sevDelta !== 0) return sevDelta;
      return +new Date(b.occurred_at) - +new Date(a.occurred_at);
    })
    .slice(0, limit);
}
