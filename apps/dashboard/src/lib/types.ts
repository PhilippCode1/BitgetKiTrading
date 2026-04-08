/** Live-Terminal API (api-gateway /v1/live/state) */

import type { GatewayReadEnvelope } from "@bitget-btc-ai/shared-ts";

export type {
  EventBusEventType,
  EventEnvelopeV1,
  GatewayReadEnvelope,
  GatewayReadStatus,
} from "@bitget-btc-ai/shared-ts";

export type LiveCandle = {
  time_s: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume_usdt: number;
};

export type LivePriceLine = {
  price: number;
  title: string;
  color: string;
};

export type LiveTrendline = {
  t0_ms: number;
  p0: number;
  t1_ms: number;
  p1: number;
  color: string;
};

export type LiveDrawing = {
  drawing_id: string;
  type: string;
  timeframe?: string;
  status?: string;
  confidence?: number | null;
  reasons_json: unknown[];
  price_lines: LivePriceLine[];
  trendline: LiveTrendline | null;
  updated_ts_ms?: number | null;
};

export type LiveSignal = {
  signal_id: string;
  direction: string;
  canonical_instrument_id?: string | null;
  market_family?: string | null;
  margin_account_mode?: string | null;
  strategy_name?: string | null;
  playbook_id?: string | null;
  playbook_family?: string | null;
  playbook_decision_mode?: string | null;
  market_regime?: string | null;
  regime_state?: string | null;
  regime_substate?: string | null;
  regime_transition_state?: string | null;
  regime_transition_reasons_json?: unknown[];
  regime_persistence_bars?: number | null;
  regime_policy_version?: string | null;
  regime_bias?: string | null;
  regime_confidence_0_1?: number | null;
  regime_reasons_json?: unknown[];
  signal_strength_0_100: number;
  probability_0_1: number;
  take_trade_prob?: number | null;
  take_trade_model_version?: string | null;
  take_trade_model_run_id?: string | null;
  take_trade_calibration_method?: string | null;
  expected_return_bps?: number | null;
  expected_mae_bps?: number | null;
  expected_mfe_bps?: number | null;
  target_projection_models_json?: unknown[];
  model_uncertainty_0_1?: number | null;
  uncertainty_effective_for_leverage_0_1?: number | null;
  shadow_divergence_0_1?: number | null;
  model_ood_score_0_1?: number | null;
  model_ood_alert?: boolean;
  uncertainty_reasons_json?: unknown[];
  ood_reasons_json?: unknown[];
  abstention_reasons_json?: unknown[];
  trade_action?: string | null;
  meta_decision_action?: string | null;
  meta_decision_kernel_version?: string | null;
  meta_trade_lane?: string | null;
  decision_confidence_0_1?: number | null;
  decision_policy_version?: string | null;
  live_execution_block_reasons_json?: unknown[];
  governor_universal_hard_block_reasons_json?: unknown[];
  live_execution_clear_for_real_money?: boolean;
  stop_distance_pct?: number | null;
  stop_budget_max_pct_allowed?: number | null;
  stop_min_executable_pct?: number | null;
  stop_fragility_0_1?: number | null;
  stop_executability_0_1?: number | null;
  stop_quality_0_1?: number | null;
  stop_to_spread_ratio?: number | null;
  allowed_leverage?: number | null;
  recommended_leverage?: number | null;
  leverage_policy_version?: string | null;
  leverage_cap_reasons_json?: unknown[];
  instrument_metadata_snapshot_id?: string | null;
  instrument_metadata?: Record<string, unknown> | null;
  signal_class: string;
  decision_state?: string;
  explain_short?: string | null;
  explain_long_md?: string | null;
  risk_warnings_json: unknown[];
  reasons_json?: unknown[];
  [key: string]: unknown;
};

export type LiveNewsItem = {
  news_id: string;
  title?: string | null;
  published_ts_ms?: number | null;
  relevance_score?: number | null;
  sentiment?: string;
  summary?: string;
};

export type LiveFeatureSnapshot = {
  canonical_instrument_id?: string | null;
  market_family?: string | null;
  symbol: string;
  timeframe: string;
  start_ts_ms: number;
  computed_ts_ms: number;
  spread_bps?: number | null;
  bid_depth_usdt_top25?: number | null;
  ask_depth_usdt_top25?: number | null;
  orderbook_imbalance?: number | null;
  depth_balance_ratio?: number | null;
  depth_to_bar_volume_ratio?: number | null;
  impact_buy_bps_5000?: number | null;
  impact_sell_bps_5000?: number | null;
  impact_buy_bps_10000?: number | null;
  impact_sell_bps_10000?: number | null;
  execution_cost_bps?: number | null;
  volatility_cost_bps?: number | null;
  funding_rate_bps?: number | null;
  funding_cost_bps_window?: number | null;
  open_interest?: number | null;
  open_interest_change_pct?: number | null;
  data_completeness_0_1?: number | null;
  staleness_score_0_1?: number | null;
  feature_quality_status?: string | null;
  orderbook_age_ms?: number | null;
  funding_age_ms?: number | null;
  open_interest_age_ms?: number | null;
  liquidity_source?: string | null;
  funding_source?: string | null;
  open_interest_source?: string | null;
};

/** Teilstrecke Markt → Dashboard (Gateway-Feld `data_lineage`). */
export type LiveDataLineageSegment = {
  segment_id: string;
  label_de: string;
  label_en: string;
  has_data: boolean;
  producer_de: string;
  producer_en: string;
  why_empty_de: string;
  why_empty_en: string;
  next_step_de: string;
  next_step_en: string;
  /** Optional: maschinenlesbare Ursachenklassen bei leerem Segment. */
  diagnostic_tags?: string[];
};

/** Gateway: Kurzsummary aus `app.structure_state` (optional). */
export type LiveStructureStateSummary = {
  symbol: string;
  timeframe: string;
  last_ts_ms: number;
  trend_dir: string;
  updated_ts_ms: number | null;
  compression_flag: boolean;
};

export type LiveOnlineDriftSnapshot = {
  scope: string;
  effective_action: string;
  computed_at: string | null;
  lookback_minutes?: number | null;
  breakdown_json: Record<string, unknown>;
};

export type LivePaperState = {
  open_positions: Array<{
    position_id: string;
    side: string;
    qty_base: string;
    entry_price_avg: string;
    unrealized_pnl_usdt: number;
  }>;
  last_closed_trade: Record<string, unknown> | null;
  unrealized_pnl_usdt: number;
  mark_price: number | null;
};

/** Gateway: immer `ok` | `error` | `skipped`; `unknown` nur Dashboard-Platzhalter ohne Gateway. */
export type LiveStateHealthDatastore = "ok" | "error" | "skipped" | "unknown";

/** Gateway /v1/live/state: Kerzen- und Ticker-Frische (Bitget-Pipeline). */
export type LiveMarketFreshnessStatus =
  | "live"
  | "delayed"
  | "stale"
  | "dead"
  | "no_candles"
  | "unknown_timeframe";

