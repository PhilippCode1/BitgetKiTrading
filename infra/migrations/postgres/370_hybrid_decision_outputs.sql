-- Prompt 20: Hybrid-Entscheider-Outputs

ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS decision_confidence_0_1 numeric,
    ADD COLUMN IF NOT EXISTS decision_policy_version text,
    ADD COLUMN IF NOT EXISTS recommended_leverage integer;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_trade_action_confidence
    ON app.signals_v1 (analysis_ts_ms DESC, trade_action, decision_confidence_0_1 DESC);
