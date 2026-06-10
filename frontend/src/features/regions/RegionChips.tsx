import { useAssetsStore } from "../../store/assets";
import { useUIStore } from "../../store/ui";

/**
 * Top row — multi-select chips for the six economic regions.
 * Phase 4.b: simple toggle UX. Map highlighting wires up in 4.c.
 */
export function RegionChips() {
  const regions = useAssetsStore((s) => s.regions);
  const highlighted = useUIStore((s) => s.highlightedRegions);
  const toggleRegion = useUIStore((s) => s.toggleRegion);
  const clearRegions = useUIStore((s) => s.clearRegions);

  return (
    <nav
      aria-label="Economic regions"
      className="flex items-center gap-2 px-4 py-2 border-b border-border bg-panel/40"
    >
      <span className="text-xs uppercase tracking-wider text-muted mr-1">
        Regions
      </span>
      {regions.map((r) => {
        const on = highlighted.has(r.id);
        return (
          <button
            key={r.id}
            type="button"
            onClick={() => toggleRegion(r.id)}
            className={
              "px-2.5 py-1 rounded-full text-xs border transition-colors " +
              (on
                ? "bg-accent/20 border-accent text-accent"
                : "border-border text-muted hover:text-white hover:border-muted")
            }
            title={`${r.label_en} (${r.members.length} members)`}
          >
            {r.label_zh}
          </button>
        );
      })}
      {highlighted.size > 0 && (
        <button
          type="button"
          onClick={clearRegions}
          className="ml-2 text-xs text-muted hover:text-white"
        >
          clear
        </button>
      )}
    </nav>
  );
}
