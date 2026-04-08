-- Prompt 21: Integer-Leverage-Allocator Outputs
ALTER TABLE app.signals_v1
    ADD COLUMN IF NOT EXISTS allowed_leverage integer,
    ADD COLUMN IF NOT EXISTS leverage_policy_version text,
    ADD COLUMN IF NOT EXISTS leverage_cap_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_app_signals_v1_allowed_leverage
    ON app.signals_v1 (analysis_ts_ms DESC, trade_action, allowed_leverage DESC);
