import "./App.css";

import { NewsPanel } from "./features/news/NewsPanel";
import { ImpactPanel } from "./features/impact/ImpactPanel";
import { RegionChips } from "./features/regions/RegionChips";
import { useBootstrap } from "./lib/useBootstrap";
import { useUIStore } from "./store/ui";

function Header() {
  const connected = useUIStore((s) => s.connected);
  return (
    <header className="flex items-center gap-3 px-4 py-2 border-b border-border bg-panel">
      <h1 className="text-base font-semibold">
        Aether <span className="text-muted font-normal">· 以太</span>
      </h1>
      <span
        className={
          "text-xs px-2 py-0.5 rounded-full " +
          (connected
            ? "bg-ok/20 text-ok"
            : "bg-err/20 text-err")
        }
      >
        {connected ? "LIVE" : "OFFLINE"}
      </span>
    </header>
  );
}

function MapPlaceholder() {
  return (
    <section className="h-full w-full grid place-items-center bg-bg text-muted text-sm">
      <div className="text-center">
        <div className="text-xs uppercase tracking-wider">Map area</div>
        <p className="mt-2 max-w-sm leading-snug">
          The deck.gl + MapLibre world map lands in Phase 4.c.
        </p>
      </div>
    </section>
  );
}

export default function App() {
  useBootstrap();
  return (
    <div className="h-full flex flex-col">
      <Header />
      <RegionChips />
      <main className="flex-1 grid grid-cols-[320px_1fr_360px] min-h-0">
        <NewsPanel />
        <MapPlaceholder />
        <ImpactPanel />
      </main>
    </div>
  );
}
