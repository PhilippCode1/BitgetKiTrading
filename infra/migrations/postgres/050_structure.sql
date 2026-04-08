CREATE TABLE IF NOT EXISTS app.swings (
    swing_id uuid PRIMARY KEY,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    start_ts_ms bigint NOT NULL,
    kind text NOT NULL CHECK (kind IN ('high', 'low')),
    price numeric NOT NULL,
    left_n integer NOT NULL CHECK (left_n > 0),
    right_n integer NOT NULL CHECK (right_n > 0),
    confirmed_ts_ms bigint NOT NULL,
    UNIQUE (symbol, timeframe, start_ts_ms, kind)
);

CREATE INDEX IF NOT EXISTS idx_app_swings_symbol_timeframe_start_desc
    ON app.swings (symbol, timeframe, start_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_swings_symbol_timeframe_kind_start_desc
    ON app.swings (symbol, timeframe, kind, start_ts_ms DESC);

CREATE TABLE IF NOT EXISTS app.structure_state (
    symbol text NOT NULL,
    timeframe text NOT NULL,
    last_ts_ms bigint NOT NULL,
    trend_dir text NOT NULL CHECK (trend_dir IN ('UP', 'DOWN', 'RANGE')),
    last_swing_high_price numeric,
    last_swing_low_price numeric,
    compression_flag boolean NOT NULL DEFAULT false,
    breakout_box_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, timeframe)
);

CREATE INDEX IF NOT EXISTS idx_app_structure_state_symbol_timeframe_updated_desc
    ON app.structure_state (symbol, timeframe, updated_ts_ms DESC);

CREATE TABLE IF NOT EXISTS app.structure_events (
    event_id uuid PRIMARY KEY,
    symbol text NOT NULL,
    timeframe text NOT NULL,
    ts_ms bigint NOT NULL,
    type text NOT NULL CHECK (
        type IN (
            'BOS',
            'CHOCH',
            'BREAKOUT',
            'FALSE_BREAKOUT',
            'COMPRESSION_ON',
            'COMPRESSION_OFF'
        )
    ),
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_app_structure_events_symbol_timeframe_ts_desc
    ON app.structure_events (symbol, timeframe, ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_app_structure_events_type_ts_desc
    ON app.structure_events (type, ts_ms DESC);
