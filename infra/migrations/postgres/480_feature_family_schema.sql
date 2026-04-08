ALTER TABLE features.candle_features
    ADD COLUMN IF NOT EXISTS canonical_instrument_id text,
    ADD COLUMN IF NOT EXISTS market_family text,
    ADD COLUMN IF NOT EXISTS product_type text,
    ADD COLUMN IF NOT EXISTS margin_account_mode text,
    ADD COLUMN IF NOT EXISTS instrument_metadata_snapshot_id text,
    ADD COLUMN IF NOT EXISTS funding_time_to_next_ms bigint,
    ADD COLUMN IF NOT EXISTS mark_index_spread_bps double precision,
    ADD COLUMN IF NOT EXISTS basis_bps double precision,
    ADD COLUMN IF NOT EXISTS session_drift_bps double precision,
    ADD COLUMN IF NOT EXISTS spread_persistence_bps double precision,
    ADD COLUMN IF NOT EXISTS mean_reversion_pressure_0_100 double precision,
    ADD COLUMN IF NOT EXISTS breakout_compression_score_0_100 double precision,
    ADD COLUMN IF NOT EXISTS realized_vol_cluster_0_100 double precision,
    ADD COLUMN IF NOT EXISTS liquidation_distance_bps_max_leverage double precision,
    ADD COLUMN IF NOT EXISTS data_completeness_0_1 double precision,
    ADD COLUMN IF NOT EXISTS staleness_score_0_1 double precision,
    ADD COLUMN IF NOT EXISTS gap_count_lookback integer,
    ADD COLUMN IF NOT EXISTS event_distance_ms bigint,
    ADD COLUMN IF NOT EXISTS feature_quality_status text;

UPDATE features.candle_features
SET canonical_instrument_id = COALESCE(NULLIF(canonical_instrument_id, ''), 'bitget:unknown:unknown:' || symbol),
    market_family = COALESCE(NULLIF(market_family, ''), 'unknown')
WHERE canonical_instrument_id IS NULL
   OR canonical_instrument_id = ''
   OR market_family IS NULL
   OR market_family = '';

ALTER TABLE features.candle_features
    ALTER COLUMN canonical_instrument_id SET NOT NULL,
    ALTER COLUMN market_family SET NOT NULL;

ALTER TABLE features.candle_features
    DROP CONSTRAINT IF EXISTS candle_features_pkey;

ALTER TABLE features.candle_features
    ADD CONSTRAINT candle_features_pkey
        PRIMARY KEY (canonical_instrument_id, timeframe, start_ts_ms);

CREATE INDEX IF NOT EXISTS idx_features_candle_features_canonical_instrument_timeframe_start_desc
    ON features.candle_features (canonical_instrument_id, timeframe, start_ts_ms DESC);

CREATE INDEX IF NOT EXISTS idx_features_candle_features_market_family_timeframe_start_desc
    ON features.candle_features (market_family, timeframe, start_ts_ms DESC);