export type LiveMarketFreshnessCandle = {
  last_start_ts_ms: number;
  last_ingest_ts_ms: number;
  bar_duration_ms: number;
  aligned_bucket_start_ms: number;
  bar_lag_ms: number;
  ingest_age_ms: number;
};

export type LiveMarketFreshnessTicker = {
  exchange_ts_ms: number;
  ingest_ts_ms: number;
  quote_age_ms: number;
  ingest_age_ms: number;
  last_pr: number | null;
};

export type LiveMarketFreshness = {
  status: LiveMarketFreshnessStatus;
  timeframe: string;
  stale_warn_ms: number;
  candle: LiveMarketFreshnessCandle | null;
  ticker: LiveMarketFreshnessTicker | null;
};

/** Gateway GET /v1/live/state — Hinweis auf Demo-/Fixture-Pfade (kein Live-Handel). */
export type DemoDataNotice = {
  show_banner: boolean;
  reasons: string[];
};

export type LiveStateResponse = GatewayReadEnvelope & {
  /** Gateway: 1+; Dashboard-Platzhalter ohne erfolgreichen Fetch: 0. */
  live_state_contract_version: number;
  symbol: string;
  timeframe: string;
  server_ts_ms: number;
  /** Immer Array (leer = cold / keine Kerzen in tsdb fuer Symbol+TF). */
  candles: LiveCandle[];
  /** null = kein Signal fuer Symbol+TF (nicht zwingend Fehler). */
  latest_signal: LiveSignal | null;
  latest_feature?: LiveFeatureSnapshot | null;
  structure_state?: LiveStructureStateSummary | null;
  latest_drawings: LiveDrawing[];
  latest_news: LiveNewsItem[];
  paper_state: LivePaperState;
  health: { db: LiveStateHealthDatastore; redis: LiveStateHealthDatastore };
  online_drift?: LiveOnlineDriftSnapshot | null;
  /** Immer gesetzt (Gateway); leeres Array bei DB-Fehler moeglich nach lineage-Build. */
  data_lineage: LiveDataLineageSegment[];
  /** Immer gesetzt; bei DB-Fehler oft `no_candles` mit candle/ticker null. */
  market_freshness: LiveMarketFreshness;
  demo_data_notice: DemoDataNotice;
};

/** Prompt 26 — Dashboard APIs */

export type StrategyScopeSnapshot = {
  venue?: string | null;
  symbol?: string | null;
  market_family?: string | null;
  canonical_instrument_id?: string | null;
  category_key?: string | null;
  product_type?: string | null;
  margin_coin?: string | null;
  margin_account_mode?: string | null;
  base_coin?: string | null;
  quote_coin?: string | null;
  settle_coin?: string | null;
  metadata_source?: string | null;
  metadata_verified?: boolean | null;
  inventory_visible?: boolean | null;
  analytics_eligible?: boolean | null;
  paper_shadow_eligible?: boolean | null;
  live_execution_enabled?: boolean | null;
  execution_disabled?: boolean | null;
  supports_funding?: boolean | null;
  supports_open_interest?: boolean | null;
  supports_long_short?: boolean | null;
  supports_shorting?: boolean | null;
  supports_reduce_only?: boolean | null;
  supports_leverage?: boolean | null;
  timeframes?: string[];
};

export type MarketUniverseConfigSnapshot = {
  market_families: string[];
  universe_symbols: string[];
  watchlist_symbols: string[];
  feature_scope: {
    symbols: string[];
    timeframes: string[];
  };
  signal_scope_symbols: string[];
  family_defaults: Record<string, Record<string, unknown>>;
  live_allowlists: {
    symbols: string[];
    market_families: string[];
    product_types: string[];
  };
  catalog_policy: {
    refresh_interval_sec: number;
    cache_ttl_sec: number;
    max_stale_sec: number;
    unknown_instrument_action: string;
  };
};

export type MarketUniverseCategoryRow = {
  schema_version: string;
  venue: string;
  market_family: string;
  product_type?: string | null;
  margin_account_mode: string;
  category_key: string;
  metadata_source: string;
  metadata_verified: boolean;
  inventory_visible: boolean;
  analytics_eligible: boolean;
  paper_shadow_eligible: boolean;
  live_execution_enabled: boolean;
  execution_disabled: boolean;
  supports_funding: boolean;
  supports_open_interest: boolean;
  supports_long_short: boolean;
  supports_shorting: boolean;
  supports_reduce_only: boolean;
  supports_leverage: boolean;
  uses_spot_public_market_data: boolean;
  instrument_count: number;
  tradeable_instrument_count: number;
  subscribable_instrument_count: number;
  metadata_verified_count: number;
  sample_symbols: string[];
  reasons: string[];
};

export type MarketUniverseInstrumentItem = {
  schema_version: string;
  venue: string;
  market_family: string;
  symbol: string;
  canonical_instrument_id: string;
  category_key: string;
  product_type?: string | null;
  margin_coin?: string | null;
  margin_account_mode: string;
  base_coin?: string | null;
  quote_coin?: string | null;
  settle_coin?: string | null;
  metadata_source: string;
  metadata_verified: boolean;
  inventory_visible: boolean;
  analytics_eligible: boolean;
  paper_shadow_eligible: boolean;
  live_execution_enabled: boolean;
  execution_disabled: boolean;
  supports_funding: boolean;
  supports_open_interest: boolean;
  supports_long_short: boolean;
  supports_shorting: boolean;
  supports_reduce_only: boolean;
  supports_leverage: boolean;
  uses_spot_public_market_data: boolean;
  trading_status: string;
  trading_enabled: boolean;
  subscribe_enabled: boolean;
  symbol_aliases: string[];
  price_tick_size?: string | null;
  quantity_step?: string | null;
  quantity_min?: string | null;
  quantity_max?: string | null;
  market_order_quantity_max?: string | null;
  min_notional_quote?: string | null;
  leverage_min?: number | null;
  leverage_max?: number | null;
  funding_interval_hours?: number | null;
  symbol_type?: string | null;
  supported_margin_coins: string[];
  refresh_ts_ms?: number | null;
};

export type MarketUniverseStatusResponse = GatewayReadEnvelope & {
  schema_version: string;
  configuration: MarketUniverseConfigSnapshot;
  snapshot: {
    snapshot_id: string;
    status: string;
    source_service: string;
    refresh_reason: string;
    fetch_started_ts_ms: number;
    fetch_completed_ts_ms: number | null;
    refreshed_families: string[];
    counts_by_family: Record<string, number>;
    warnings: string[];
    errors: string[];
  } | null;
  summary: {
    category_count: number;
    instrument_count: number;
    inventory_visible_category_count: number;
    analytics_eligible_category_count: number;
    paper_shadow_eligible_category_count: number;
    live_execution_enabled_category_count: number;
    execution_disabled_category_count: number;
    inventory_visible_instrument_count: number;
    analytics_eligible_instrument_count: number;
    paper_shadow_eligible_instrument_count: number;
    live_execution_enabled_instrument_count: number;
    execution_disabled_instrument_count: number;
  };
  categories: MarketUniverseCategoryRow[];
  instruments: MarketUniverseInstrumentItem[];
};

