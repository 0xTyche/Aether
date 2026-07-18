/** Hook that keeps the REST snapshot loaded and the WS open while mounted. */

import { useEffect } from "react";

import { useAssetsStore } from "../store/assets";
import { useEventsStore } from "../store/events";
import { useOutcomesStore } from "../store/outcomes";
import { usePricesStore } from "../store/prices";
import { useUIStore } from "../store/ui";
import { api } from "./api";
import { WSClient } from "./ws";

/**
 * How many past events to pull on mount. Must exceed LATEST_N_COUNT so the
 * count-based window is always fully satisfied from the store; the surplus
 * also covers the wider time windows. The widest window (24h) can still
 * outgrow this as event volume rises — filling that gap needs paging, not
 * a bigger number.
 */
const EVENT_PREFETCH_COUNT = 200;

const RETRY_BASE_MS = 2_000;
const RETRY_MAX_MS = 30_000;

/**
 * Load one slice into its store. Never rejects — it reports the slice name on
 * failure so one dead endpoint can't discard its siblings' responses.
 */
async function loadSlice<T>(
  name: string,
  fetch: () => Promise<T>,
  apply: (data: T) => void,
): Promise<string | null> {
  try {
    apply(await fetch());
    return null;
  } catch (err) {
    console.error(`snapshot.slice_failed:${name}`, err);
    return name;
  }
}

/**
 * Fetch the REST snapshot into the stores. Returns the names of the slices
 * that failed, empty if all landed.
 *
 * The slices are deliberately independent: news, assets and prices come from
 * unrelated endpoints, so a 500 on one of them must not blank the panels fed
 * by the others. Promise.all would do exactly that — it discards resolved
 * values as soon as any sibling rejects.
 */
export async function loadSnapshot(
  eventLimit: number = EVENT_PREFETCH_COUNT,
): Promise<string[]> {
  const outcomes = await Promise.all([
    loadSlice("assets", api.listAssets, (d) =>
      useAssetsStore.getState().setAssets(d),
    ),
    loadSlice("regions", api.listRegions, (d) =>
      useAssetsStore.getState().setRegions(d),
    ),
    loadSlice(
      "events",
      () => api.listEvents(eventLimit),
      (d) => useEventsStore.getState().setInitial(d),
    ),
    loadSlice("prices", api.latestPrices, (d) =>
      usePricesStore.getState().setInitial(d),
    ),
  ]);
  return outcomes.filter((name): name is string => name !== null);
}

export function useBootstrap(): void {
  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | null = null;
    let retryDelay = RETRY_BASE_MS;
    let inFlight = false;

    const clearRetry = () => {
      if (retryTimer !== null) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
    };

    /**
     * Load the snapshot, retrying with backoff until it lands. Without this
     * a single failure (backend still booting, network blip) would leave the
     * panels empty for the whole session — the WS only carries new events,
     * so nothing else ever backfills history.
     */
    const attempt = (): void => {
      if (cancelled || inFlight) return;
      clearRetry();
      inFlight = true;
      loadSnapshot()
        .then((failed) => {
          if (cancelled) return;
          if (failed.length === 0) {
            retryDelay = RETRY_BASE_MS;
            useUIStore.getState().setSnapshotStatus("ready");
            return;
          }
          // Whatever succeeded is already on screen; keep retrying for the rest.
          useUIStore.getState().setSnapshotStatus("failed");
          retryTimer = window.setTimeout(attempt, retryDelay);
          retryDelay = Math.min(retryDelay * 2, RETRY_MAX_MS);
        })
        .finally(() => {
          inFlight = false;
        });
    };

    attempt();

    // A *re*connect means the socket was down for a while, so the store has
    // a hole in it. The first open is skipped — attempt() already covers it.
    let sawConnection = false;

    const ws = new WSClient({
      channels: ["events", "prices", "impacts"],
      onOpen: () => {
        useUIStore.getState().setConnected(true);
        if (sawConnection) attempt();
        sawConnection = true;
      },
      onClose: () => useUIStore.getState().setConnected(false),
      onMessage: (msg) => {
        if (msg.type === "event.new") {
          useEventsStore.getState().upsert(msg.event);
        } else if (msg.type === "price.update") {
          usePricesStore.getState().applyUpdates(msg.updates);
        } else if (msg.type === "impact.outcome") {
          useOutcomesStore.getState().apply(msg.outcomes);
        }
      },
    });
    ws.start();

    return () => {
      cancelled = true;
      clearRetry();
      ws.stop();
    };
  }, []);
}
