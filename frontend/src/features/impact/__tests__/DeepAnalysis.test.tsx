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
