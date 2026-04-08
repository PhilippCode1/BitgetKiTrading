-- Prompt 27: Alert-Engine + Telegram (Outbox, Dedupe, Audit)

CREATE SCHEMA IF NOT EXISTS alert;

CREATE TABLE IF NOT EXISTS alert.bot_state (
    key text PRIMARY KEY,
    last_update_id bigint NOT NULL DEFAULT 0,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

INSERT INTO alert.bot_state (key, last_update_id) VALUES ('telegram', 0)
ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS alert.chat_subscriptions (
    chat_id bigint PRIMARY KEY,
    status text NOT NULL CHECK (status IN ('pending', 'allowed', 'blocked')),
    user_id bigint NULL,
    username text NULL,
    title text NULL,
    muted_until_ts_ms bigint NULL,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert.alert_outbox (
    alert_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_ts timestamptz NOT NULL DEFAULT now(),
    alert_type text NOT NULL CHECK (
        alert_type IN (
            'GROSS_SIGNAL',
            'CORE_SIGNAL',
            'TREND_WARN',
            'TRADE_CLOSED',
            'STOP_DANGER',
            'NEWS_HIGH',
            'SYSTEM_ALERT'
        )
    ),
    severity text NOT NULL CHECK (severity IN ('info', 'warn', 'critical')),
    symbol text NULL,
    timeframe text NULL,
    dedupe_key text NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    chat_id bigint NOT NULL,
    state text NOT NULL CHECK (state IN ('pending', 'sending', 'sent', 'failed', 'simulated')),
    attempt_count int NOT NULL DEFAULT 0,
    last_error text NULL,
    telegram_message_id bigint NULL,
    sent_ts timestamptz NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_outbox_state_created
    ON alert.alert_outbox (state, created_ts DESC);

CREATE INDEX IF NOT EXISTS idx_alert_outbox_dedupe_key
    ON alert.alert_outbox (dedupe_key);

CREATE TABLE IF NOT EXISTS alert.dedupe_keys (
    dedupe_key text PRIMARY KEY,
    expires_ts timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_dedupe_expires ON alert.dedupe_keys (expires_ts);

CREATE TABLE IF NOT EXISTS alert.command_audit (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id bigint NULL,
    user_id bigint NULL,
    command text NOT NULL,
    args jsonb NOT NULL DEFAULT '{}'::jsonb,
    ts timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert.structure_trend_state (
    symbol text NOT NULL,
    timeframe text NOT NULL,
    last_trend_dir text NOT NULL,
    updated_ts_ms bigint NOT NULL,
    PRIMARY KEY (symbol, timeframe)
);