export type SignalOutcomeBadge = {
  evaluations_count: number;
  wins: number;
  losses: number;
  win_rate: number;
};

/** Gruppierte Gateway-Sicht; spiegelt `api_gateway.signal_contract` (ohne flache Felder zu ersetzen). */
export type SignalViewGroup = Record<string, unknown>;

export type SignalViewList = {
  contract_version: string;
  identity: SignalViewGroup;
  decision_and_status: SignalViewGroup;
  strategy_and_routing: SignalViewGroup;
  regime: SignalViewGroup;
  scores_and_leverage: SignalViewGroup;
  risk_stops: SignalViewGroup;
  risk_governor: SignalViewGroup;
  execution_and_alerts: SignalViewGroup;
  outcome: SignalViewGroup;
  deterministic_engine: Record<string, unknown>;
};

export type SignalViewDetail = Omit<SignalViewList, "deterministic_engine"> & {
  instrument_and_metadata: SignalViewGroup;
  scoring_diagnostics: SignalViewGroup;
  portfolio: SignalViewGroup;
  deterministic_engine: Record<string, unknown>;
};

export type SignalExplainLayers = {
  persisted_narrative: Record<string, unknown>;
  deterministic_engine: Record<string, unknown>;
  live_llm_advisory: Record<string, unknown>;
};

export type SignalRecentItem = {
  signal_id: string;
  symbol: string;
  timeframe: string;
  direction: string;
  market_regime?: string | null;
  regime_bias?: string | null;
  regime_confidence_0_1?: number | null;
  signal_strength_0_100: number;
  probability_0_1: number;
  take_trade_prob?: number | null;
  take_trade_model_version?: string | null;
  take_trade_model_run_id?: string | null;
  take_trade_calibration_method?: string | null;
  expected_return_bps?: number | null;
  expected_mae_bps?: number | null;
  expected_mfe_bps?: number | null;
  model_uncertainty_0_1?: number | null;
  uncertainty_effective_for_leverage_0_1?: number | null;
  model_ood_alert?: boolean;
  trade_action?: string | null;
  meta_decision_action?: string | null;
  meta_decision_kernel_version?: string | null;
  meta_trade_lane?: string | null;
  canonical_instrument_id?: string | null;
  market_family?: string | null;
  strategy_name?: string | null;
  playbook_id?: string | null;
  playbook_family?: string | null;
  playbook_decision_mode?: string | null;
  regime_state?: string | null;
  regime_substate?: string | null;
  regime_transition_state?: string | null;
  stop_distance_pct?: number | null;
  stop_budget_max_pct_allowed?: number | null;
  stop_min_executable_pct?: number | null;
  stop_fragility_0_1?: number | null;
  stop_executability_0_1?: number | null;
  stop_quality_0_1?: number | null;
  stop_to_spread_ratio?: number | null;
  stop_budget_policy_version?: string | null;
  instrument_metadata_snapshot_id?: string | null;
  instrument_venue?: string | null;
  instrument_category_key?: string | null;
  instrument_metadata_source?: string | null;
  instrument_metadata_verified?: boolean | null;
  instrument_product_type?: string | null;
  instrument_margin_account_mode?: string | null;
  instrument_base_coin?: string | null;
  instrument_quote_coin?: string | null;
  instrument_settle_coin?: string | null;
  instrument_inventory_visible?: boolean | null;
  instrument_analytics_eligible?: boolean | null;
  instrument_paper_shadow_eligible?: boolean | null;
  instrument_live_execution_enabled?: boolean | null;
  instrument_execution_disabled?: boolean | null;
  instrument_supports_funding?: boolean | null;
  instrument_supports_open_interest?: boolean | null;
  instrument_supports_long_short?: boolean | null;
  instrument_supports_shorting?: boolean | null;
  instrument_supports_reduce_only?: boolean | null;
  instrument_supports_leverage?: boolean | null;
  exit_family_effective_primary?: string | null;
  exit_family_primary_ensemble?: string | null;
  specialist_router_id?: string | null;
  router_selected_playbook_id?: string | null;
  router_operator_gate_required?: boolean | null;
  live_execution_block_reasons_json?: unknown[];
  governor_universal_hard_block_reasons_json?: unknown[];
  live_execution_clear_for_real_money?: boolean;
  latest_execution_id?: string | null;
  latest_execution_decision_action?: string | null;
  latest_execution_decision_reason?: string | null;
  latest_execution_runtime_mode?: string | null;
  latest_execution_requested_mode?: string | null;
  latest_execution_created_ts?: string | null;
  operator_release_exists?: boolean;
  operator_release_source?: string | null;
  operator_release_ts?: string | null;
  live_mirror_eligible?: boolean | null;
  shadow_live_match_ok?: boolean | null;
  shadow_live_hard_violations?: unknown;
  shadow_live_soft_violations?: unknown;
  telegram_alert_type?: string | null;
  telegram_delivery_state?: string | null;
  telegram_message_id?: number | string | null;
  telegram_sent_ts?: string | null;
  decision_confidence_0_1?: number | null;
  decision_policy_version?: string | null;
  allowed_leverage?: number | null;
  recommended_leverage?: number | null;
  leverage_policy_version?: string | null;
  leverage_cap_reasons_json?: unknown[];
  signal_class: string;
  decision_state: string;
  analysis_ts_ms: number;
  created_ts: string | null;
  outcome_badge: SignalOutcomeBadge | null;
  signal_contract_version?: string;
  signal_view?: SignalViewList;
};

export type SignalsFacetsResponse = GatewayReadEnvelope & {
  lookback_rows: number;
  market_families: string[];
  playbook_families: string[];
  meta_trade_lanes: string[];
  regime_states: string[];
  specialist_routers: string[];
  exit_families: string[];
  symbols: string[];
  /** Distinct timeframes im Facet-Lookback (DB-Kanon, z. B. 1H) — gleiche Semantik wie Query `timeframe` nach Gateway-Normalisierung. */
  timeframes: string[];
  directions: string[];
  decision_states: string[];
  trade_actions: string[];
  strategy_names: string[];
  playbook_ids: string[];
  signal_classes: string[];
};

export type SignalsRecentResponse = GatewayReadEnvelope & {
  items: SignalRecentItem[];
  limit: number;
  /** Gateway: mindestens ein Listenfilter gesetzt (inkl. min_strength). */
  filters_active?: boolean;
};

