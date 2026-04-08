/**
 * TypeScript-Typen passend zu shared/contracts/schemas/drawing.schema.json
 * fuer LLM Structured Outputs / Frontend.
 */

export type DrawingSchemaVersion = "1.0";

export type DrawingType =
  | "support_zone"
  | "resistance_zone"
  | "trendline"
  | "breakout_box"
  | "liquidity_zone"
  | "target_zone"
  | "stop_zone";

export type DrawingStatus = "active" | "hit" | "invalidated" | "expired";

export type HorizontalZoneGeometry = {
  kind: "horizontal_zone";
  price_low: string;
  price_high: string;
  label?: string;
  rank?: number;
};

export type TimedPoint = {
  t_ms: number;
  price: string;
};

export type TwoPointLineGeometry = {
  kind: "two_point_line";
  point_a: TimedPoint;
  point_b: TimedPoint;
  direction?: "up" | "down";
};

export type PriceTimeBoxGeometry = {
  kind: "price_time_box";
  price_low: string;
  price_high: string;
  t_start_ms: number;
  t_end_ms: number | null;
};

export type DrawingGeometry =
  | HorizontalZoneGeometry
  | TwoPointLineGeometry
  | PriceTimeBoxGeometry;

export type DrawingRecord = {
  schema_version: DrawingSchemaVersion;
  drawing_id: string;
  parent_id: string;
  revision: number;
  symbol: string;
  timeframe: string;
  type: DrawingType;
  status: DrawingStatus;
  geometry: DrawingGeometry;
  style: Record<string, unknown>;
  confidence: number;
  reasons: string[];
  created_ts_ms: number;
  updated_ts_ms: number;
};
