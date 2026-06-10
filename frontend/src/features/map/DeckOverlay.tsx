/** Tiny react-map-gl ↔ deck.gl bridge.
 *
 * MapboxOverlay implements `react-map-gl`'s `IControl` interface, so it
 * mounts as an interleaved control inside the MapLibre canvas — no
 * separate DOM layer, perfect picking, no event-routing headaches.
 */

import { MapboxOverlay, type MapboxOverlayProps } from "@deck.gl/mapbox";
import { useControl } from "react-map-gl/maplibre";

export function DeckOverlay(props: MapboxOverlayProps) {
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const overlay = useControl(() => new MapboxOverlay(props));
  overlay.setProps(props);
  return null;
}
