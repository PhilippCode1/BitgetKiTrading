-- Prompt 18: Regressionsmodelle fuer erwartete Return-/MAE-/MFE-Bps

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS expected_return_bps numeric,
    ADD COLUMN IF NOT EXISTS expected_mae_bps numeric,
    ADD COLUMN IF NOT EXISTS expected_mfe_bps numeric,
    ADD COLUMN IF NOT EXISTS target_projection_models_json jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_expected_return_bps
    ON app.signals_v1 (analysis_ts_ms DESC, expected_return_bps DESC)
    WHERE expected_return_bps IS NOT NULL;
