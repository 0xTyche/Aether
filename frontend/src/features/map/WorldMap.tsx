import "maplibre-gl/dist/maplibre-gl.css";

import { ArcLayer, GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { FeatureCollection } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { Map as MapLibre, type MapRef } from "react-map-gl/maplibre";

import { useAnimationPhase } from "../../lib/useAnimationPhase";
import { useEventsInWindow } from "../../lib/useEventsInWindow";
import { useAssetsStore } from "../../store/assets";
import { useEventsStore } from "../../store/events";
import { useUIStore } from "../../store/ui";
import { DeckOverlay } from "./DeckOverlay";
import { buildArcsForEvent, type ArcDatum } from "./arcsForEvent";
import {
  STROKE_COLOR,
  fillFor,
  isoOf,
  type RGBA,
} from "./countryStyle";
import {
  MARKER_COLOR,
  markersFromEvents,
  radiusFor,
  type EventMarker,
} from "./eventMarkers";
import { loadCountryGeometry } from "./loadGeometry";

const OPENFREEMAP_DARK = "https://tiles.openfreemap.org/styles/dark";

const INITIAL_VIEW = {
  longitude: 0,
  latitude: 20,
  zoom: 1.8,
};

function memberIsoSet(
  regionIds: Set<string>,
  regionsById: Record<string, { members: string[] }>,
): Set<string> {
  const out = new Set<string>();
  for (const id of regionIds) {
    const r = regionsById[id];
    if (!r) continue;
    for (const iso of r.members) out.add(iso);
  }
  return out;
}

const ARROW_RGBA: Record<"up" | "down" | "neutral", [RGBA, RGBA]> = {
  up:      [[74, 222, 128, 220], [74, 222, 128, 80]],
  down:    [[248, 113, 113, 220], [248, 113, 113, 80]],
  neutral: [[148, 163, 184, 200], [148, 163, 184, 60]],
};

export function WorldMap() {
  const mapRef = useRef<MapRef | null>(null);
  const [geom, setGeom] = useState<FeatureCollection | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const selectedId = useEventsStore((s) => s.selectedId);
  const events = useEventsStore((s) => s.events);
  const selectEvent = useEventsStore((s) => s.select);
  const selectedEvent = events.find((e) => e.id === selectedId) ?? null;

  const inWindow = useEventsInWindow();
  const phase = useAnimationPhase();
  const markers = useMemo(() => markersFromEvents(inWindow), [inWindow]);
  const highMarkers = useMemo(
    () => markers.filter((m) => m.severity === "high"),
    [markers],
  );
  const nonHighMarkers = useMemo(
    () => markers.filter((m) => m.severity !== "high"),
    [markers],
  );

  const assetsById = useAssetsStore((s) => s.byId);
  const regionsById = useAssetsStore((s) => s.regionsById);
  const highlighted = useUIStore((s) => s.highlightedRegions);

  // Load geometry once.
  useEffect(() => {
    let cancelled = false;
    loadCountryGeometry()
      .then((g) => {
        if (!cancelled) setGeom(g);
      })
      .catch((err) => console.error("map.geometry_load_failed", err));
    return () => {
      cancelled = true;
    };
  }, []);

  // Fly to the selected event's origin when it changes.
  useEffect(() => {
    if (!selectedEvent || selectedEvent.origin_lat == null || selectedEvent.origin_lng == null) return;
    const map = mapRef.current?.getMap();
    if (!map) return;
    map.flyTo({
      center: [selectedEvent.origin_lng, selectedEvent.origin_lat],
      zoom: Math.max(map.getZoom(), 3.2),
      duration: 1200,
      essential: true,
    });
  }, [selectedEvent]);

  const highlightedISOs = useMemo(
    () => memberIsoSet(highlighted, regionsById),
    [highlighted, regionsById],
  );

  const arcs: ArcDatum[] = useMemo(
    () => buildArcsForEvent(selectedEvent, assetsById),
    [selectedEvent, assetsById],
  );

  const layers = useMemo(() => {
    if (!geom) return [];
    const styleCtx = {
      hoveredISO: hovered,
      originISO: selectedEvent?.origin_country ?? null,
      highlightedISOs,
    };
    return [
      new GeoJsonLayer({
        id: "countries",
        data: geom,
        pickable: true,
        stroked: true,
        filled: true,
        getFillColor: (f) => fillFor(f, styleCtx),
        getLineColor: STROKE_COLOR,
        lineWidthMinPixels: 0.5,
        updateTriggers: {
          getFillColor: [hovered, selectedEvent?.origin_country, highlightedISOs],
        },
        onHover: (info) => {
          const f = info.object;
          setHovered(f ? isoOf(f) : null);
        },
        onClick: (info) => {
          const iso = info.object ? isoOf(info.object) : null;
          if (!iso) return;
          // Future: filter the news feed by country. For now just log.
          console.log("map.country_clicked", iso);
        },
      }),
      // Static low/medium markers — no animation triggers, cheap to redraw.
      nonHighMarkers.length > 0 &&
        new ScatterplotLayer<EventMarker>({
          id: "event-markers-static",
          data: nonHighMarkers,
          pickable: true,
          stroked: true,
          radiusUnits: "pixels",
          lineWidthMinPixels: 1,
          getPosition: (m) => [m.lng, m.lat],
          getRadius: (m) => radiusFor(m, 0),
          getFillColor: (m) => MARKER_COLOR[m.severity],
          getLineColor: [255, 255, 255, 90],
          onClick: (info) => {
            if (info.object?.eventId) selectEvent(info.object.eventId);
          },
        }),
      // High markers pulse — rebuilt every animation tick.
      highMarkers.length > 0 &&
        new ScatterplotLayer<EventMarker>({
          id: "event-markers-pulse",
          data: highMarkers,
          pickable: true,
          stroked: true,
          radiusUnits: "pixels",
          lineWidthMinPixels: 1,
          getPosition: (m) => [m.lng, m.lat],
          getRadius: (m) => radiusFor(m, phase),
          getFillColor: (m) => MARKER_COLOR[m.severity],
          getLineColor: [255, 255, 255, 110],
          updateTriggers: { getRadius: [phase] },
          onClick: (info) => {
            if (info.object?.eventId) selectEvent(info.object.eventId);
          },
        }),
      arcs.length > 0 &&
        new ArcLayer({
          id: "event-arcs",
          data: arcs,
          getSourcePosition: (d: ArcDatum) => d.source,
          getTargetPosition: (d: ArcDatum) => d.target,
          getSourceColor: (d: ArcDatum) => ARROW_RGBA[d.direction][0],
          getTargetColor: (d: ArcDatum) => ARROW_RGBA[d.direction][1],
          getWidth: 2,
          widthMinPixels: 1.5,
          greatCircle: true,
        }),
    ].filter(Boolean);
  }, [
    geom, hovered, selectedEvent, highlightedISOs, arcs,
    nonHighMarkers, highMarkers, phase, selectEvent,
  ]);

  return (
    <div className="relative h-full w-full">
      <MapLibre
        ref={mapRef}
        initialViewState={INITIAL_VIEW}
        mapStyle={OPENFREEMAP_DARK}
        attributionControl={false}
        style={{ width: "100%", height: "100%" }}
      >
        <DeckOverlay layers={layers as never} interleaved />
      </MapLibre>
      {selectedEvent && (
        <button
          type="button"
          onClick={() => selectEvent(null)}
          className="absolute top-2 right-2 z-10 px-2 py-1 text-xs rounded bg-panel/80 border border-border text-muted hover:text-white"
        >
          clear selection
        </button>
      )}
      {!geom && (
        <div className="absolute inset-0 grid place-items-center text-muted text-sm pointer-events-none">
          loading map geometry…
        </div>
      )}
    </div>
  );
}