export type SignalDetail = {
  signal_id: string;
  symbol: string;
  timeframe: string;
  direction: string;
  canonical_instrument_id?: string | null;
  market_family?: string | null;
  strategy_name?: string | null;
  playbook_id?: string | null;
  playbook_family?: string | null;
  playbook_decision_mode?: string | null;
  regime_state?: string | null;
  regime_substate?: string | null;
  regime_transition_state?: string | null;
  stop_distance_pct?: number | null;
  stop_budget_max_pct_allowed?: number | null;
  stop_min_executable_pct?: number | null;
  stop_fragility_0_1?: number | null;
  stop_executability_0_1?: number | null;
  stop_quality_0_1?: number | null;
  stop_to_spread_ratio?: number | null;
  stop_budget_policy_version?: string | null;
  instrument_metadata_snapshot_id?: string | null;
  instrument_venue?: string | null;
  instrument_category_key?: string | null;
  instrument_metadata_source?: string | null;
  instrument_metadata_verified?: boolean | null;
  instrument_product_type?: string | null;
  instrument_margin_account_mode?: string | null;
  instrument_base_coin?: string | null;
  instrument_quote_coin?: string | null;
  instrument_settle_coin?: string | null;
  instrument_inventory_visible?: boolean | null;
  instrument_analytics_eligible?: boolean | null;
  instrument_paper_shadow_eligible?: boolean | null;
  instrument_live_execution_enabled?: boolean | null;
  instrument_execution_disabled?: boolean | null;
  instrument_supports_funding?: boolean | null;
  instrument_supports_open_interest?: boolean | null;
  instrument_supports_long_short?: boolean | null;
  instrument_supports_shorting?: boolean | null;
  instrument_supports_reduce_only?: boolean | null;
  instrument_supports_leverage?: boolean | null;
  instrument_metadata?: Record<string, unknown> | null;
  exit_family_effective_primary?: string | null;
  exit_family_primary_ensemble?: string | null;
  specialist_router_id?: string | null;
  router_selected_playbook_id?: string | null;
  router_operator_gate_required?: boolean | null;
  market_regime?: string | null;
  regime_bias?: string | null;
  regime_confidence_0_1?: number | null;
  regime_reasons_json: unknown[];
  signal_strength_0_100: number;
  probability_0_1: number;
  take_trade_prob?: number | null;
  take_trade_model_version?: string | null;
  take_trade_model_run_id?: string | null;
  take_trade_calibration_method?: string | null;
  expected_return_bps?: number | null;
  expected_mae_bps?: number | null;
  expected_mfe_bps?: number | null;
  target_projection_models_json?: unknown[];
  model_uncertainty_0_1?: number | null;
  uncertainty_effective_for_leverage_0_1?: number | null;
  shadow_divergence_0_1?: number | null;
  model_ood_score_0_1?: number | null;
  model_ood_alert?: boolean;
  uncertainty_reasons_json?: unknown[];
  ood_reasons_json?: unknown[];
  abstention_reasons_json?: unknown[];
  trade_action?: string | null;
  meta_decision_action?: string | null;
  meta_decision_kernel_version?: string | null;
  meta_trade_lane?: string | null;
  decision_confidence_0_1?: number | null;
  decision_policy_version?: string | null;
  allowed_leverage?: number | null;
  recommended_leverage?: number | null;
  leverage_policy_version?: string | null;
  leverage_cap_reasons_json?: unknown[];
  signal_class: string;
  decision_state: string;
  rejection_state?: boolean;
  rejection_reasons_json: unknown[];
  analysis_ts_ms: number;
  reasons_json: unknown[];
  created_ts: string | null;
  outcome_badge: SignalOutcomeBadge | null;
  /** Risk-Governor v2: blockiert nur Live-Broker, nicht zwingend Hybrid/Paper */
  live_execution_block_reasons_json?: unknown[];
  governor_universal_hard_block_reasons_json?: unknown[];
  portfolio_risk_synthesis_json?: Record<string, unknown> | null;
  live_execution_clear_for_real_money?: boolean;
  latest_execution_id?: string | null;
  latest_execution_decision_action?: string | null;
  latest_execution_decision_reason?: string | null;
  latest_execution_runtime_mode?: string | null;
  latest_execution_requested_mode?: string | null;
  latest_execution_created_ts?: string | null;
  operator_release_exists?: boolean;
  operator_release_source?: string | null;
  operator_release_ts?: string | null;
  live_mirror_eligible?: boolean | null;
  shadow_live_match_ok?: boolean | null;
  shadow_live_hard_violations?: unknown;
  shadow_live_soft_violations?: unknown;
  telegram_alert_type?: string | null;
  telegram_delivery_state?: string | null;
  telegram_message_id?: number | string | null;
  telegram_sent_ts?: string | null;
  signal_contract_version?: string;
  signal_view?: SignalViewDetail;
};

export type SignalExplainResponse = GatewayReadEnvelope & {
  signal_id: string;
  signal_contract_version?: string;
  explain_short: string | null;
  explain_long_md: string | null;
  risk_warnings_json: unknown[];
  stop_explain_json: Record<string, unknown>;
  targets_explain_json: Record<string, unknown>;
  reasons_json: unknown[];
  explanation_layers?: SignalExplainLayers | null;
};

export type PaperOpenPosition = {
  position_id: string;
  symbol: string;
  side: string;
  qty_base: string;
  entry_price_avg: string;
  mark_price: number | null;
  unrealized_pnl_usdt: number;
  leverage: string;
  leverage_allocator?: Record<string, unknown> | null;
  opened_ts_ms: number;
  meta: Record<string, unknown>;
};

export type PaperOpenResponse = GatewayReadEnvelope & {
  positions: PaperOpenPosition[];
};

export type PaperTradeRow = {
  position_id: string;
  symbol: string;
  side: string;
  qty_base: string;
  entry_price_avg: string;
  closed_ts_ms: number | null;
  state: string;
  pnl_net_usdt: number | null;
  fees_total_usdt: number | null;
  funding_total_usdt: number | null;
  direction_correct: boolean | null;
  reason_closed: string | null;
  leverage_allocator?: Record<string, unknown> | null;
  meta: Record<string, unknown>;
};

export type PaperTradesResponse = GatewayReadEnvelope & {
  trades: PaperTradeRow[];
  limit: number;
};

export type PaperLedgerEntry = {
  entry_id: string;
  ts_ms: number;
  amount_usdt: string;
  balance_after: string;
  reason: string;
  note: string | null;
  meta: Record<string, unknown>;
};

export type PaperEquityPoint = { time_s: number; equity: number };

/** GET /v1/paper/metrics/summary — Konto-Summaries aus paper.accounts + Aggregates; Kurve aus learn.trade_evaluations. */
export type PaperMetricsResponse = GatewayReadEnvelope & {
  account: {
    account_id: string;
    initial_equity: number;
    equity: number;
    currency: string | null;
  } | null;
  fees_total_usdt: number;
  funding_total_usdt: number;
  /** Kumulativ ab initial_equity über geschlossene Evaluations; leer ohne Paper-Konto. */
  equity_curve: PaperEquityPoint[];
  /** Spiegel der letzten Konten-Ledger-Zeilen (wie GET /v1/paper/ledger/recent, gekürzt). */
  account_ledger_recent?: PaperLedgerEntry[];
};

export type PaperLedgerResponse = GatewayReadEnvelope & {
  entries: PaperLedgerEntry[];
  limit: number;
  account_id?: string;
};

export type PaperJournalEvent = {
  source: string;
  ref_id: string;
  ts_ms: number;
  symbol: string | null;
  detail: Record<string, unknown>;
};

export type PaperJournalResponse = GatewayReadEnvelope & {
  events: PaperJournalEvent[];
  limit: number;
  account_id?: string;
};

export type NewsScoredItem = {
  news_id: string;
  source: string | null;
  title: string | null;
  url: string | null;
  score_0_100: number;
  sentiment: string | null;
  impact_window: string | null;
  published_ts_ms: number | null;
  summary: string;
};

