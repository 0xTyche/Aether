/** Events store — keeps the most recent N events plus the currently selected. */

import { create } from "zustand";

import type { Event } from "../types/api";

const MAX_KEEP = 200;

interface EventsState {
  events: Event[];
  selectedId: string | null;
  setInitial: (list: Event[]) => void;
  upsert: (event: Event) => void;
  select: (id: string | null) => void;
  selected: () => Event | null;
}

export const useEventsStore = create<EventsState>((set, get) => ({
  events: [],
  selectedId: null,

  setInitial: (list) =>
    set((state) => {
      const sorted = [...list].sort(
        (a, b) => +new Date(b.occurred_at) - +new Date(a.occurred_at),
      );
      return {
        events: sorted,
        // Only auto-select if user hasn't already picked something.
        selectedId: state.selectedId ?? sorted[0]?.id ?? null,
      };
    }),

  upsert: (event) =>
    set((state) => {
      const without = state.events.filter((e) => e.id !== event.id);
      const next = [event, ...without].slice(0, MAX_KEEP);
      // Auto-select the first event ever seen, and any newly-arriving
      // high-severity event so the user can't miss it.
      const isNew = !state.events.some((e) => e.id === event.id);
      let nextSelectedId = state.selectedId;
      if (isNew) {
        if (state.selectedId == null || event.severity === "high") {
          nextSelectedId = event.id;
        }
      }
      return { events: next, selectedId: nextSelectedId };
    }),

  select: (id) => set(() => ({ selectedId: id })),

  selected: () => {
    const { events, selectedId } = get();
    if (!selectedId) return null;
    return events.find((e) => e.id === selectedId) ?? null;
  },
}));
