/**
 * 1:1 mit shared/contracts/schemas/payload_*.schema.json (Katalog: payload_schema_map.json).
 * Jede `payload_*.schema.json` hat genau einen `export type ...Payload` (Trade-Lifecycle fuer drei Event-Typen).
 */

import type { EventBusEventType } from "./eventStreams";

export type MarketTickPayload = { [k: string]: unknown };

export type MarketFeedHealthPayload = {
  ok: boolean;
  ws_connected: boolean;
  symbol: string;
  connection_state?: string;
  reasons?: string[];
  age_ticker_ms?: number | null;
  age_orderbook_ms?: number | null;
  age_trade_ms?: number | null;
  ready_max_age_ms?: number;
  orderbook_desynced?: boolean;
  last_gapfill_reason?: string | null;
  stale_escalation_count?: number;
};

export type CandleClosePayload = {
  start_ts_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  usdt_vol?: number;
  quote_vol?: number;
};

export type FundingUpdatePayload = { [k: string]: unknown };
export type StructureUpdatedPayload = { [k: string]: unknown };
export type DrawingUpdatedPayload = { [k: string]: unknown };

export type SignalCreatedPayload = {
  signal_id: string;
  direction: string;
  market_regime?: string;
  regime_bias?: string;
  regime_confidence_0_1?: number;
  signal_strength_0_100?: number;
  probability_0_1?: number;
};

export type TradeLifecyclePayload = {
  trade_id: string;
  symbol?: string;
  side?: string;
  status?: string;
  paper?: boolean;
};

export type FundingBookedPayload = { [k: string]: unknown };
export type RiskAlertPayload = { [k: string]: unknown };
export type LearningFeedbackPayload = { [k: string]: unknown };
export type StrategyRegistryUpdatedPayload = { [k: string]: unknown };
export type NewsItemCreatedPayload = { [k: string]: unknown };
export type NewsScoredPayload = { [k: string]: unknown };
export type LlmFailedPayload = { [k: string]: unknown };
export type DlqPayload = { [k: string]: unknown };
export type SystemAlertPayload = { [k: string]: unknown };
export type OperatorIntelPayload = { [k: string]: unknown };
export type TsfmSignalCandidatePayload = { [k: string]: unknown };
export type OnchainWhaleDetectionPayload = { [k: string]: unknown };
export type OrderbookInconsistencyPayload = { [k: string]: unknown };
export type OrderflowToxicityPayload = { [k: string]: unknown };
export type SocialSentimentUpdatePayload = { [k: string]: unknown };
export type IntermarketCorrelationUpdatePayload = { [k: string]: unknown };
export type RegimeDivergenceDetectedPayload = { [k: string]: unknown };
export type DriftEventPayload = { [k: string]: unknown };

export type EventPayloadByType = {
  market_tick: MarketTickPayload;
  market_feed_health: MarketFeedHealthPayload;
  candle_close: CandleClosePayload;
  funding_update: FundingUpdatePayload;
  structure_updated: StructureUpdatedPayload;
  drawing_updated: DrawingUpdatedPayload;
  signal_created: SignalCreatedPayload;
  trade_opened: TradeLifecyclePayload;
  trade_updated: TradeLifecyclePayload;
  trade_closed: TradeLifecyclePayload;
  funding_booked: FundingBookedPayload;
  risk_alert: RiskAlertPayload;
  learning_feedback: LearningFeedbackPayload;
  strategy_registry_updated: StrategyRegistryUpdatedPayload;
  news_item_created: NewsItemCreatedPayload;
  news_scored: NewsScoredPayload;
  llm_failed: LlmFailedPayload;
  dlq: DlqPayload;
  system_alert: SystemAlertPayload;
  operator_intel: OperatorIntelPayload;
  tsfm_signal_candidate: TsfmSignalCandidatePayload;
  onchain_whale_detection: OnchainWhaleDetectionPayload;
  orderbook_inconsistency: OrderbookInconsistencyPayload;
  orderflow_toxicity: OrderflowToxicityPayload;
  social_sentiment_update: SocialSentimentUpdatePayload;
  intermarket_correlation_update: IntermarketCorrelationUpdatePayload;
  regime_divergence_detected: RegimeDivergenceDetectedPayload;
  drift_event: DriftEventPayload;
};

export type EnvelopeV1For<E extends EventBusEventType> = {
  event_type: E;
  payload: EventPayloadByType[E];
};
