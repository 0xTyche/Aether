/** Filter the events store down to those that occurred within
 *  the user-selected time window.
 *
 *  The hook re-runs every 30s on a wall-clock tick so events that
 *  age past the window naturally drop out without a user action.
 */

import { useEffect, useMemo, useState } from "react";

import { useEventsStore } from "../store/events";
import { useUIStore } from "../store/ui";
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
    const cutoff = now - windowMin * 60_000;
    return events.filter((e) => +new Date(e.occurred_at) >= cutoff);
  }, [events, windowMin, now]);
}
