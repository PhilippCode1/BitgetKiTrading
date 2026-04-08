-- Telegram: zweistufige Operator-Freigaben, revisionssichere Audit-Spur (keine Strategie-Mutation via Chat).

CREATE TABLE IF NOT EXISTS alert.telegram_operator_pending (
    pending_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id bigint NOT NULL,
    user_id bigint NULL,
    action_kind text NOT NULL CHECK (action_kind IN ('operator_release', 'emergency_flatten')),
    execution_id uuid NULL,
    request_body_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    summary_redacted text NOT NULL DEFAULT '',
    confirm_code_hash text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NULL,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_telegram_operator_pending_open
    ON alert.telegram_operator_pending (chat_id, expires_at)
    WHERE consumed_at IS NULL;

CREATE TABLE IF NOT EXISTS alert.operator_action_audit (
    audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ts timestamptz NOT NULL DEFAULT now(),
    outcome text NOT NULL CHECK (outcome IN (
        'rejected_forbidden_command',
        'rejected_invalid_args',
        'rejected_not_enabled',
        'rejected_not_eligible',
        'rejected_expired',
        'rejected_bad_code',
        'rejected_wrong_chat',
        'rejected_http_error',
        'rejected_missing_upstream',
        'pending_created',
        'pending_cancelled',
        'executed_ok',
        'executed_error'
    )),
    action_kind text NULL,
    chat_id bigint NULL,
    user_id bigint NULL,
    execution_id uuid NULL,
    pending_id uuid NULL,
    http_status int NULL,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_operator_action_audit_ts
    ON alert.operator_action_audit (ts DESC);
