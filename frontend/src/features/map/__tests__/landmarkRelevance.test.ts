import { describe, expect, it } from "vitest";

import type { Event } from "../../../types/api";
import { eventsForLandmark, isEventRelevant } from "../landmarkRelevance";
import type { Landmark } from "../landmarks";

function mkEvent(over: Partial<Event>): Event {
  return {
    id: "e1",
    classifier: "rule",
    rule_id: null,
    severity: "low",
    origin_country: null,
    origin_lat: null,
    origin_lng: null,
    affected_regions: null,
    title: "",
    explanation: null,
    analysis: null,
    occurred_at: "2026-06-14T10:00:00Z",
    created_at: "2026-06-14T10:00:00Z",
    predictions: [],
    ...over,
  };
}

const PBOC: Landmark = {
  id: "cb-pboc",
  name_zh: "中国人民银行",
  name_en: "PBoC",
  lat: 39.9,
  lng: 116.4,
  category: "central-bank",
  countries: ["CN"],
  keywords: ["PBoC", "人民银行"],
};

const HORMUZ: Landmark = {
  id: "ww-hormuz",
  name_zh: "霍尔木兹",
  name_en: "Hormuz",
  lat: 26.5,
  lng: 56.3,
  category: "strategic-waterway",
  keywords: ["Hormuz", "霍尔木兹"],
};

const GHAWAR: Landmark = {
  id: "ch-ghawar",
  name_zh: "Ghawar",
  name_en: "Ghawar",
  lat: 25.4,
  lng: 49.6,
  category: "commodity-hub",
  asset_ids: ["BRENT", "WTI"],
  keywords: ["Saudi", "OPEC"],
};

describe("isEventRelevant", () => {
  it("matches central bank by origin_country", () => {
    expect(isEventRelevant(mkEvent({ origin_country: "CN" }), PBOC)).toBe(true);
    expect(isEventRelevant(mkEvent({ origin_country: "JP" }), PBOC)).toBe(false);
  });

  it("matches central bank by keyword in title", () => {
    expect(isEventRelevant(mkEvent({ title: "人民银行降准 50bp" }), PBOC)).toBe(true);
  });

  it("matches commodity hub by asset_id in predictions", () => {
    const e = mkEvent({
      predictions: [{ asset_id: "BRENT", direction: "up", magnitude: "medium", confidence: 0.7, rationale: null, timeframe_min: 60 }],
    });
    expect(isEventRelevant(e, GHAWAR)).toBe(true);
  });

  it("matches waterway by keyword (case-insensitive)", () => {
    expect(isEventRelevant(mkEvent({ title: "Tanker stuck near hormuz" }), HORMUZ)).toBe(true);
  });

  it("matches keywords against explanation as well as title", () => {
    expect(isEventRelevant(mkEvent({ title: "X", explanation: "Saudi production cut" }), GHAWAR)).toBe(true);
  });

  it("returns false when nothing matches", () => {
    expect(isEventRelevant(mkEvent({ title: "Unrelated tech earnings" }), PBOC)).toBe(false);
  });
});

describe("eventsForLandmark", () => {
  it("sorts high severity before medium / low and caps at limit", () => {
    const events: Event[] = [
      mkEvent({ id: "1", origin_country: "CN", severity: "low", occurred_at: "2026-06-14T10:00:00Z" }),
      mkEvent({ id: "2", origin_country: "CN", severity: "high", occurred_at: "2026-06-14T09:00:00Z" }),
      mkEvent({ id: "3", origin_country: "CN", severity: "medium", occurred_at: "2026-06-14T11:00:00Z" }),
    ];
    const out = eventsForLandmark(events, PBOC);
    expect(out.map((e) => e.id)).toEqual(["2", "3", "1"]);
  });

  it("respects the limit", () => {
    const events: Event[] = Array.from({ length: 8 }, (_, i) =>
      mkEvent({ id: String(i), origin_country: "CN" }),
    );
    expect(eventsForLandmark(events, PBOC, 3)).toHaveLength(3);
  });

  it("returns [] when no events match", () => {
    expect(eventsForLandmark([mkEvent({ origin_country: "JP" })], PBOC)).toEqual([]);
  });
});
