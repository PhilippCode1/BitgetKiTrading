-- Prompt 21: Learning / Trade Feedback Collector

CREATE SCHEMA IF NOT EXISTS learn;

CREATE TABLE IF NOT EXISTS learn.processed_events (
    stream text NOT NULL,
    message_id text NOT NULL,
    processed_ts timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (stream, message_id)
);

CREATE TABLE IF NOT EXISTS learn.trade_evaluations (
    evaluation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_trade_id uuid NOT NULL UNIQUE,
    signal_id uuid,
    symbol text NOT NULL,
    timeframe text NOT NULL DEFAULT '5m',
    opened_ts_ms bigint NOT NULL,
    closed_ts_ms bigint NOT NULL,
    side text NOT NULL CHECK (side IN ('long', 'short')),
    qty_base numeric NOT NULL,
    entry_price_avg numeric NOT NULL,
    exit_price_avg numeric,
    pnl_gross_usdt numeric NOT NULL,
    fees_total_usdt numeric NOT NULL,
    funding_total_usdt numeric NOT NULL,
    pnl_net_usdt numeric NOT NULL,
    direction_correct boolean NOT NULL,
    stop_hit boolean NOT NULL DEFAULT false,
    tp1_hit boolean NOT NULL DEFAULT false,
    tp2_hit boolean NOT NULL DEFAULT false,
    tp3_hit boolean NOT NULL DEFAULT false,
    time_to_tp1_ms bigint,
    time_to_stop_ms bigint,
    stop_quality_score integer,
    stop_distance_atr_mult numeric,
    slippage_bps_entry numeric,
    slippage_bps_exit numeric,
    market_regime text,
    news_context_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    signal_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    feature_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    structure_snapshot_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_labels_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learn_trade_eval_symbol_closed
    ON learn.trade_evaluations (symbol, closed_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_learn_trade_eval_created
    ON learn.trade_evaluations (created_ts DESC);

CREATE TABLE IF NOT EXISTS learn.signal_outcomes (
    signal_id uuid PRIMARY KEY,
    evaluations_count integer NOT NULL DEFAULT 0,
    wins integer NOT NULL DEFAULT 0,
    losses integer NOT NULL DEFAULT 0,
    updated_ts timestamptz NOT NULL DEFAULT now()
);
