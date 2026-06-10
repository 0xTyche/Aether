import { useEffect, useState } from "react";

import { useAssetsStore } from "../../store/assets";
import { useEventsStore } from "../../store/events";
import { usePricesStore } from "../../store/prices";
import type { Event, ImpactPrediction } from "../../types/api";

/**
 * Right column — for the selected event, render each predicted impact
 * alongside the realised price move since the event's occurred_at time.
 *
 * "Expected" comes from the prediction (rule or LLM). "Actual" compares
 * the latest known price against the prediction's baseline — taken once
 * when the event becomes selected, so we don't keep moving the goalpost
 * as new ticks arrive.
 */

interface Baseline {
  eventId: string;
  takenAt: number;
  priceByAsset: Record<string, number>;
}

export function ImpactPanel() {
  const events = useEventsStore((s) => s.events);
  const selectedId = useEventsStore((s) => s.selectedId);
  const event = events.find((e) => e.id === selectedId) ?? null;

  const baseline = useBaselinePrices(event);

  return (
    <aside
      aria-label="Asset impacts"
      className="h-full overflow-y-auto border-l border-border bg-panel/60"
    >
      <header className="px-4 py-3 border-b border-border text-xs uppercase tracking-wider text-muted sticky top-0 bg-panel/95 backdrop-blur z-10">
        Asset impacts
      </header>
      {!event && (
        <div className="p-4 text-sm text-muted">
          Select an event from the left to see expected vs actual moves.
        </div>
      )}
      {event && <EventHeader event={event} />}
      {event && (
        <ul className="divide-y divide-border">
          {event.predictions.map((p) => (
            <ImpactRow
              key={p.asset_id}
              prediction={p}
              baselinePrice={baseline?.priceByAsset[p.asset_id] ?? null}
            />
          ))}
        </ul>
      )}
    </aside>
  );
}

function EventHeader({ event }: { event: Event }) {
  return (
    <div className="px-4 py-3 border-b border-border">
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="uppercase">{event.classifier}</span>
        <span>·</span>
        <span className={"uppercase " + severityClass(event.severity)}>
          {event.severity}
        </span>
        {event.origin_country && (
          <span className="ml-auto font-mono">{event.origin_country}</span>
        )}
      </div>
      <h2 className="mt-1 text-sm font-medium leading-snug">{event.title}</h2>
      {event.explanation && (
        <p className="mt-2 text-xs text-muted leading-snug">{event.explanation}</p>
      )}
      {event.affected_regions && event.affected_regions.length > 0 && (
        <div className="mt-2 flex gap-1">
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
  );
}

function ImpactRow({
  prediction,
  baselinePrice,
}: {
  prediction: ImpactPrediction;
  baselinePrice: number | null;
}) {
  const assets = useAssetsStore((s) => s.byId);
  const latest = usePricesStore((s) => s.latest[prediction.asset_id]);
  const display = assets[prediction.asset_id]?.display_name ?? prediction.asset_id;

  // Realised move: percentage change vs baseline; null if no data yet.
  const actualPct =
    baselinePrice != null && latest != null && baselinePrice !== 0
      ? ((latest.price - baselinePrice) / baselinePrice) * 100
      : null;

  const verdict = actualPct == null ? "pending" : verdictFor(prediction.direction, actualPct);

  return (
    <li className="px-4 py-2.5">
      <div className="flex items-center gap-3">
        <div className="min-w-0">
          <div className="text-sm font-mono">{prediction.asset_id}</div>
          <div className="text-[10px] text-muted truncate">{display}</div>
        </div>
        <span className="ml-auto flex items-baseline gap-1.5">
          <ExpectedGlyph d={prediction.direction} m={prediction.magnitude} />
          <span className="text-[10px] text-muted">expected</span>
        </span>
      </div>
      <div className="mt-1 flex items-center gap-3 text-xs">
        {actualPct == null ? (
          <span className="text-muted">no price yet</span>
        ) : (
          <>
            <span className={"font-mono " + pctColor(actualPct)}>
              {actualPct >= 0 ? "+" : ""}
              {actualPct.toFixed(2)}%
            </span>
            <span className="text-muted">actual</span>
            <span className={"ml-auto text-[10px] " + verdictColor(verdict)}>
              {verdict.toUpperCase()}
            </span>
          </>
        )}
      </div>
      {prediction.rationale && (
        <p className="mt-1 text-[10px] text-muted leading-snug">
          {prediction.rationale}
        </p>
      )}
    </li>
  );
}

function ExpectedGlyph({
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

type Verdict = "hit" | "miss" | "flat" | "pending";

function verdictFor(direction: ImpactPrediction["direction"], pct: number): Verdict {
  if (Math.abs(pct) < 0.05) return "flat";
  if (direction === "neutral") return Math.abs(pct) < 0.5 ? "hit" : "miss";
  if (direction === "up") return pct > 0 ? "hit" : "miss";
  if (direction === "down") return pct < 0 ? "hit" : "miss";
  return "pending";
}

function verdictColor(v: Verdict): string {
  return v === "hit"
    ? "text-ok"
    : v === "miss"
      ? "text-err"
      : v === "flat"
        ? "text-warn"
        : "text-muted";
}

function pctColor(pct: number): string {
  if (Math.abs(pct) < 0.05) return "text-muted";
  return pct > 0 ? "text-ok" : "text-err";
}

function severityClass(s: "low" | "medium" | "high"): string {
  return s === "high" ? "text-err" : s === "medium" ? "text-warn" : "text-ok";
}

/**
 * Snapshot the latest known prices once when the selected event changes,
 * and remember them as the baseline for the "expected vs actual" math.
 *
 * Pulling from store inside the hook keeps the implementation framework-
 * free; no need for a global "baselines" store.
 */
function useBaselinePrices(event: Event | null): Baseline | null {
  const allLatest = usePricesStore((s) => s.latest);
  const [baseline, setBaseline] = useState<Baseline | null>(null);

  useEffect(() => {
    if (!event) {
      setBaseline(null);
      return;
    }
    if (baseline && baseline.eventId === event.id) return;

    const priceByAsset: Record<string, number> = {};
    for (const p of event.predictions) {
      const tick = allLatest[p.asset_id];
      if (tick) priceByAsset[p.asset_id] = tick.price;
    }
    setBaseline({
      eventId: event.id,
      takenAt: Date.now(),
      priceByAsset,
    });
    // We intentionally only re-snap on event change, not on every tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [event?.id]);

  return baseline;
}
