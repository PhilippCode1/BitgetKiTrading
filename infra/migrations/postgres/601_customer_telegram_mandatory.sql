-- PROMPT 20: Kunden-Telegram verpflichtend — Pending-Link, Binding, Outbox-Typ

CREATE TABLE IF NOT EXISTS app.telegram_link_pending (
    pending_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    token_sha256 text NOT NULL,
    expires_ts timestamptz NOT NULL,
    consumed_ts timestamptz NULL,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_telegram_link_token UNIQUE (token_sha256)
);

CREATE INDEX IF NOT EXISTS idx_telegram_link_pending_tenant_created
    ON app.telegram_link_pending (tenant_id, created_ts DESC);

COMMENT ON TABLE app.telegram_link_pending IS
    'Einmal-Link fuer /start link_<token> im Bot; Token nur als SHA-256.';

CREATE TABLE IF NOT EXISTS app.customer_telegram_binding (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    telegram_chat_id bigint NOT NULL,
    telegram_username text NULL,
    verified_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_customer_telegram_chat UNIQUE (telegram_chat_id)
);

COMMENT ON TABLE app.customer_telegram_binding IS
    'Serverseitig: Chat-ID fuer Pflichtbenachrichtigungen; nicht an Browser liefern.';

CREATE INDEX IF NOT EXISTS idx_customer_telegram_binding_chat
    ON app.customer_telegram_binding (telegram_chat_id);

ALTER TABLE alert.alert_outbox DROP CONSTRAINT IF EXISTS alert_outbox_alert_type_check;

ALTER TABLE alert.alert_outbox
    ADD CONSTRAINT alert_outbox_alert_type_check CHECK (
        alert_type IN (
            'GROSS_SIGNAL',
            'CORE_SIGNAL',
            'TREND_WARN',
            'TRADE_CLOSED',
            'STOP_DANGER',
            'NEWS_HIGH',
            'SYSTEM_ALERT',
            'LIVE_EXECUTION_POLICY_WARN',
            'LIVE_BROKER_KILL_SWITCH',
            'LIVE_BROKER_EMERGENCY_FLATTEN',
            'LIVE_BROKER_ORDER_TIMEOUT',
            'LIVE_BROKER_RECONCILE',
            'LIVE_BROKER_MONITOR',
            'OPERATOR_STRATEGY_INTENT',
            'OPERATOR_NO_TRADE',
            'OPERATOR_PLAN_SUMMARY',
            'OPERATOR_RISK_NOTICE',
            'OPERATOR_FILL',
            'OPERATOR_EXIT',
            'OPERATOR_POST_TRADE',
            'OPERATOR_EXECUTION_UPDATE',
            'OPERATOR_PRE_TRADE',
            'OPERATOR_RELEASE_PENDING',
            'OPERATOR_TRADE_OPEN',
            'OPERATOR_TRADE_CLOSE',
            'OPERATOR_INCIDENT',
            'OPERATOR_SAFETY_LATCH',
            'CUSTOMER_NOTIFY'
        )
    );
