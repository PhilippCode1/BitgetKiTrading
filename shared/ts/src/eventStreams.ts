/**
 * Synchron zu shared/contracts/catalog/event_streams.json (event_type + alle Streams).
 * Aenderungen: zuerst JSON, dann diese Datei und shared_py EventType-Literal anpassen.
 */
export const EVENT_TYPE_TO_STREAM = {
  market_tick: "events:market_tick",
  market_feed_health: "events:market_feed_health",
  candle_close: "events:candle_close",
  funding_update: "events:funding_update",
  structure_updated: "events:structure_updated",
  drawing_updated: "events:drawing_updated",
  signal_created: "events:signal_created",
  trade_opened: "events:trade_opened",
  trade_updated: "events:trade_updated",
  trade_closed: "events:trade_closed",
  funding_booked: "events:funding_booked",
  risk_alert: "events:risk_alert",
  learning_feedback: "events:learning_feedback",
  strategy_registry_updated: "events:strategy_registry_updated",
  news_item_created: "events:news_item_created",
  news_scored: "events:news_scored",
  llm_failed: "events:llm_failed",
  dlq: "events:dlq",
  system_alert: "events:system_alert",
  operator_intel: "events:operator_intel",
  tsfm_signal_candidate: "events:tsfm_signal_candidate",
  onchain_whale_detection: "events:onchain_whale_detection",
  orderbook_inconsistency: "events:orderbook_inconsistency",
  orderflow_toxicity: "events:orderflow_toxicity",
  social_sentiment_update: "events:social_sentiment_update",
  intermarket_correlation_update: "events:intermarket_correlation_update",
  regime_divergence_detected: "events:regime_divergence_detected",
  drift_event: "events:drift_event",
} as const;

export type EventBusEventType = keyof typeof EVENT_TYPE_TO_STREAM;

export const EVENT_STREAMS_ALL: readonly string[] =
  Object.values(EVENT_TYPE_TO_STREAM);

/** Gateway Live-SSE (/v1/live/stream) — Teilmenge */
export const LIVE_SSE_STREAMS = [
  "events:candle_close",
  "events:drawing_updated",
  "events:signal_created",
  "events:news_scored",
  "events:trade_opened",
  "events:trade_updated",
  "events:trade_closed",
  "events:market_feed_health",
] as const;

export type LiveSseStream = (typeof LIVE_SSE_STREAMS)[number];
