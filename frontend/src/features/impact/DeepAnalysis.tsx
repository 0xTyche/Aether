/** Collapsible "深度分析" section under the event header.
 *
 *  Visible only when the event has any analysis fields populated
 *  (rule-engine events have analysis=null and the component returns null).
 */

import { useState } from "react";

import type { Crowding, EventAnalysis, OffPoolImpact } from "../../types/api";

interface DeepAnalysisProps {
  analysis: EventAnalysis | null;
}

const CROWDING_LABEL: Record<Crowding, string> = {
  high: "拥挤",
  medium: "一般",
  low: "易忽略",
};

const ARROW: Record<OffPoolImpact["direction"], string> = {
  up: "↑",
  down: "↓",
  neutral: "→",
};

/** 1440 -> "1d", 240 -> "4h", 15 -> "15m". */
function formatHorizon(minutes: number): string {
  if (minutes > 0 && minutes % 10080 === 0) return `${minutes / 10080}w`;
  if (minutes > 0 && minutes % 1440 === 0) return `${minutes / 1440}d`;
  if (minutes > 0 && minutes % 60 === 0) return `${minutes / 60}h`;
  return `${minutes}m`;
}

function SectionTitle({ children }: { children: string }) {
  return (
    <div className="text-[10px] uppercase tracking-wider text-muted mb-1.5">{children}</div>
  );
}

export function DeepAnalysis({ analysis }: DeepAnalysisProps) {
  const [open, setOpen] = useState(false);

  if (!analysis) return null;
  const cls = analysis.classification;
  const chain = analysis.transmission_chain ?? [];
  const mechanisms = analysis.mechanisms ?? [];
  const offPool = analysis.off_pool ?? [];
  const rejected = analysis.rejected ?? [];
  const premise = analysis.premise_check ?? "";
  const hasClassification = cls && (cls.primary_category || cls.shock_nature.length > 0);
  const hasChain = chain.length > 0;
  if (
    !hasClassification &&
    !hasChain &&
    !premise &&
    mechanisms.length === 0 &&
    offPool.length === 0 &&
    rejected.length === 0
  ) {
    return null;
  }

  const summary = [
    chain.length > 0 ? `${chain.length} 步传导链` : hasClassification ? "已分类" : null,
    offPool.length > 0 ? `池外 ${offPool.length} 个` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const anyDraft = mechanisms.some((m) => m.review_status !== "approved");

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
            点击展开 · {summary}
          </span>
        )}
      </button>

      {open && (
        <div className="px-4 py-3 space-y-3 bg-bg/30">
          {hasClassification && cls && (
            <section>
              <SectionTitle>分类</SectionTitle>
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

          {premise && (
            <section>
              <SectionTitle>前提核查</SectionTitle>
              <p className="text-xs leading-snug">{premise}</p>
            </section>
          )}

          {mechanisms.length > 0 && (
            <section>
              <SectionTitle>机制</SectionTitle>
              <div className="flex flex-wrap items-center gap-1.5">
                {mechanisms.map((m, i) => (
                  <span key={m.id} className="flex items-center gap-1.5">
                    {i > 0 && <span className="text-muted text-[10px]">→</span>}
                    <span
                      title={`${m.id} · 先验 ${Math.round(m.prior * 100)}% · ${m.evidence_tier} 级`}
                      className="text-xs px-2 py-0.5 rounded bg-border/60"
                    >
                      {m.name}
                    </span>
                  </span>
                ))}
              </div>
              {analysis.chain_prior != null && (
                <div className="mt-1.5 text-[10px] text-muted">
                  整链把握 {Math.round(analysis.chain_prior * 100)}%（各卡先验相乘
                  {anyDraft ? "，卡片尚未审核" : ""}）
                </div>
              )}
            </section>
          )}

          {hasChain && (
            <section>
              <SectionTitle>传导链</SectionTitle>
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

          {offPool.length > 0 && (
            <section>
              <SectionTitle>资产池外</SectionTitle>
              <ul className="space-y-1.5">
                {offPool.map((o, i) => (
                  <li key={`${o.name}-${i}`} className="text-xs leading-snug">
                    <div className="flex flex-wrap items-baseline gap-x-1.5">
                      <span className="font-mono">{ARROW[o.direction]}</span>
                      <span>{o.name}</span>
                      {(o.ticker || o.market) && (
                        <span className="text-[10px] text-muted font-mono">
                          {[o.ticker, o.market].filter(Boolean).join(" · ")}
                        </span>
                      )}
                      <span className="text-[10px] text-muted">
                        {formatHorizon(o.timeframe_min)}
                        {o.crowding ? ` · ${CROWDING_LABEL[o.crowding]}` : ""}
                      </span>
                    </div>
                    {o.rationale && <div className="text-muted">{o.rationale}</div>}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {rejected.length > 0 && (
            <section>
              <SectionTitle>放弃的候选</SectionTitle>
              <ul className="space-y-1">
                {rejected.map((r, i) => (
                  <li key={`${r.target}-${i}`} className="text-xs leading-snug">
                    <span>{r.target}</span>
                    {r.reason && <span className="text-muted">：{r.reason}</span>}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
