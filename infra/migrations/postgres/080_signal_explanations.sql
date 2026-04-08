-- Prompt 14: Explainability 1:1 zu app.signals_v1
CREATE TABLE IF NOT EXISTS app.signal_explanations (
    signal_id uuid PRIMARY KEY REFERENCES app.signals_v1 (signal_id) ON DELETE CASCADE,
    explain_version text NOT NULL,
    explain_short text NOT NULL,
    explain_long_md text NOT NULL,
    explain_long_json jsonb NOT NULL,
    risk_warnings_json jsonb NOT NULL,
    stop_explain_json jsonb NOT NULL,
    targets_explain_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_signal_explanations_updated_desc
    ON app.signal_explanations (updated_at DESC);
