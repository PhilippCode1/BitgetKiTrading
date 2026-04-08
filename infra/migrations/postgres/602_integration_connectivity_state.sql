-- Nachvollziehbare Integrations-Health (PROMPT 21): rollierende Erfolgs-/Fehler-Zeitstempel, keine Secrets.

CREATE TABLE IF NOT EXISTS app.integration_connectivity_state (
    integration_key text PRIMARY KEY,
    last_status text NOT NULL DEFAULT 'unknown',
    last_error_public text,
    last_success_ts timestamptz,
    last_failure_ts timestamptz,
    probe_detail_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integration_connectivity_updated
    ON app.integration_connectivity_state (updated_ts DESC);
