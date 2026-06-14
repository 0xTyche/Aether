/** Static landmark layer — central banks, waterways, commodity hubs.
 *
 *  Rendered as DOM markers via `react-map-gl` so each marker can host
 *  a real Lucide React icon and a CSS-styled hover tooltip. Scale is
 *  ~44 markers globally, well within DOM marker comfort.
 *
 *  On hover, the tooltip lists events from the current time window
 *  that the landmark cares about (per `landmarkRelevance.ts`).
 *  Clicking a listed event triggers the existing select flow.
 */

import {
  Anchor,
  Flame,
  Fuel,
  Gem,
  Landmark as LandmarkIcon,
  Pickaxe,
  Wheat,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { Marker } from "react-map-gl/maplibre";

import { useEventsInWindow } from "../../lib/useEventsInWindow";
import { useEventsStore } from "../../store/events";
import type { Event } from "../../types/api";
import { eventsForLandmark } from "./landmarkRelevance";
import { LANDMARKS, type Landmark, type LandmarkCategory } from "./landmarks";

const CATEGORY_COLOR: Record<LandmarkCategory, string> = {
  "central-bank": "text-sky-300/70 hover:text-sky-200",
  "strategic-waterway": "text-cyan-300/70 hover:text-cyan-200",
  "commodity-hub": "text-amber-300/70 hover:text-amber-200",
};

function pickIcon(lm: Landmark): LucideIcon {
  if (lm.category === "central-bank") return LandmarkIcon;
  if (lm.category === "strategic-waterway") return Anchor;
  // commodity-hub: route by detail keyword
  const d = (lm.detail ?? "").toLowerCase();
  if (d.includes("oil")) return Fuel;
  if (d.includes("gas") || d.includes("lng")) return Flame;
  if (d.includes("corn") || d.includes("soybean") || d.includes("agri") || d.includes("grain")) return Wheat;
  if (d.includes("rare")) return Gem;
  return Pickaxe;
}

export function LandmarkMarkers() {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const inWindow = useEventsInWindow();
  const selectEvent = useEventsStore((s) => s.select);

  return (
    <>
      {LANDMARKS.map((lm) => {
        const Icon = pickIcon(lm);
        const isHovered = hoveredId === lm.id;
        const related = isHovered ? eventsForLandmark(inWindow, lm) : [];
        return (
          <Marker
            key={lm.id}
            longitude={lm.lng}
            latitude={lm.lat}
            anchor="center"
          >
            <div
              className="relative cursor-help"
              onMouseEnter={() => setHoveredId(lm.id)}
              onMouseLeave={() => setHoveredId(null)}
            >
              <Icon
                size={16}
                strokeWidth={1.8}
                className={`drop-shadow ${CATEGORY_COLOR[lm.category]} transition-colors`}
              />
              {isHovered && (
                <LandmarkTooltip
                  landmark={lm}
                  events={related}
                  onEventClick={selectEvent}
                />
              )}
            </div>
          </Marker>
        );
      })}
    </>
  );
}

function LandmarkTooltip({
  landmark,
  events,
  onEventClick,
}: {
  landmark: Landmark;
  events: Event[];
  onEventClick: (id: string) => void;
}) {
  return (
    <div
      className="absolute left-5 top-1/2 -translate-y-1/2 w-64 rounded-md border border-border bg-panel/95 backdrop-blur shadow-xl text-xs z-30 pointer-events-auto"
      role="tooltip"
    >
      <header className="px-2.5 py-1.5 border-b border-border">
        <div className="font-medium text-sm leading-tight">{landmark.name_zh}</div>
        <div className="text-muted text-[10px] leading-tight">{landmark.name_en}</div>
        {landmark.category === "commodity-hub" && landmark.detail && (
          <div className="text-amber-300/80 text-[10px] mt-0.5 font-mono">
            {landmark.detail}
          </div>
        )}
      </header>

      <div className="px-2.5 py-1.5 space-y-1">
        <div className="text-muted text-[10px] uppercase tracking-wide">
          当前窗口相关事件 ({events.length})
        </div>
        {events.length === 0 ? (
          <div className="text-muted/60 text-[10px] italic py-0.5">— 无相关</div>
        ) : (
          events.map((e) => (
            <button
              key={e.id}
              type="button"
              onClick={() => onEventClick(e.id)}
              className="flex items-center gap-1.5 w-full text-left hover:bg-border/30 rounded px-1 py-0.5"
              title={e.title}
            >
              <SeverityDot s={e.severity} />
              <span className="text-[11px] truncate">{e.title}</span>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function SeverityDot({ s }: { s: Event["severity"] }) {
  const cls =
    s === "high" ? "bg-err" : s === "medium" ? "bg-warn" : "bg-ok";
  return (
    <span
      className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${cls}`}
    />
  );
}
