import { beforeAll, describe, expect, it } from "vitest";

import {
  getAllCountryCodes,
  getCountryAtCoordinates,
  getCountryNameByCode,
  iso3ToIso2Code,
  preloadCountryGeometry,
} from "../country-geometry";

describe("country-geometry (vendored from worldmonitor)", () => {
  beforeAll(async () => {
    await preloadCountryGeometry();
  });

  it("loads at least 100 country codes", () => {
    expect(getAllCountryCodes().length).toBeGreaterThan(100);
  });

  it("resolves New York City to US", () => {
    expect(getCountryAtCoordinates(40.7128, -74.006)?.code).toBe("US");
  });

  it("resolves Tokyo to JP", () => {
    expect(getCountryAtCoordinates(35.6762, 139.6503)?.code).toBe("JP");
  });

  it("resolves London to GB", () => {
    expect(getCountryAtCoordinates(51.5074, -0.1278)?.code).toBe("GB");
  });

  it("returns null for the middle of the Pacific Ocean", () => {
    expect(getCountryAtCoordinates(0, -160)).toBeNull();
  });

  it("converts ISO3 codes to ISO2", () => {
    expect(iso3ToIso2Code("USA")).toBe("US");
    expect(iso3ToIso2Code("JPN")).toBe("JP");
    expect(iso3ToIso2Code("DEU")).toBe("DE");
  });

  it("returns country names by ISO2", () => {
    expect(getCountryNameByCode("US")).toBeTruthy();
    expect(getCountryNameByCode("JP")).toBeTruthy();
  });
});
