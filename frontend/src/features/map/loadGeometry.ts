import type { Feature, FeatureCollection, Geometry, GeoJsonProperties } from "geojson";

const BASE_URL = "/vendor/worldmonitor/countries.geojson";
const WM_OVERRIDES_URL = "/vendor/worldmonitor/country-boundary-overrides.geojson";
const LOCAL_OVERRIDES_URL = "/data/boundary-overrides.geojson";

const FETCH_TIMEOUT_MS = 8_000;

type CountryFC = FeatureCollection<Geometry, GeoJsonProperties>;

async function fetchGeoJson(url: string, optional = false): Promise<CountryFC | null> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      if (optional) return null;
      throw new Error(`failed to load ${url}: HTTP ${res.status}`);
    }
    return (await res.json()) as CountryFC;
  } catch (err) {
    if (optional) return null;
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

function isoOf(f: Feature): string | null {
  const p = f.properties ?? {};
  const raw =
    (p["ISO3166-1-Alpha-2"] as string | undefined) ??
    (p.ISO_A2 as string | undefined) ??
    (p.iso_a2 as string | undefined);
  if (typeof raw !== "string") return null;
  const code = raw.trim().toUpperCase();
  return /^[A-Z]{2}$/.test(code) ? code : null;
}

function applyOverrides(base: CountryFC, overrides: CountryFC[]): CountryFC {
  const byIso = new Map<string, Feature>();
  for (const f of base.features) {
    const code = isoOf(f);
    if (code) byIso.set(code, f);
  }
  for (const layer of overrides) {
    for (const f of layer.features) {
      const code = isoOf(f);
      if (code) byIso.set(code, f);
    }
  }
  return { type: "FeatureCollection", features: Array.from(byIso.values()) };
}

let cache: Promise<CountryFC> | null = null;

export function loadCountryGeometry(): Promise<CountryFC> {
  if (!cache) cache = load();
  return cache;
}

async function load(): Promise<CountryFC> {
  const [base, wm, local] = await Promise.all([
    fetchGeoJson(BASE_URL, false),
    fetchGeoJson(WM_OVERRIDES_URL, true),
    fetchGeoJson(LOCAL_OVERRIDES_URL, true),
  ]);
  if (!base) throw new Error("base country geometry failed to load");
  const layers = [wm, local].filter((x): x is CountryFC => x !== null);
  return applyOverrides(base, layers);
}

export function resetGeometryCache(): void {
  cache = null;
}
