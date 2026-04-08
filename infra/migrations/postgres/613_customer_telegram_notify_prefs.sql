-- Prompt 19: Benachrichtigungs-Präferenzen pro Mandant für Kunden-Telegram (CUSTOMER_NOTIFY).

CREATE TABLE IF NOT EXISTS app.customer_telegram_notify_prefs (
    tenant_id VARCHAR(128) PRIMARY KEY,
    notify_orders_demo BOOLEAN NOT NULL DEFAULT TRUE,
    notify_orders_live BOOLEAN NOT NULL DEFAULT TRUE,
    notify_billing BOOLEAN NOT NULL DEFAULT TRUE,
    notify_contract BOOLEAN NOT NULL DEFAULT TRUE,
    notify_risk BOOLEAN NOT NULL DEFAULT TRUE,
    notify_ai_tip BOOLEAN NOT NULL DEFAULT FALSE,
    updated_ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE app.customer_telegram_notify_prefs IS
    'Telegram-Benachrichtigungsarten pro Tenant; fehlende Zeile = Server-Defaults (alle außer KI-Tip an).';

CREATE INDEX IF NOT EXISTS idx_customer_telegram_notify_prefs_updated
    ON app.customer_telegram_notify_prefs (updated_ts DESC);