export type NewsScoredResponse = GatewayReadEnvelope & {
  items: NewsScoredItem[];
  limit: number;
};

export type NewsDetail = {
  news_id: string;
  source: string | null;
  title: string | null;
  url: string | null;
  score_0_100: number;
  sentiment: string | null;
  impact_window: string | null;
  published_ts_ms: number | null;
  description: string | null;
  content: string | null;
  llm_summary_json: Record<string, unknown>;
};

/** learn.strategies + Lifecycle; status not_set = keine Zeile in learn.strategy_status. */
export type StrategyRegistryItem = {
  strategy_id: string;
  name: string;
  description: string | null;
  /** Lifecycle: promoted | candidate | shadow | retired | not_set */
  status: string;
  latest_version: string | null;
  scope_json?: StrategyScopeSnapshot | null;
  rolling_pf: unknown;
  rolling_win_rate: unknown;
  rolling_metrics_json: Record<string, unknown>;
  /** Fenster der ausgelieferten Rolling-Metrik (aktuell 30d). */
  rolling_time_window?: string | null;
  created_ts: string | null;
  registry_row_kind?: "registry";
  signal_path_signal_count?: number;
  signal_path_last_signal_ts_ms?: number | null;
  /** True wenn kein JOIN-Zeile learn.strategy_scores_rolling (30d) — PF/Win in der Liste dann meist leer. */
  rolling_snapshot_empty?: boolean;
};

/**
 * Schluessel aus app.signals_v1 ohne learn.strategies-Zeile.
 * Zaehlung/Link: `signal_registry_key` auf der Signalseite (playbook_id ODER strategy_name).
 */
export type SignalPathPlaybookUnlinkedItem = {
  playbook_key: string;
  playbook_family: string | null;
  signal_count: number;
  last_signal_ts_ms: number | null;
  registry_row_kind: "signal_path_only";
};

export type StrategiesListResponse = GatewayReadEnvelope & {
  items: StrategyRegistryItem[];
  signal_path_playbooks?: SignalPathPlaybookUnlinkedItem[];
};

export type StrategyDetailResponse = {
  strategy_id: string;
  name: string;
  description: string | null;
  scope_json: StrategyScopeSnapshot;
  created_ts: string | null;
  updated_ts: string | null;
  current_status: string | null;
  /** Kanonisch fuer UI: not_set wenn kein strategy_status (Gateway ab Registry-Erweiterung). */
  lifecycle_status?: string;
  /** True wenn learn.strategy_scores_rolling keine Zeilen fuer diese strategy_id liefert. */
  performance_rolling_empty?: boolean;
  performance_rolling_empty_hint_de?: string | null;
  status_updated_ts: string | null;
  versions: Array<{
    strategy_version_id: string;
    version: string;
    created_ts: string | null;
  }>;
  status_history: Array<{
    old_status: string | null;
    new_status: string;
    reason: string | null;
    changed_by: string | null;
    ts: string | null;
  }>;
  performance_rolling?: Array<{
    time_window: string | null;
    metrics_json: Record<string, unknown>;
    updated_ts: string | null;
  }>;
  signal_path?: {
    registry_key?: string;
    matching_signal_count: number;
    last_signal_ts_ms: number | null;
    match_rule_de: string;
    signals_list_query_param?: string;
    signals_link_hint_de?: string;
  };
  ai_explanations?: {
    availability: string;
    hint_de: string;
  };
};

export type LearningMetricsItem = {
  strategy_id: string;
  strategy_name: string;
  window: string;
  metrics_json: Record<string, unknown>;
  updated_ts: string | null;
};

export type ModelRegistryV2SlotItem = {
  model_name: string;
  role: string;
  run_id: string;
  calibration_status: string;
  activated_ts: string | null;
  notes: string | null;
  updated_ts: string | null;
  version: string | null;
  promoted_bool: boolean;
  calibration_method: string | null;
  /** global | market_family | market_regime | playbook | router_slot (Migration 550) */
  scope_type?: string;
  scope_key?: string;
};

export type ErrorPatternItem = {
  pattern_key: string;
  window: string;
  count: number;
  examples_json: unknown[];
  updated_ts: string | null;
};

export type RecommendationItem = {
  rec_id: string;
  type: string;
  payload_json: Record<string, unknown>;
  status: string;
  created_ts: string | null;
};

export type DriftItem = {
  drift_id: string;
  metric_name: string;
  severity: string;
  details_json: Record<string, unknown>;
  detected_ts: string | null;
};

/** Materialisierter Online-Drift (learn.online_drift_state), Prompt 26 */
export type OnlineDriftStateItem = {
  scope: string;
  effective_action: string;
  computed_at: string | null;
  lookback_minutes: number | null;
  breakdown_json: Record<string, unknown>;
};

/** GET /v1/learning/drift/online-state — Envelope + `gateway_online_drift_state_response` */
export type LearningDriftOnlineStateResponse = GatewayReadEnvelope & {
  item: OnlineDriftStateItem | null;
  /** Historisch; bei leerem State meist null — Nutzertext in `message` */
  detail?: string | null;
  seeded?: boolean;
  seed_metadata?: Record<string, unknown>;
};

export type LearningStrategyMetricsListResponse = GatewayReadEnvelope & {
  items: LearningMetricsItem[];
  limit: number;
};

export type LearningPatternsTopResponse = GatewayReadEnvelope & {
  items: ErrorPatternItem[];
  limit: number;
};

export type LearningRecommendationsListResponse = GatewayReadEnvelope & {
  items: RecommendationItem[];
  limit: number;
};

export type LearningDriftRecentResponse = GatewayReadEnvelope & {
  items: DriftItem[];
  limit: number;
  seeded?: boolean;
  seed_metadata?: Record<string, unknown>;
};

export type LearningModelRegistryV2ListResponse = GatewayReadEnvelope & {
  items: ModelRegistryV2SlotItem[];
  limit: number;
};

export type BacktestsRunsListResponse = GatewayReadEnvelope & {
  items: BacktestRunItem[];
  limit: number;
};

export type BacktestRunItem = {
  run_id: string;
  symbol: string | null;
  mode: string | null;
  status: string | null;
  cv_method: string | null;
  metrics_json: Record<string, unknown>;
  created_ts: string | null;
};

export type SystemHealthServiceItem = {
  name: string;
  status: string;
  configured: boolean;
  url?: string;
  note?: string;
  ready?: boolean;
  latency_ms?: number;
  http_status?: number;
  service_status?: string;
  failed_checks?: string[];
  execution_mode?: string;
  strategy_execution_mode?: string;
  paper_path_active?: boolean;
  shadow_trade_enable?: boolean;
  shadow_path_active?: boolean;
  live_trade_enable?: boolean;
  live_order_submission_enabled?: boolean;
  open_alert_count?: number;
  outbox_pending?: number;
  outbox_failed?: number;
  oldest_pending_age_ms?: number | null;
  last_run_ts_ms?: number | null;
  last_run_duration_ms?: number | null;
  last_error?: string | null;
  /** Gateway-Health-Probe: Verbindungs-/Parse-Fehler (ohne Secrets). */
  detail?: string;
  live_broker_monitored?: boolean;
  system_alert_stream_monitored?: boolean;
  /** market-stream /health: öffentlicher Bitget-WS (Telemetrie). */
  bitget_ws_stream?: Record<string, unknown>;
  /** live-broker /health: privater Bitget-WS (Telemetrie). */
  private_ws?: Record<string, unknown>;
};

