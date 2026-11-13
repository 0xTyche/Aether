import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeepAnalysis } from "../DeepAnalysis";


describe("DeepAnalysis", () => {
  it("renders nothing when analysis is null", () => {
    const { container } = render(<DeepAnalysis analysis={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing when both classification and chain are empty", () => {
    const { container } = render(<DeepAnalysis analysis={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it("starts collapsed and toggles on click", () => {
    render(
      <DeepAnalysis
        analysis={{
          classification: { primary_category: "宏观经济与政策类", shock_nature: ["折现率估值"] },
          transmission_chain: ["BoJ 加息", "套息平仓", "风险资产承压"],
        }}
      />,
    );
    const trigger = screen.getByRole("button", { name: /深度分析/ });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("BoJ 加息")).toBeNull();

    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(screen.queryByText("BoJ 加息")).not.toBeNull();
    expect(screen.queryByText("套息平仓")).not.toBeNull();
    expect(screen.queryByText("宏观经济与政策类")).not.toBeNull();
    expect(screen.queryByText("折现率估值")).not.toBeNull();
  });

  it("renders premise, mechanisms, off-pool assets and rejected candidates", () => {
    render(
      <DeepAnalysis
        analysis={{
          premise_check: "海啸预警已发布",
          mechanisms: [
            { id: "seismic", name: "强震与海啸", prior: 0.6, evidence_tier: "B", review_status: "draft" },
            { id: "export", name: "出口节点中断", prior: 0.65, evidence_tier: "B", review_status: "draft" },
          ],
          chain_prior: 0.39,
          off_pool: [
            {
              name: "原糖期货", ticker: "SB", market: "ICE", direction: "up",
              magnitude: "medium", confidence: 0.55, timeframe_min: 10080,
              crowding: "low", mechanism_id: "export", role: "commodity_price",
              rationale: "桑托斯港出口中断",
            },
          ],
          rejected: [{ target: "巴西股指", reason: "已被定价" }],
        }}
      />,
    );
    const trigger = screen.getByRole("button", { name: /深度分析/ });
    expect(trigger.textContent).toContain("池外 1 个");

    fireEvent.click(trigger);
    expect(screen.queryByText("海啸预警已发布")).not.toBeNull();
    expect(screen.queryByText("出口节点中断")).not.toBeNull();
    expect(screen.queryByText(/整链把握 39%/)).not.toBeNull();
    expect(screen.queryByText(/卡片尚未审核/)).not.toBeNull();
    expect(screen.queryByText("原糖期货")).not.toBeNull();
    expect(screen.queryByText("SB · ICE")).not.toBeNull();
    expect(screen.queryByText("1w · 易忽略")).not.toBeNull();
    expect(screen.queryByText("巴西股指")).not.toBeNull();
    expect(screen.queryByText("：已被定价")).not.toBeNull();
  });

  it("shows only the transmission chain when classification is missing", () => {
    render(
      <DeepAnalysis
        analysis={{ transmission_chain: ["step1", "step2"] }}
      />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByText("step1")).not.toBeNull();
    expect(screen.queryByText("分类")).toBeNull();
  });
});
