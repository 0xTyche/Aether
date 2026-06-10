import { useEventsStore } from "../../store/events";
import type { Event } from "../../types/api";

/** Left column — newest events first; click to select. */
export function NewsPanel() {
  const events = useEventsStore((s) => s.events);
  const selectedId = useEventsStore((s) => s.selectedId);
  const select = useEventsStore((s) => s.select);

  return (
    <aside
      aria-label="News stream"
      className="h-full overflow-y-auto border-r border-border bg-panel/60"
    >
      <header className="px-4 py-3 border-b border-border text-xs uppercase tracking-wider text-muted sticky top-0 bg-panel/95 backdrop-blur z-10">
        News stream · {events.length}
      </header>
      <ul className="divide-y divide-border">
        {events.length === 0 && (
          <li className="px-4 py-6 text-sm text-muted">
            No events yet. The first scheduled tick runs within 60s of boot.
          </li>
        )}
        {events.map((e) => (
          <NewsItem
            key={e.id}
            event={e}
            selected={selectedId === e.id}
            onSelect={() => select(e.id)}
          />
        ))}
      </ul>
    </aside>
  );
}

function NewsItem({
  event,
  selected,
  onSelect,
}: {
  event: Event;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        className={
          "block w-full text-left px-4 py-3 transition-colors hover:bg-border/30 " +
          (selected ? "bg-border/40 border-l-2 border-accent" : "border-l-2 border-transparent")
        }
      >
        <div className="flex items-center gap-2 text-xs text-muted">
          <SeverityDot s={event.severity} />
          <span className="font-mono">{relativeTime(event.occurred_at)}</span>
          <span>·</span>
          <span className="uppercase">{event.classifier}</span>
          {event.origin_country && (
            <span className="ml-auto px-1.5 py-0.5 rounded bg-border/40 text-[10px] font-mono">
              {event.origin_country}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm leading-snug">{event.title}</p>
        {event.affected_regions && event.affected_regions.length > 0 && (
          <div className="mt-1.5 flex gap-1">
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
      </button>
    </li>
  );
}

function SeverityDot({ s }: { s: "low" | "medium" | "high" }) {
  const color = s === "high" ? "bg-err" : s === "medium" ? "bg-warn" : "bg-ok";
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color}`}
      title={`severity: ${s}`}
    />
  );
}

/** Compact relative time: 12s, 4m, 2h, 3d. Falls back to date for >7d. */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const sec = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day}d`;
  return new Date(iso).toLocaleDateString();
}
