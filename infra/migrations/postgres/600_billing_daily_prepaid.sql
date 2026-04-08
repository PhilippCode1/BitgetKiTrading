-- PROMPT 19: Taegliche API-Flatrate vom Prepaid-Guthaben; revisionssichere Alerts

CREATE TABLE IF NOT EXISTS app.billing_daily_accrual (
    accrual_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    accrual_date date NOT NULL,
    amount_charged_list_usd numeric(18, 8) NOT NULL,
    balance_before_list_usd numeric(18, 8) NOT NULL,
    balance_after_list_usd numeric(18, 8) NOT NULL,
    ledger_id uuid,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_billing_daily_tenant_date UNIQUE (tenant_id, accrual_date)
);

CREATE INDEX IF NOT EXISTS idx_billing_daily_tenant_created
    ON app.billing_daily_accrual (tenant_id, created_ts DESC);

COMMENT ON TABLE app.billing_daily_accrual IS
    'Idempotenter Tagesabzug (UTC-Datum); verknuepft mit usage_ledger.';

CREATE TABLE IF NOT EXISTS app.billing_balance_alert (
    alert_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    alert_level text NOT NULL CHECK (alert_level IN ('warning', 'critical', 'depleted')),
    balance_list_usd numeric(18, 8) NOT NULL,
    accrual_date date NOT NULL,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_billing_alert_tenant_level_date UNIQUE (tenant_id, alert_level, accrual_date)
);

CREATE INDEX IF NOT EXISTS idx_billing_alert_tenant_created
    ON app.billing_balance_alert (tenant_id, created_ts DESC);

COMMENT ON TABLE app.billing_balance_alert IS
    'Schwellen-Alerts (max. eine Zeile pro Stufe und UTC-Tag); zusaetzlich portal_audit.';
