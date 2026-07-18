/** Narrow the events store down to the user-selected window.
 *
 *  Two selection modes share one setting:
 *    - a positive minute count → events younger than that age
 *    - LATEST_N_WINDOW         → the newest LATEST_N_COUNT events, any age
 *
 *  The time mode re-runs every 30s on a wall-clock tick so events age out
 *  of the window without a user action. The count mode has no such cutoff,
 *  so it deliberately ignores the tick.
 */

import { useEffect, useMemo, useState } from "react";

import { useEventsStore } from "../store/events";
import { LATEST_N_COUNT, LATEST_N_WINDOW, useUIStore } from "../store/ui";
import type { Event } from "../types/api";

export function useEventsInWindow(): Event[] {
  const events = useEventsStore((s) => s.events);
  const windowMin = useUIStore((s) => s.eventWindowMin);

  // Wall-clock tick so age-out happens without a price/event arriving.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(id);
  }, []);

  return useMemo(() => {
    if (windowMin === LATEST_N_WINDOW) {
      return [...events]
        .sort((a, b) => +new Date(b.occurred_at) - +new Date(a.occurred_at))
        .slice(0, LATEST_N_COUNT);
    }
    const cutoff = now - windowMin * 60_000;
    return events.filter((e) => +new Date(e.occurred_at) >= cutoff);
  }, [events, windowMin, now]);
}
