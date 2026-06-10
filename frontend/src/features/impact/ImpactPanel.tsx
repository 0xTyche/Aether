import { useEventsStore } from "../../store/events";

/**
 * Right column — for the selected event, show predicted vs actual per asset.
 * Phase 4.b: placeholder. 4.d adds the live "expected vs actual" diff.
 */
export function ImpactPanel() {
  const selectedId = useEventsStore((s) => s.selectedId);
  const events = useEventsStore((s) => s.events);
  const event = events.find((e) => e.id === selectedId) ?? null;

  return (
    <aside
      aria-label="Asset impacts"
      className="h-full overflow-y-auto border-l border-border bg-panel/60"
    >
      <header className="px-4 py-3 border-b border-border text-xs uppercase tracking-wider text-muted">
        Asset impacts
      </header>
      {!event && (
        <div className="p-4 text-sm text-muted">
          Select an event from the left to see predicted asset impacts.
        </div>
      )}
      {event && (
        <div>
          <div className="px-4 py-3 border-b border-border">
            <div className="text-xs text-muted">
              {event.classifier.toUpperCase()} · {event.severity.toUpperCase()}
              {event.origin_country ? ` · ${event.origin_country}` : ""}
            </div>
            <h2 className="mt-1 text-sm font-medium leading-snug">{event.title}</h2>
            {event.explanation && (
              <p className="mt-2 text-xs text-muted leading-snug">{event.explanation}</p>
            )}
          </div>
          <ul className="divide-y divide-border">
            {event.predictions.map((p) => (
              <li key={p.asset_id} className="px-4 py-2 flex items-center gap-3">
                <span className="text-sm font-mono w-24">{p.asset_id}</span>
                <DirectionGlyph d={p.direction} m={p.magnitude} />
                <span className="text-xs text-muted ml-auto">
                  {((p.confidence ?? 0) * 100).toFixed(0)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}

function DirectionGlyph({
  d,
  m,
}: {
  d: "up" | "down" | "neutral";
  m: "small" | "medium" | "large";
}) {
  const arrow = d === "up" ? "▲" : d === "down" ? "▼" : "—";
  const color = d === "up" ? "text-ok" : d === "down" ? "text-err" : "text-muted";
  const size = m === "large" ? "text-base" : m === "medium" ? "text-sm" : "text-xs";
  return <span className={`${color} ${size} font-mono`}>{arrow}</span>;
}
