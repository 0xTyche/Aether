/** Tests for the panel-width clamping + map-min guard. */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  MAP_MIN_WIDTH,
  PANEL_MAX_WIDTH,
  PANEL_MIN_WIDTH,
  useUIStore,
} from "../ui";


function resetStore() {
  // Reset to defaults; window.innerWidth in happy-dom defaults to 1024.
  useUIStore.setState({ leftWidth: 320, rightWidth: 360 });
}

const ORIGINAL_INNER_WIDTH = (
  typeof window !== "undefined" ? window.innerWidth : 1024
);

function setViewportWidth(w: number) {
  Object.defineProperty(window, "innerWidth", { value: w, configurable: true });
}

describe("UI store — panel widths", () => {
  beforeEach(() => {
    setViewportWidth(1920); // generous viewport unless a test overrides
    resetStore();
  });
  afterEach(() => {
    setViewportWidth(ORIGINAL_INNER_WIDTH);
  });

  it("clamps left width to MIN", () => {
    const applied = useUIStore.getState().setLeftWidth(50);
    expect(applied).toBe(PANEL_MIN_WIDTH);
    expect(useUIStore.getState().leftWidth).toBe(PANEL_MIN_WIDTH);
  });

  it("clamps left width to MAX", () => {
    const applied = useUIStore.getState().setLeftWidth(9999);
    expect(applied).toBe(PANEL_MAX_WIDTH);
    expect(useUIStore.getState().leftWidth).toBe(PANEL_MAX_WIDTH);
  });

  it("clamps right width to MIN and MAX symmetrically", () => {
    expect(useUIStore.getState().setRightWidth(10)).toBe(PANEL_MIN_WIDTH);
    expect(useUIStore.getState().setRightWidth(99999)).toBe(PANEL_MAX_WIDTH);
  });

  it("rejects a width that would squeeze the map below MAP_MIN_WIDTH", () => {
    setViewportWidth(800); // tight viewport
    // left + right + handles must leave >= MAP_MIN_WIDTH for the map.
    // 800 - 200 - PANEL_MAX_WIDTH (600) - 8 = -8 → reject.
    useUIStore.setState({ leftWidth: 200, rightWidth: 200 });
    const before = useUIStore.getState().leftWidth;
    const applied = useUIStore.getState().setLeftWidth(500); // would make map = -8
    expect(applied).toBe(before); // unchanged
    expect(useUIStore.getState().leftWidth).toBe(before);
  });

  it("accepts a width that leaves exactly MAP_MIN_WIDTH for the map", () => {
    // viewport - left - right - 8 == MAP_MIN_WIDTH
    setViewportWidth(1200);
    useUIStore.setState({ leftWidth: 200, rightWidth: 200 });
    // Center is 1200 - 200 - 200 - 8 = 792. Try widening left by 392.
    const applied = useUIStore.getState().setLeftWidth(592);
    expect(applied).toBe(592); // 1200 - 592 - 200 - 8 = 400 == MAP_MIN_WIDTH
  });
});