export type SystemHealthOpsSummary = {
  monitor: {
    open_alert_count: number;
  };
  alert_engine: {
    outbox_pending: number;
    outbox_failed: number;
    outbox_sending: number;
  };
  live_broker: {
    latest_reconcile_status: string | null;
    latest_reconcile_created_ts: string | null;
    latest_reconcile_age_ms: number | null;
    latest_reconcile_drift_total: number;
    active_kill_switch_count: number;
    safety_latch_active?: boolean;
    last_fill_created_ts: string | null;
    last_fill_age_ms: number | null;
    critical_audit_count_24h: number;
    order_status_counts: Record<string, number>;
  };
};

/** Abgestimmt mit `config/execution_tier.py` / `execution_runtime.execution_tier`. */
export type ExecutionTierSnapshot = {
  schema_version: number;
  deployment: string;
  app_env: string;
  production: boolean;
  trading_plane: string;
  execution_mode: string;
  bitget_demo_enabled: boolean;
  live_broker_enabled: boolean;
  live_order_submission_enabled: boolean;
  automated_live_orders_enabled: boolean;
  strategy_execution_mode: string;
  implicit_mode_switch_risk?: string;
};

/** Abgestimmt mit `config/execution_runtime.py` / Gateway `execution.execution_runtime`. */
export type ExecutionRuntimeSnapshot = {
  schema_version: number;
  primary_mode: string;
  strategy_execution_mode: string;
  flags: Record<string, boolean>;
  paths: Record<string, boolean>;
  capabilities: Record<string, boolean>;
  live_release: Record<string, boolean>;
  execution_tier?: ExecutionTierSnapshot;
};

/** Strukturierter englischer Block fuer KI/Automation (Gateway + Dashboard-Fallback). */
export type HealthWarningMachine = {
  schema_version: string;
  problem_id: string;
  severity: string;
  summary_en: string;
  facts: Record<string, unknown>;
  suggested_actions: Array<Record<string, unknown>>;
  verify_commands: string[];
};

/** Menschenlesbare Health-Warnung (Gateway-Feld `warnings_display`); Codes nur in `code` fuer Keys. */
export type HealthWarningDisplayItem = {
  code: string;
  title: string;
  message: string;
  next_step: string;
  related_services: string;
  machine?: HealthWarningMachine;
};

export type IntegrationsMatrixCredentialPolicy = {
  vault_mode: string;
  reference_only: boolean;
  note_de: string;
  note_en: string;
};

export type IntegrationsMatrixRow = {
  integration_key: string;
  display_name_de: string;
  display_name_en: string;
  feature_flags: Record<string, unknown>;
  health_probes: Record<string, unknown>;
  health_status: string;
  health_error_public?: string | null;
  credential_refs?: string[];
  live_access?: Record<string, unknown>;
  ops_hint?: Record<string, unknown>;
  last_success_ts?: string | null;
  last_failure_ts?: string | null;
  last_error_persisted?: string | null;
  last_probe_ts?: string | null;
  state_updated_ts?: string | null;
};

export type IntegrationsMatrixBlock = {
  schema_version: string;
  server_ts_ms: number;
  credential_policy: IntegrationsMatrixCredentialPolicy;
  integrations: IntegrationsMatrixRow[];
};

/** Postgres-Kernschema + Migrationsabgleich (Gateway GET /v1/system/health). */
export type DatabaseSchemaHealthDetail = {
  status?: string;
  connect_error?: string;
  missing_tables?: string[];
  pending_migrations?: string[];
  pending_migrations_preview?: string[];
  migration_catalog_available?: boolean;
  expected_migration_files?: number;
  applied_migration_files?: number;
  schema_core_ok?: boolean;
  migrations_fully_applied?: boolean;
  tables?: Record<string, { exists: boolean; row_count: number | null }>;
};

/** Abgestimmt mit Gateway `system_health_truth_layer` / `GET /v1/system/health`. */
export type SystemHealthAggregate = {
  level: "green" | "degraded" | "red";
  summary_de: string;
  primary_reason_codes: string[];
};

export type SystemHealthTruthLayerMeta = {
  schema_version: number;
  readiness: {
    path: string;
    role: string;
    contract_version: number;
    semantics_de: string;
  };
  system_health: {
    path: string;
    role: string;
    contract_version: number;
    auth_de: string;
    semantics_de: string;
  };
};

export type SystemHealthReadinessCoreBlock = {
  ok: boolean;
  database: string;
  redis: string;
  checks: Record<string, { ok: boolean; detail: string }>;
  contract_version: number;
  note: string | null;
};

export type SystemHealthResponse = {
  server_ts_ms: number;
  symbol: string;
  /** Wahrheitsschicht: Verhaeltnis /ready zu diesem Endpunkt. */
  truth_layer?: SystemHealthTruthLayerMeta;
  /** Kompakter Ampel-Zustand fuer UI/Monitoring. */
  aggregate?: SystemHealthAggregate;
  /** Kern-Readiness wie GET /ready ohne Peer-URLs. */
  readiness_core?: SystemHealthReadinessCoreBlock;
  execution: {
    execution_mode: string;
    strategy_execution_mode: string;
    paper_path_active: boolean;
    shadow_trade_enable: boolean;
    shadow_path_active: boolean;
    live_trade_enable: boolean;
    live_order_submission_enabled: boolean;
    execution_runtime?: ExecutionRuntimeSnapshot;
  };
  market_universe?: MarketUniverseConfigSnapshot;
  database: string;
  /** Technischer Schema-/Migrationsstatus; bei `database !== ok` zuerst hier pruefen. */
  database_schema?: DatabaseSchemaHealthDetail | null;
  data_freshness: {
    last_candle_ts_ms: number | null;
    last_signal_ts_ms: number | null;
    last_news_ts_ms: number | null;
  };
  redis: string | undefined;
  stream_lengths_top: Array<{
    name: string;
    length: number | null;
    error?: string;
  }>;
  /** Redis-Ping, Stream-Laengen, events:*-Stichprobe (Diagnose). */
  redis_streams_detail?: Record<string, unknown>;
  services: SystemHealthServiceItem[];
  ops: SystemHealthOpsSummary;
  /** Kurzdiagnose externer Provider / Konnektivitaet (Gateway). */
  provider_ops_summary?: Record<string, unknown>;
  warnings: string[];
  /** Strukturierte Anzeigetexte zu `warnings` (ab Gateway mit `health_warnings_display`). */
  warnings_display?: HealthWarningDisplayItem[];
  /** Selten: camelCase vom Proxy — Dashboard mappt auf warnings_display. */
  warningsDisplay?: HealthWarningDisplayItem[];
  /** PROMPT 21: externe Integrationen, Feature-Flags, Health, Fehler-/Erfolgs-Zeitstempel. */
  integrations_matrix?: IntegrationsMatrixBlock | null;
};

