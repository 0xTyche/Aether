import { useAssetsStore } from "../../store/assets";
import { useUIStore } from "../../store/ui";

/** Multi-select chips for the six economic regions. */
export function RegionChips() {
  const regions = useAssetsStore((s) => s.regions);
  const highlighted = useUIStore((s) => s.highlightedRegions);
  const toggleRegion = useUIStore((s) => s.toggleRegion);
  const clearRegions = useUIStore((s) => s.clearRegions);

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs uppercase tracking-wider text-muted">Regions</span>
      {regions.map((r) => {
        const on = highlighted.has(r.id);
        return (
          <button
            key={r.id}
            type="button"
            onClick={() => toggleRegion(r.id)}
            className={
              "px-2.5 py-0.5 rounded-full text-xs border transition-colors " +
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
          className="ml-1 text-xs text-muted hover:text-white"
        >
          clear
        </button>
      )}
    </div>
  );
}
