CREATE SCHEMA IF NOT EXISTS features;

CREATE TABLE IF NOT EXISTS features.candle_features (
    symbol text NOT NULL,
    timeframe text NOT NULL,
    start_ts_ms bigint NOT NULL,
    atr_14 double precision,
    atrp_14 double precision,
    rsi_14 double precision,
    ret_1 double precision,
    ret_5 double precision,
    momentum_score double precision,
    impulse_body_ratio double precision,
    impulse_upper_wick_ratio double precision,
    impulse_lower_wick_ratio double precision,
    range_score double precision,
    trend_ema_fast double precision,
    trend_ema_slow double precision,
    trend_slope_proxy double precision,
    trend_dir integer NOT NULL DEFAULT 0 CHECK (trend_dir IN (-1, 0, 1)),
    confluence_score_0_100 double precision,
    vol_z_50 double precision,
    source_event_id text NOT NULL,
    computed_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, timeframe, start_ts_ms)
);

CREATE INDEX IF NOT EXISTS idx_features_candle_features_symbol_timeframe_start_desc
    ON features.candle_features (symbol, timeframe, start_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_features_candle_features_symbol_timeframe_computed_desc
    ON features.candle_features (symbol, timeframe, computed_ts_ms DESC);
