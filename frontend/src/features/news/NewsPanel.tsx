import { useEventsStore } from "../../store/events";

/**
 * Left column — newest events first, click to select.
 * Phase 4.b: minimal placeholder rendering. Polished in 4.d.
 */
export function NewsPanel() {
  const events = useEventsStore((s) => s.events);
  const selectedId = useEventsStore((s) => s.selectedId);
  const select = useEventsStore((s) => s.select);

  return (
    <aside
      aria-label="News stream"
      className="h-full overflow-y-auto border-r border-border bg-panel/60"
    >
      <header className="px-4 py-3 border-b border-border text-xs uppercase tracking-wider text-muted">
        News stream · {events.length}
      </header>
      <ul className="divide-y divide-border">
        {events.length === 0 && (
          <li className="px-4 py-6 text-sm text-muted">
            No events yet. The first scheduled tick runs within 60s of boot.
          </li>
        )}
        {events.map((e) => (
          <li key={e.id}>
            <button
              type="button"
              onClick={() => select(e.id)}
              className={
                "block w-full text-left px-4 py-3 transition-colors hover:bg-border/30 " +
                (selectedId === e.id ? "bg-border/40" : "")
              }
            >
              <div className="flex items-center gap-2 text-xs text-muted">
                <SeverityDot s={e.severity} />
                <span>{new Date(e.occurred_at).toLocaleTimeString()}</span>
                <span>·</span>
                <span className="uppercase">{e.classifier}</span>
                {e.origin_country && <span>· {e.origin_country}</span>}
              </div>
              <p className="mt-1 text-sm leading-snug">{e.title}</p>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

function SeverityDot({ s }: { s: "low" | "medium" | "high" }) {
  const color = s === "high" ? "bg-err" : s === "medium" ? "bg-warn" : "bg-ok";
  return <span className={"inline-block w-2 h-2 rounded-full " + color} />;
}
