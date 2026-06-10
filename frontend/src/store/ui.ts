/** UI-state store: which regions are highlighted, connection status, etc. */

import { create } from "zustand";

interface UIState {
  connected: boolean;
  setConnected: (v: boolean) => void;
  highlightedRegions: Set<string>;
  toggleRegion: (id: string) => void;
  clearRegions: () => void;
}

export const useUIStore = create<UIState>((set) => ({
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
}));
