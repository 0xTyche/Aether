/** Latest-price-per-asset store. */

import { create } from "zustand";

import type { PriceTick } from "../types/api";

export interface PriceSnapshot {
  asset_id: string;
  price: number;
  ts: string;
  source: string;
  /** Server timestamp of when this snapshot last changed locally. */
  receivedAt: number;
}

interface PricesState {
  latest: Record<string, PriceSnapshot>;
  setInitial: (ticks: PriceTick[]) => void;
  applyUpdates: (ticks: PriceTick[]) => void;
  get: (assetId: string) => PriceSnapshot | undefined;
}

function tickToSnapshot(t: PriceTick): PriceSnapshot {
  return {
    asset_id: t.asset_id,
    price: Number(t.price),
    ts: t.ts,
    source: t.source,
    receivedAt: Date.now(),
  };
}

export const usePricesStore = create<PricesState>((set, get) => ({
  latest: {},

  setInitial: (ticks) =>
    set(() => ({
      latest: Object.fromEntries(
        ticks.map((t) => [t.asset_id, tickToSnapshot(t)]),
      ),
    })),

  applyUpdates: (ticks) =>
    set((state) => {
      const next = { ...state.latest };
      for (const t of ticks) {
        const prev = next[t.asset_id];
        if (prev && prev.ts >= t.ts) continue; // stale update
        next[t.asset_id] = tickToSnapshot(t);
      }
      return { latest: next };
    }),

  get: (assetId) => get().latest[assetId],
}));
