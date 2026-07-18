/** UI-state store: highlighted regions, connection status, panel widths. */

import { create } from "zustand";
import { persist, type PersistOptions } from "zustand/middleware";

export const PANEL_MIN_WIDTH = 200;
export const PANEL_MAX_WIDTH = 600;
export const MAP_MIN_WIDTH = 400;
const HANDLE_SLACK_PX = 8; // 2 × 4px resize handles take some grid space too

/**
 * Sentinel window meaning "the newest N events regardless of age".
 *
 * Negative so it can share `eventWindowMin` with the real minute values:
 * `setEventWindowMin` already rejects anything outside EVENT_WINDOW_OPTIONS,
 * so listing it here is all the persisted-value migration this needs.
 */
export const LATEST_N_WINDOW = -1;
export const LATEST_N_COUNT = 100;

/**
 * Window options for filtering events on map + news. Positive entries are
 * minutes; LATEST_N_WINDOW selects by count instead of by age.
 */
export const EVENT_WINDOW_OPTIONS: readonly number[] = [
  5,
  30,
  60,
  240,
  1440,
  LATEST_N_WINDOW,
];

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

  eventWindowMin: number;
  setEventWindowMin: (m: number) => void;
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
type Persisted = Pick<UIState, "leftWidth" | "rightWidth" | "eventWindowMin">;
const persistOpts: PersistOptions<UIState, Persisted> = {
  name: "aether:panels",
  partialize: (state) => ({
    leftWidth: state.leftWidth,
    rightWidth: state.rightWidth,
    eventWindowMin: state.eventWindowMin,
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

      eventWindowMin: 60,
      setEventWindowMin: (m) =>
        set(() => {
          const allowed = EVENT_WINDOW_OPTIONS.includes(m) ? m : 60;
          return { eventWindowMin: allowed };
        }),
    }),
    persistOpts,
  ),
);
