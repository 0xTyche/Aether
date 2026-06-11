/** Hook that loads initial REST state once and keeps the WS open while mounted. */

import { useEffect } from "react";

import { useAssetsStore } from "../store/assets";
import { useEventsStore } from "../store/events";
import { useOutcomesStore } from "../store/outcomes";
import { usePricesStore } from "../store/prices";
import { useUIStore } from "../store/ui";
import { api } from "./api";
import { WSClient } from "./ws";

export function useBootstrap(): void {
  const setAssets = useAssetsStore((s) => s.setAssets);
  const setRegions = useAssetsStore((s) => s.setRegions);
  const setEventsInitial = useEventsStore((s) => s.setInitial);
  const upsertEvent = useEventsStore((s) => s.upsert);
  const setPricesInitial = usePricesStore((s) => s.setInitial);
  const applyPriceUpdates = usePricesStore((s) => s.applyUpdates);
  const applyOutcomes = useOutcomesStore((s) => s.apply);
  const setConnected = useUIStore((s) => s.setConnected);

  useEffect(() => {
    let mounted = true;

    Promise.all([
      api.listAssets(),
      api.listRegions(),
      api.listEvents(50),
      api.latestPrices(),
    ])
      .then(([assets, regions, events, prices]) => {
        if (!mounted) return;
        setAssets(assets);
        setRegions(regions);
        setEventsInitial(events);
        setPricesInitial(prices);
      })
      .catch((err) => {
        console.error("bootstrap.failed", err);
      });

    const ws = new WSClient({
      channels: ["events", "prices", "impacts"],
      onOpen: () => setConnected(true),
      onClose: () => setConnected(false),
      onMessage: (msg) => {
        if (msg.type === "event.new") {
          upsertEvent(msg.event);
        } else if (msg.type === "price.update") {
          applyPriceUpdates(msg.updates);
        } else if (msg.type === "impact.outcome") {
          applyOutcomes(msg.outcomes);
        }
      },
    });
    ws.start();

    return () => {
      mounted = false;
      ws.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
