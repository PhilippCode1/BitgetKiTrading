-- Prompt 16: Regime-Klassifikation fuer Signals V1

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS regime_bias text,
    ADD COLUMN IF NOT EXISTS regime_confidence_0_1 numeric,
    ADD COLUMN IF NOT EXISTS regime_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_regime
    ON app.signals_v1 (market_regime, analysis_ts_ms DESC);
