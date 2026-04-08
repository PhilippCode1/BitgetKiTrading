-- Prompt 13: Modellvertrag, Feature-Schema-Metadaten und Learning-Contract-Snapshot

ALTER TABLE features.candle_features
    ADD COLUMN IF NOT EXISTS feature_schema_version text;

ALTER TABLE features.candle_features
    ADD COLUMN IF NOT EXISTS feature_schema_hash text;

CREATE INDEX IF NOT EXISTS idx_features_candle_features_schema
    ON features.candle_features (
        symbol,
        timeframe,
        feature_schema_version,
        feature_schema_hash,
        start_ts_ms DESC
    );

ALTER TABLE learn.trade_evaluations
    ADD COLUMN IF NOT EXISTS model_contract_json jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_learn_trade_eval_model_contract_gin
    ON learn.trade_evaluations USING gin (model_contract_json);
