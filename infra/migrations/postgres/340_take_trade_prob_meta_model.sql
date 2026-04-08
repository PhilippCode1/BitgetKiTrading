-- Prompt 17: Meta-Label-Modell take_trade_prob

ALTER TABLE app.model_runs
    ADD COLUMN IF NOT EXISTS artifact_path text,
    ADD COLUMN IF NOT EXISTS target_name text,
    ADD COLUMN IF NOT EXISTS output_field text,
    ADD COLUMN IF NOT EXISTS calibration_method text,
    ADD COLUMN IF NOT EXISTS metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_app_model_runs_name_promoted_created
    ON app.model_runs (model_name, promoted_bool DESC, created_ts DESC);

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS take_trade_prob numeric,
    ADD COLUMN IF NOT EXISTS take_trade_model_version text,
    ADD COLUMN IF NOT EXISTS take_trade_model_run_id uuid,
    ADD COLUMN IF NOT EXISTS take_trade_calibration_method text;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_take_trade_prob
    ON app.signals_v1 (analysis_ts_ms DESC, take_trade_prob DESC)
    WHERE take_trade_prob IS NOT NULL;
