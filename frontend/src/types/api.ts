/** Shared TypeScript types mirroring `aether.api.schemas`. */

export interface Asset {
  id: string;
  asset_class: string;
  display_name: string;
  country_iso: string | null;
  region: string | null;
  lat: number | null;
  lng: number | null;
}

export interface Region {
  id: string;
  label_zh: string;
  label_en: string;
  region_type: string;
  central_bank: string | null;
  members: string[];
}

export interface ImpactPrediction {
  asset_id: string;
  direction: "up" | "down" | "neutral";
  magnitude: "small" | "medium" | "large";
  confidence: number | null;
  rationale: string | null;
  timeframe_min: number;
}

export interface Event {
  id: string;
  classifier: "rule" | "llm";
  rule_id: string | null;
  severity: "low" | "medium" | "high";
  origin_country: string | null;
  origin_lat: number | null;
  origin_lng: number | null;
  affected_regions: string[] | null;
  title: string;
  explanation: string | null;
  occurred_at: string;
  created_at: string;
  predictions: ImpactPrediction[];
}

export interface PriceTick {
  asset_id: string;
  price: string; // sent as string to preserve decimal precision
  ts: string;
  source: string;
}

/* ---------- WebSocket protocol ---------- */

export type WSChannel = "events" | "prices" | "impacts";

export interface WSWelcomeMessage {
  type: "welcome";
  ts: string;
}

export interface WSSubscribedMessage {
  type: "subscribed";
  channels: WSChannel[];
}

export interface WSEventMessage {
  type: "event.new";
  event: Event;
}

export interface WSPriceMessage {
  type: "price.update";
  ts: string;
  updates: PriceTick[];
}

export interface WSPongMessage {
  type: "pong";
  ts?: string;
}

export interface WSErrorMessage {
  type: "error";
  message: string;
}

export type WSServerMessage =
  | WSWelcomeMessage
  | WSSubscribedMessage
  | WSEventMessage
  | WSPriceMessage
  | WSPongMessage
  | WSErrorMessage;
