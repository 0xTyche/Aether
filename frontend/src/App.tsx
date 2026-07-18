import "./App.css";

import { ImpactPanel } from "./features/impact/ImpactPanel";
import { ResizeHandle } from "./features/layout/ResizeHandle";
import { TimeWindowChips } from "./features/layout/TimeWindowChips";
import { WorldMap } from "./features/map/WorldMap";
import { NewsPanel } from "./features/news/NewsPanel";
import { RegionChips } from "./features/regions/RegionChips";
import { useBootstrap } from "./lib/useBootstrap";
import { useUIStore } from "./store/ui";

function Header() {
  const connected = useUIStore((s) => s.connected);
  const snapshotStatus = useUIStore((s) => s.snapshotStatus);
  return (
    <header className="flex items-center gap-3 px-4 py-2 border-b border-border bg-panel">
      <h1 className="text-base font-semibold">
        Aether <span className="text-muted font-normal">· 以太</span>
      </h1>
      <span
        className={
          "text-xs px-2 py-0.5 rounded-full " +
          (connected ? "bg-ok/20 text-ok" : "bg-err/20 text-err")
        }
      >
        {connected ? "LIVE" : "OFFLINE"}
      </span>
      {snapshotStatus === "failed" && (
        <span
          role="status"
          className="text-xs px-2 py-0.5 rounded-full bg-warn/20 text-warn"
          title="Could not load history from the backend. Retrying automatically."
        >
          数据陈旧 · 重试中
        </span>
      )}
    </header>
  );
}

export default function App() {
  useBootstrap();

  const leftWidth = useUIStore((s) => s.leftWidth);
  const rightWidth = useUIStore((s) => s.rightWidth);
  const setLeftWidth = useUIStore((s) => s.setLeftWidth);
  const setRightWidth = useUIStore((s) => s.setRightWidth);

  return (
    <div className="h-full flex flex-col">
      <Header />
      <nav
        aria-label="Dashboard controls"
        className="flex items-center gap-6 px-4 py-2 border-b border-border bg-panel/40 overflow-x-auto"
      >
        <TimeWindowChips />
        <span className="h-4 w-px bg-border" />
        <RegionChips />
      </nav>
      <main
        className="flex-1 grid min-h-0"
        style={{
          gridTemplateColumns: `${leftWidth}px 4px 1fr 4px ${rightWidth}px`,
        }}
      >
        <NewsPanel />
        <ResizeHandle
          side="left"
          ariaLabel="Resize news panel"
          onDelta={(dx) => setLeftWidth(leftWidth + dx)}
        />
        <WorldMap />
        <ResizeHandle
          side="right"
          ariaLabel="Resize impact panel"
          onDelta={(dx) => setRightWidth(rightWidth + dx)}
        />
        <ImpactPanel />
      </main>
    </div>
  );
}
