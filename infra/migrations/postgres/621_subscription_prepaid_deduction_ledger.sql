-- Prompt 41: Tägliche Abo-Abzüge vom internen Prepaid (UTC), idempotente Ledger-Zeilen.

CREATE TABLE IF NOT EXISTS app.subscription_billing_ledger (
    entry_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    entry_type text NOT NULL,
    accrual_date_utc date NOT NULL,
    plan_code text NOT NULL,
    net_amount_cents_eur bigint NOT NULL,
    amount_list_usd numeric(18, 8) NOT NULL,
    vat_rate_bps integer,
    idempotency_key text NOT NULL,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_subscription_billing_ledger_entry_type CHECK (entry_type IN ('DEDUCTION')),
    CONSTRAINT uq_subscription_billing_ledger_tenant_date UNIQUE (tenant_id, accrual_date_utc)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_subscription_billing_ledger_idempotency
    ON app.subscription_billing_ledger (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_subscription_billing_ledger_tenant_ts
    ON app.subscription_billing_ledger (tenant_id, accrual_date_utc DESC);

COMMENT ON TABLE app.subscription_billing_ledger IS
    'Prompt 41: ein Eintrag pro Tenant/UTC-Tag, Typ DEDUCTION; idempotency_key = tenant:subscription:deduct:YYYY-MM-DD.';

-- Erweitert 609-Status: Abo wegen mangelndem Guthaben gesperrt
ALTER TABLE app.tenant_subscription DROP CONSTRAINT IF EXISTS chk_tenant_subscription_status;
ALTER TABLE app.tenant_subscription ADD CONSTRAINT chk_tenant_subscription_status CHECK (
    status IN (
        'trialing',
        'active',
        'past_due',
        'canceled',
        'expired',
        'suspended_insufficient_funds'
    )
);

-- Zusätzliche Katalog-Pläne: Basic, Pro, Institution (Monatspreis netto, Ref. 30 Tage)
INSERT INTO app.billing_subscription_plan (
    plan_code,
    billing_interval,
    display_name_de,
    net_amount_cents,
    currency,
    vat_rate_bps,
    reference_period_days,
    is_active
)
VALUES
    (
        'plan_basic',
        'month',
        'Basic',
        3000,
        'EUR',
        1900,
        30,
        true
    ),
    (
        'plan_pro',
        'month',
        'Pro',
        30000,
        'EUR',
        1900,
        30,
        true
    ),
    (
        'plan_institution',
        'month',
        'Institution',
        150000,
        'EUR',
        1900,
        30,
        true
    )
ON CONFLICT (plan_code) DO UPDATE SET
    display_name_de = EXCLUDED.display_name_de,
    net_amount_cents = EXCLUDED.net_amount_cents,
    vat_rate_bps = EXCLUDED.vat_rate_bps,
    reference_period_days = EXCLUDED.reference_period_days,
    is_active = EXCLUDED.is_active;
