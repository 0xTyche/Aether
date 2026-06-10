/** Thin REST client for the dashboard. Uses the Vite dev proxy in dev. */

import type { Asset, Event, PriceTick, Region } from "../types/api";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`GET ${path}: HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => getJson<{ status: string; version: string }>("/api/health"),
  listAssets: () => getJson<Asset[]>("/api/assets"),
  listRegions: () => getJson<Region[]>("/api/regions"),
  listEvents: (limit = 50) => getJson<Event[]>(`/api/events?limit=${limit}`),
  getEvent: (id: string) => getJson<Event>(`/api/events/${id}`),
  latestPrices: () => getJson<PriceTick[]>("/api/prices/latest"),
};
