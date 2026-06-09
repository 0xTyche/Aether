import { useCallback, useEffect, useState } from "react";

import {
  getCountryAtCoordinates,
  preloadCountryGeometry,
} from "../../vendor/worldmonitor/country-geometry";

// NOTE: hit-test runs against vendor's internal geometry state (base + WM overrides).
// Local `boundary-overrides.geojson` is NOT yet reflected here — handled by `loadGeometry.ts`
// for the rendered map layer. Unify when deck.gl integration lands (Phase 4).
type HitTest = (lat: number, lng: number) => string | null;

export function useCountryHitTest(): { ready: boolean; hitTest: HitTest } {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    preloadCountryGeometry()
      .then(() => {
        if (!cancelled) setReady(true);
      })
      .catch((err) => {
        console.error("country geometry preload failed", err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const hitTest = useCallback<HitTest>((lat, lng) => {
    return getCountryAtCoordinates(lat, lng)?.code ?? null;
  }, []);

  return { ready, hitTest };
}
