/** Asset master + regions master, loaded once at boot. */

import { create } from "zustand";

import type { Asset, Region } from "../types/api";

interface AssetsState {
  assets: Asset[];
  byId: Record<string, Asset>;
  regions: Region[];
  regionsById: Record<string, Region>;
  setAssets: (a: Asset[]) => void;
  setRegions: (r: Region[]) => void;
}

export const useAssetsStore = create<AssetsState>((set) => ({
  assets: [],
  byId: {},
  regions: [],
  regionsById: {},
  setAssets: (a) =>
    set(() => ({
      assets: a,
      byId: Object.fromEntries(a.map((x) => [x.id, x])),
    })),
  setRegions: (r) =>
    set(() => ({
      regions: r,
      regionsById: Object.fromEntries(r.map((x) => [x.id, x])),
    })),
}));
