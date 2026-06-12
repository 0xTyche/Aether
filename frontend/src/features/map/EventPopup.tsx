/** Floating popup anchored at the selected event's origin lat/lng.
 *
 *  Anchored via MapLibre's `project()` so the popup tracks the map as
 *  the user pans / zooms. Listens to the map's move event and
 *  re-projects each frame the map is animating.
 */

import { useEffect, useState } from "react";
import type { MapRef } from "react-map-gl/maplibre";

import { useEventsStore } from "../../store/events";
import type { Event } from "../../types/api";

interface EventPopupProps {
  mapRef: React.RefObject<MapRef | null>;
}

export function EventPopup({ mapRef }: EventPopupProps) {
  const selectedId = useEventsStore((s) => s.selectedId);
  const events = useEventsStore((s) => s.events);
  const select = useEventsStore((s) => s.select);
  const event = events.find((e) => e.id === selectedId) ?? null;

  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  // Reproject whenever the selected event changes OR the map moves.
  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !event || event.origin_lat == null || event.origin_lng == null) {
      setPos(null);
      return;
    }

    const update = () => {
      if (event.origin_lng == null || event.origin_lat == null) return;
      const p = map.project([event.origin_lng, event.origin_lat]);
      setPos({ x: p.x, y: p.y });
    };
    update();
    map.on("move", update);
    map.on("zoom", update);
    return () => {
      map.off("move", update);
      map.off("zoom", update);
    };
  }, [event, mapRef]);

  if (!event || pos == null) return null;

  return (
    <div
      className="absolute z-20 -translate-x-1/2 -translate-y-full mb-2 pointer-events-auto"
      style={{ left: pos.x, top: pos.y - 14 }}
      role="dialog"
      aria-label={`Event: ${event.title}`}
    >
      <PopupCard event={event} onClose={() => select(null)} />
      <PopupTail />
    </div>
  );
}

function PopupCard({ event, onClose }: { event: Event; onClose: () => void }) {
  return (
    <div className="w-72 rounded-md border border-border bg-panel/95 backdrop-blur shadow-xl text-xs">
      <header className="flex items-center justify-between gap-2 px-3 py-2 border-b border-border">
        <h3 className="font-medium text-sm leading-tight truncate" title={event.title}>
          {event.title}
        </h3>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="text-muted hover:text-white text-lg leading-none px-1 -mr-1"
        >
          ×
        </button>
      </header>

      <div className="px-3 py-2 space-y-2">
        <div className="flex items-center gap-1.5 text-[10px]">
          <SeverityBadge s={event.severity} />
          <Badge>{event.classifier.toUpperCase()}</Badge>
          {event.origin_country && (
            <Badge>{event.origin_country}</Badge>
          )}
          <span className="ml-auto text-muted font-mono">
            {new Date(event.occurred_at).toLocaleString(undefined, {
              month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
            })}
          </span>
        </div>

        {event.explanation && (
          <p className="text-muted leading-snug">{event.explanation}</p>
        )}

        {event.affected_regions && event.affected_regions.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {event.affected_regions.map((r) => (
              <span
                key={r}
                className="text-[10px] px-1.5 py-0.5 rounded-full bg-accent/15 text-accent font-mono"
              >
                {r}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="px-1.5 py-0.5 rounded bg-border/60 font-mono text-muted">
      {children}
    </span>
  );
}

function SeverityBadge({ s }: { s: "low" | "medium" | "high" }) {
  const cls =
    s === "high"
      ? "bg-err/30 text-err"
      : s === "medium"
        ? "bg-warn/30 text-warn"
        : "bg-ok/30 text-ok";
  return (
    <span className={`px-1.5 py-0.5 rounded font-mono ${cls}`}>
      {s.toUpperCase()}
    </span>
  );
}

/** Small triangular tail pointing down at the marker. */
function PopupTail() {
  return (
    <div
      className="absolute left-1/2 -translate-x-1/2"
      style={{
        top: "100%",
        width: 0,
        height: 0,
        borderLeft: "6px solid transparent",
        borderRight: "6px solid transparent",
        borderTop: "6px solid rgb(17 24 39 / 0.95)", // matches bg-panel/95
      }}
    />
  );
}
