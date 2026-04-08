-- Prompt 19: Uncertainty, OOD und harte Abstention-Policy

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS model_uncertainty_0_1 numeric,
    ADD COLUMN IF NOT EXISTS shadow_divergence_0_1 numeric,
    ADD COLUMN IF NOT EXISTS model_ood_score_0_1 numeric,
    ADD COLUMN IF NOT EXISTS model_ood_alert boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS uncertainty_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS ood_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS abstention_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS trade_action text;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_trade_action_uncertainty
    ON app.signals_v1 (analysis_ts_ms DESC, trade_action, model_uncertainty_0_1 DESC);