export type AdminRulesResponse = {
  rule_sets: Array<{
    rule_set_id: string;
    rules_json: Record<string, unknown>;
    updated_ts: string | null;
  }>;
  env: Record<string, string | undefined>;
};

/** GET /v1/admin/console-overview */
export type AdminConsoleOverviewResponse = {
  schema_version: string;
  commercial_enabled: boolean;
  profit_fee_module_enabled: boolean;
  lifecycle: {
    status_counts: Array<{ lifecycle_status: string; count: number }>;
    recent: Array<{
      tenant_id_masked: string;
      tenant_id: string;
      lifecycle_status: string;
      email_verified: boolean;
      trial_started_at: string | null;
      trial_ends_at: string | null;
      updated_ts: string | null;
    }>;
  } | null;
  subscriptions: {
    subscription_rows: number;
    dunning_attention: number;
  } | null;
  contracts_review_open: number | null;
  profit_fee_by_status: Array<{ status: string; count: number }> | null;
  integrations_telegram: Array<{
    telegram_state: string;
    count: number;
  }> | null;
  integrations_broker: Array<{ broker_state: string; count: number }> | null;
};

/** GET /v1/commerce/customer/performance (Prompt 20) */
export type CommerceCustomerPerformanceResponse = {
  schema_version: string;
  tenant_id_masked: string;
  generated_at_ms: number;
  explainability: { de: string; en: string };
  demo: Record<string, unknown>;
  live_and_fees: Record<string, unknown>;
};

/** GET /v1/admin/performance-overview (Prompt 20) */
export type AdminPerformanceOverviewResponse = {
  schema_version: string;
  as_of_ms: number;
  paper: {
    open_positions: number;
    closed_trades_total: number;
    closed_trades_last_30d: number;
    sum_realized_pnl_net_usdt_30d: number;
  };
  live: {
    fills_last_30d: number;
    orders_non_terminal_count: number;
    note_de?: string;
  };
};

/** GET /v1/admin/telegram-customer-delivery (Prompt 19) */
export type AdminTelegramCustomerDeliveryResponse = {
  schema_version: string;
  bindings_count: number | null;
  customer_notify_recent: Array<{
    alert_id: string;
    created_ts: string | null;
    severity: string;
    state: string;
    attempt_count: number;
    last_error: string | null;
    dedupe_key: string | null;
    customer_category: string;
    tenant_id_masked: string;
  }> | null;
  customer_notify_failed_recent: Array<{
    alert_id: string;
    created_ts: string | null;
    state: string;
    attempt_count: number;
    last_error: string | null;
    customer_category: string;
    tenant_id_masked: string;
  }> | null;
  command_audit_recent: Array<{
    id: string;
    ts: string | null;
    chat_id_masked: string | null;
    user_id: number | null;
    command: string;
    args: unknown;
  }> | null;
};

export type LlmGovernanceTaskRow = {
  task_id: string;
  prompt_version: string;
  status: string;
  guardrail_tier: string;
  schema_filename: string | null;
};

export type LlmGovernanceEvalCaseRow = {
  id: string;
  description_de: string;
  category: string;
  task_types: string[];
};

export type LlmGovernanceSummary = {
  ok: boolean;
  prompt_manifest_version: string;
  guardrails_version: string;
  eval_baseline_sha256_prefix?: string;
  /** Versioniertes globales System-Prompt-Layer (shared/prompts/system/). */
  system_prompt?: {
    global_version: string;
    global_instruction_chars: number;
  };
  /** Eval-Baseline: Case-Katalog; release_gate=true → CI-Regression erforderlich. */
  eval_regression?: {
    baseline_id: string;
    release_gate: boolean;
    case_count: number;
    cases: LlmGovernanceEvalCaseRow[];
  };
  model_mapping: {
    openai_model_primary: string;
    openai_model_high_reasoning?: string;
    openai_model_fast?: string;
    llm_use_fake_provider: boolean;
    llm_openai_use_responses_api?: boolean;
    llm_openai_allow_chat_fallback?: boolean;
  };
  orchestrator_health: {
    status?: string;
    fake_mode?: boolean;
    openai_configured?: boolean;
  };
  tasks: LlmGovernanceTaskRow[];
  eval_hint_de?: string;
};

export type AdminLlmGovernanceResponse = {
  source: string;
  summary: LlmGovernanceSummary;
  eval_scores_placeholder: {
    status: string;
    hint_de: string;
  };
};

/** Aus GET /v1/live-broker/runtime → item.operator_live_submission (Gateway db_live_broker_queries). */
export type LiveBrokerOperatorLiveSubmission = {
  lane:
    | "live_lane_ready"
    | "live_lane_disabled_config"
    | "live_lane_blocked_safety"
    | "live_lane_blocked_exchange"
    | "live_lane_blocked_upstream"
    | "live_lane_degraded_reconcile"
    | "live_lane_unknown";
  reasons_de: string[];
  safety_kill_switch_count: number;
  safety_latch_active: boolean;
};

export type LiveBrokerBitgetPrivateStatus = {
  ui_status: string;
  bitget_connection_label: string;
  credential_profile?: string | null;
  demo_mode?: boolean | null;
  public_api_ok?: boolean | null;
  private_api_configured?: boolean | null;
  private_auth_ok?: boolean | null;
  private_detail_de?: string | null;
  private_auth_detail_de?: string | null;
  private_auth_classification?: string | null;
  private_auth_exchange_code?: string | null;
  /** Demo-Pfad: paptrading-Header aktiv (kein Secret). */
  paptrading_header_active?: boolean | null;
  credential_isolation_relaxed?: boolean | null;
  /** Circuit/Offset — Admin/Ops, keine API-Keys. */
  bitget_private_rest?: Record<string, unknown> | null;
};

export type LiveBrokerRuntimeItem = {
  reconcile_snapshot_id: string;
  status: string;
  execution_mode: string;
  runtime_mode: string;
  strategy_execution_mode: string | null;
  upstream_ok: boolean;
  paper_path_active: boolean;
  shadow_trade_enable: boolean;
  shadow_enabled: boolean;
  shadow_path_active: boolean;
  live_trade_enable: boolean;
  live_submission_enabled: boolean;
  live_order_submission_enabled: boolean;
  require_shadow_match_before_live?: boolean;
  decision_counts: Record<string, number>;
  details: Record<string, unknown>;
  bitget_private_status?: LiveBrokerBitgetPrivateStatus;
  order_status_counts: Record<string, number>;
  active_kill_switches: Array<Record<string, unknown>>;
  safety_latch_active?: boolean;
  operator_live_submission: LiveBrokerOperatorLiveSubmission;
  instrument_catalog?: {
    snapshot_id: string;
    status: string;
    refreshed_families: string[];
    counts: Record<string, number>;
    capability_matrix?: MarketUniverseCategoryRow[];
    warnings: string[];
    errors: string[];
    fetch_completed_ts_ms?: number | null;
  } | null;
  current_instrument_metadata?: Record<string, unknown> | null;
  created_ts: string | null;
};

