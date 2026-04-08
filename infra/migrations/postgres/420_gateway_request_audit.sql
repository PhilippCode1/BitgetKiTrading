-- Prompt 29: Gateway HTTP-/Admin-Audit (keine Secrets in detail_json speichern)

CREATE TABLE IF NOT EXISTS app.gateway_request_audit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_ts timestamptz NOT NULL DEFAULT now(),
    actor text NOT NULL,
    auth_method text NOT NULL,
    action text NOT NULL,
    http_method text NOT NULL,
    path text NOT NULL,
    client_ip text,
    user_agent text,
    detail_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_gateway_request_audit_created_ts
    ON app.gateway_request_audit (created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_gateway_request_audit_action
    ON app.gateway_request_audit (action, created_ts DESC);
