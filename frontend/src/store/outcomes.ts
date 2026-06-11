/** Official impact outcomes keyed by (event_id, asset_id). */

import { create } from "zustand";

import type { OutcomeOnWire } from "../types/api";

export interface OfficialOutcome {
  event_id: string;
  asset_id: string;
  predicted_direction: "up" | "down" | "neutral";
  t0_price: number | null;
  t1_price: number | null;
  actual_pct: number | null;
  actual_direction: "up" | "down" | "flat" | null;
  accuracy: "hit" | "miss" | "partial" | null;
}

function outcomeKey(eventId: string, assetId: string): string {
  return `${eventId}::${assetId}`;
}

function fromWire(o: OutcomeOnWire): OfficialOutcome {
  return {
    event_id: o.event_id,
    asset_id: o.asset_id,
    predicted_direction: o.predicted_direction,
    t0_price: o.t0_price == null ? null : Number(o.t0_price),
    t1_price: o.t1_price == null ? null : Number(o.t1_price),
    actual_pct: o.actual_pct,
    actual_direction: o.actual_direction,
    accuracy: o.accuracy,
  };
}

interface OutcomesState {
  byKey: Record<string, OfficialOutcome>;
  apply: (outcomes: OutcomeOnWire[]) => void;
  get: (eventId: string, assetId: string) => OfficialOutcome | undefined;
}

export const useOutcomesStore = create<OutcomesState>((set, get) => ({
  byKey: {},

  apply: (outcomes) =>
    set((state) => {
      const next = { ...state.byKey };
      for (const w of outcomes) {
        next[outcomeKey(w.event_id, w.asset_id)] = fromWire(w);
      }
      return { byKey: next };
    }),

  get: (eventId, assetId) => get().byKey[outcomeKey(eventId, assetId)],
}));
