/** Country polygon styling shared between idle and event-driven layers. */

import type { Feature } from "geojson";

export type RGBA = [number, number, number, number];

const COLOR_BASE: RGBA = [30, 41, 59, 25];        // subtle slate fill
const COLOR_HOVER: RGBA = [148, 163, 184, 60];    // muted blue-grey
const COLOR_ORIGIN: RGBA = [248, 113, 113, 130];  // red — event source
const COLOR_REGION: RGBA = [96, 165, 250, 65];    // accent blue
const STROKE: RGBA = [148, 163, 184, 90];

/** ISO 3166-1 alpha-2 for a feature, or null if absent. */
export function isoOf(f: Feature): string | null {
  const p = f.properties ?? {};
  const raw =
    (p["ISO3166-1-Alpha-2"] as string | undefined) ??
    (p.ISO_A2 as string | undefined) ??
    (p.iso_a2 as string | undefined);
  if (typeof raw !== "string") return null;
  const code = raw.trim().toUpperCase();
  return /^[A-Z]{2}$/.test(code) ? code : null;
}

export interface CountryFillContext {
  hoveredISO: string | null;
  originISO: string | null;
  highlightedISOs: Set<string>;
}

export function fillFor(f: Feature, ctx: CountryFillContext): RGBA {
  const iso = isoOf(f);
  if (!iso) return COLOR_BASE;
  if (iso === ctx.originISO) return COLOR_ORIGIN;
  if (ctx.highlightedISOs.has(iso)) return COLOR_REGION;
  if (iso === ctx.hoveredISO) return COLOR_HOVER;
  return COLOR_BASE;
}

export const STROKE_COLOR = STROKE;
