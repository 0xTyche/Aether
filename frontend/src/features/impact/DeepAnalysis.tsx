/** Collapsible "深度分析" section under the event header.
 *
 *  Visible only when the event has any analysis fields populated
 *  (rule-engine events have analysis=null and the component returns null).
 */

import { useState } from "react";

import type { EventAnalysis } from "../../types/api";

interface DeepAnalysisProps {
  analysis: EventAnalysis | null;
}

export function DeepAnalysis({ analysis }: DeepAnalysisProps) {
  const [open, setOpen] = useState(false);

  if (!analysis) return null;
  const cls = analysis.classification;
  const chain = analysis.transmission_chain ?? [];
  const hasClassification = cls && (cls.primary_category || cls.shock_nature.length > 0);
  const hasChain = chain.length > 0;
  if (!hasClassification && !hasChain) return null;

  return (
    <div className="border-t border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="w-full flex items-center gap-2 px-4 py-2 text-xs uppercase tracking-wider text-muted hover:bg-border/30 transition-colors"
      >
        <span className={"inline-block transition-transform " + (open ? "rotate-90" : "")}>
          ▶
        </span>
        <span>深度分析</span>
        {!open && (
          <span className="ml-auto normal-case text-[10px] text-muted/70">
            点击展开 · {chain.length > 0 ? `${chain.length} 步传导链` : "已分类"}
          </span>
        )}
      </button>

      {open && (
        <div className="px-4 py-3 space-y-3 bg-bg/30">
          {hasClassification && cls && (
            <section>
              <div className="text-[10px] uppercase tracking-wider text-muted mb-1.5">
                分类
              </div>
              <div className="flex flex-wrap items-center gap-1.5">
                {cls.primary_category && (
                  <span className="text-xs px-2 py-0.5 rounded bg-accent/15 text-accent">
                    {cls.primary_category}
                  </span>
                )}
                {cls.shock_nature.map((s) => (
                  <span
                    key={s}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-border/60 font-mono text-muted"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </section>
          )}

          {hasChain && (
            <section>
              <div className="text-[10px] uppercase tracking-wider text-muted mb-1.5">
                传导链
              </div>
              <ol className="space-y-1.5">
                {chain.map((step, i) => (
                  <li key={i} className="flex gap-2 text-xs leading-snug">
                    <span className="font-mono text-muted shrink-0 w-5">
                      {i + 1}.
                    </span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