export type LiveBrokerRuntimeResponse = GatewayReadEnvelope & {
  item: LiveBrokerRuntimeItem | null;
};

export type LiveBrokerDecisionItem = {
  execution_id: string;
  source_service: string;
  source_signal_id: string | null;
  symbol: string;
  signal_market_family?: string | null;
  signal_playbook_id?: string | null;
  signal_meta_trade_lane?: string | null;
  signal_canonical_instrument_id?: string | null;
  live_mirror_eligible?: boolean | null;
  timeframe: string | null;
  direction: string;
  requested_runtime_mode: string;
  effective_runtime_mode: string;
  decision_action: string;
  decision_reason: string;
  order_type: string;
  leverage: number | null;
  signal_allowed_leverage: number | null;
  signal_recommended_leverage: number | null;
  signal_trade_action: string | null;
  signal_leverage_policy_version: string | null;
  signal_leverage_cap_reasons_json: unknown[];
  approved_7x: boolean;
  qty_base: string | null;
  entry_price: string | null;
  stop_loss: string | null;
  take_profit: string | null;
  operator_release_exists?: boolean;
  operator_release_source?: string | null;
  operator_release_ts?: string | null;
  risk_trade_action?: string | null;
  risk_decision_state?: string | null;
  risk_primary_reason?: string | null;
  risk_reasons_json?: unknown[];
  shadow_live_match_ok?: boolean | null;
  shadow_live_hard_violations?: unknown;
  shadow_live_soft_violations?: unknown;
  payload: Record<string, unknown>;
  trace: Record<string, unknown>;
  created_ts: string | null;
  updated_ts: string | null;
};

export type LiveBrokerDecisionsResponse = GatewayReadEnvelope & {
  items: LiveBrokerDecisionItem[];
  limit: number;
};

export type LiveBrokerOrderItem = {
  internal_order_id: string;
  parent_internal_order_id: string | null;
  source_service: string;
  symbol: string;
  product_type: string;
  margin_mode: string;
  margin_coin: string;
  side: string;
  trade_side: string | null;
  order_type: string;
  force: string | null;
  reduce_only: boolean;
  size: string;
  price: string | null;
  note: string | null;
  client_oid: string;
  exchange_order_id: string | null;
  status: string;
  last_action: string;
  last_http_status: number | null;
  last_exchange_code: string | null;
  last_exchange_msg: string | null;
  last_response: Record<string, unknown>;
  trace: Record<string, unknown>;
  created_ts: string | null;
  updated_ts: string | null;
};

export type LiveBrokerOrdersResponse = GatewayReadEnvelope & {
  items: LiveBrokerOrderItem[];
  limit: number;
};

export type LiveBrokerFillItem = {
  internal_order_id: string;
  exchange_order_id: string | null;
  exchange_trade_id: string;
  symbol: string;
  side: string;
  price: string | null;
  size: string | null;
  fee: string | null;
  fee_coin: string | null;
  is_maker: boolean | null;
  exchange_ts_ms: number | null;
  raw: Record<string, unknown>;
  created_ts: string | null;
};

export type LiveBrokerFillsResponse = GatewayReadEnvelope & {
  items: LiveBrokerFillItem[];
  limit: number;
};

export type LiveBrokerOrderActionItem = {
  order_action_id: string;
  internal_order_id: string;
  action: string;
  request_path: string;
  client_oid: string | null;
  exchange_order_id: string | null;
  http_status: number | null;
  exchange_code: string | null;
  exchange_msg: string | null;
  retry_count: number | null;
  request: Record<string, unknown>;
  response: Record<string, unknown>;
  created_ts: string | null;
};

export type LiveBrokerOrderActionsResponse = GatewayReadEnvelope & {
  items: LiveBrokerOrderActionItem[];
  limit: number;
};

export type LiveBrokerKillSwitchEvent = {
  kill_switch_event_id: string;
  scope: string;
  scope_key: string;
  event_type: string;
  is_active: boolean;
  source: string;
  reason: string;
  symbol: string | null;
  product_type: string | null;
  margin_coin: string | null;
  internal_order_id: string | null;
  details: Record<string, unknown>;
  created_ts: string | null;
};

export type LiveBrokerKillSwitchResponse = GatewayReadEnvelope & {
  items: LiveBrokerKillSwitchEvent[];
  limit: number;
};

export type LiveBrokerAuditTrail = {
  audit_trail_id: string;
  category: string;
  action: string;
  severity: string;
  scope: string;
  scope_key: string;
  source: string;
  internal_order_id: string | null;
  symbol: string | null;
  details: Record<string, unknown>;
  created_ts: string | null;
};

export type LiveBrokerAuditResponse = GatewayReadEnvelope & {
  items: LiveBrokerAuditTrail[];
  limit: number;
  category?: string | null;
};

export type LiveBrokerForensicTimelineEvent = {
  ts: string | null;
  kind: string;
  ref: string | null;
  summary: Record<string, unknown>;
};

/** Erfolg: volle Timeline; Degrade: `execution_id` + `error` + Envelope (uebrige Felder fehlen) */
export type LiveBrokerForensicTimelineResponse = GatewayReadEnvelope & {
  execution_id: string;
  error?: string;
} & Partial<{
    schema_version: number;
    decision: Record<string, unknown>;
    signal_context: Record<string, unknown> | null;
    operator_release: Record<string, unknown> | null;
    journal: Record<string, unknown>[];
    orders: Record<string, unknown>[];
    fills: Record<string, unknown>[];
    exit_plans: Record<string, unknown>[];
    order_actions: Record<string, unknown>[];
    audit_trails: Record<string, unknown>[];
    shadow_live_assessment: Record<string, unknown> | null;
    risk_snapshot: Record<string, unknown> | null;
    learning_e2e_record: Record<string, unknown> | null;
    paper_positions: Record<string, unknown>[];
    trade_reviews: Record<string, unknown>[];
    telegram_operator_actions: Record<string, unknown>[];
    telegram_alert_outbox: Record<string, unknown>[];
    gateway_audit_trails: Record<string, unknown>[];
    timeline_sorted: LiveBrokerForensicTimelineEvent[];
  }>;

export type MonitorAlertItem = {
  alert_key: string;
  severity: string;
  title: string;
  message: string;
  details: Record<string, unknown>;
  state: string;
  created_ts: string | null;
  updated_ts: string | null;
};

export type MonitorAlertsResponse = GatewayReadEnvelope & {
  items: MonitorAlertItem[];
  limit: number;
};

export type AlertOutboxItem = {
  alert_id: string;
  created_ts: string | null;
  alert_type: string;
  severity: string;
  symbol: string | null;
  timeframe: string | null;
  dedupe_key: string | null;
  chat_id: number | null;
  state: string;
  attempt_count: number | null;
  last_error: string | null;
  telegram_message_id: number | string | null;
  sent_ts: string | null;
  payload: Record<string, unknown>;
};

export type AlertOutboxResponse = GatewayReadEnvelope & {
  items: AlertOutboxItem[];
  limit: number;
};
