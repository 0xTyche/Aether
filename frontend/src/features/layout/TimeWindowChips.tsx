import { EVENT_WINDOW_OPTIONS, useUIStore } from "../../store/ui";

/** A small chip row to pick how far back events should be shown. */
export function TimeWindowChips() {
  const value = useUIStore((s) => s.eventWindowMin);
  const set = useUIStore((s) => s.setEventWindowMin);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-wider text-muted">Window</span>
      {EVENT_WINDOW_OPTIONS.map((m) => {
        const active = m === value;
        return (
          <button
            key={m}
            type="button"
            onClick={() => set(m)}
            className={
              "px-2 py-0.5 rounded-full text-xs border transition-colors font-mono " +
              (active
                ? "bg-accent/20 border-accent text-accent"
                : "border-border text-muted hover:text-white hover:border-muted")
            }
            title={`Show events from the last ${formatWindow(m)}`}
          >
            {formatWindow(m)}
          </button>
        );
      })}
    </div>
  );
}

function formatWindow(min: number): string {
  if (min < 60) return `${min}m`;
  if (min < 1440) return `${Math.round(min / 60)}h`;
  return `${Math.round(min / 1440)}d`;
}
