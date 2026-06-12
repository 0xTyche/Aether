/** UI-state store: highlighted regions, connection status, panel widths. */

import { create } from "zustand";
import { persist, type PersistOptions } from "zustand/middleware";

export const PANEL_MIN_WIDTH = 200;
export const PANEL_MAX_WIDTH = 600;
export const MAP_MIN_WIDTH = 400;
const HANDLE_SLACK_PX = 8; // 2 × 4px resize handles take some grid space too

interface UIState {
  connected: boolean;
  setConnected: (v: boolean) => void;

  highlightedRegions: Set<string>;
  toggleRegion: (id: string) => void;
  clearRegions: () => void;

  leftWidth: number;
  rightWidth: number;
  /** Returns the actually-applied value after clamping + map-min guard. */
  setLeftWidth: (w: number) => number;
  setRightWidth: (w: number) => number;
}

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function viewportWidth(): number {
  if (typeof window === "undefined") return 1920;
  return window.innerWidth;
}

/**
 * Persist only the panel widths. Set / regions are intentionally session-
 * only — they reset on reload so the UI starts from a known clean state.
 */
type Persisted = Pick<UIState, "leftWidth" | "rightWidth">;
const persistOpts: PersistOptions<UIState, Persisted> = {
  name: "aether:panels",
  partialize: (state) => ({
    leftWidth: state.leftWidth,
    rightWidth: state.rightWidth,
  }),
  version: 1,
};

export const useUIStore = create<UIState>()(
  persist(
    (set, get) => ({
      connected: false,
      setConnected: (v) => set(() => ({ connected: v })),

      highlightedRegions: new Set<string>(),
      toggleRegion: (id) =>
        set((state) => {
          const next = new Set(state.highlightedRegions);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return { highlightedRegions: next };
        }),
      clearRegions: () =>
        set(() => ({ highlightedRegions: new Set<string>() })),

      leftWidth: 320,
      rightWidth: 360,

      setLeftWidth: (w) => {
        const clamped = clamp(w, PANEL_MIN_WIDTH, PANEL_MAX_WIDTH);
        const { rightWidth } = get();
        const centerLeft = viewportWidth() - clamped - rightWidth - HANDLE_SLACK_PX;
        if (centerLeft < MAP_MIN_WIDTH) return get().leftWidth; // reject
        set({ leftWidth: clamped });
        return clamped;
      },

      setRightWidth: (w) => {
        const clamped = clamp(w, PANEL_MIN_WIDTH, PANEL_MAX_WIDTH);
        const { leftWidth } = get();
        const centerLeft = viewportWidth() - leftWidth - clamped - HANDLE_SLACK_PX;
        if (centerLeft < MAP_MIN_WIDTH) return get().rightWidth; // reject
        set({ rightWidth: clamped });
        return clamped;
      },
    }),
    persistOpts,
  ),
);
