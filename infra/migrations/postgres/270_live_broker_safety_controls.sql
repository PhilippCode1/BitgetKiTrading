-- Prompt 11: Live broker kill switch, audit trail and emergency safety controls

CREATE TABLE IF NOT EXISTS live.kill_switch_events (
    kill_switch_event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope text NOT NULL CHECK (scope IN ('service', 'account', 'trade')),
    scope_key text NOT NULL,
    event_type text NOT NULL CHECK (
        event_type IN (
            'arm',
            'release',
            'auto_cancel',
            'flatten_requested',
            'flatten_completed',
            'flatten_failed'
        )
    ),
    is_active boolean NOT NULL,
    source text NOT NULL,
    reason text NOT NULL,
    symbol text NULL,
    product_type text NULL,
    margin_coin text NULL,
    internal_order_id uuid NULL,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_kill_switch_scope_created
    ON live.kill_switch_events (scope, scope_key, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_kill_switch_symbol_created
    ON live.kill_switch_events (symbol, created_ts DESC);

CREATE TABLE IF NOT EXISTS live.audit_trails (
    audit_trail_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    category text NOT NULL,
    action text NOT NULL,
    severity text NOT NULL CHECK (severity IN ('info', 'warn', 'critical')),
    scope text NOT NULL,
    scope_key text NOT NULL,
    source text NOT NULL,
    internal_order_id uuid NULL,
    symbol text NULL,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_audit_trails_created
    ON live.audit_trails (created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_live_audit_trails_scope_created
    ON live.audit_trails (scope, scope_key, created_ts DESC);
