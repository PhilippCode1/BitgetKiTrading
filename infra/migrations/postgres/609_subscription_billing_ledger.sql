-- Prompt 13: Abo-Katalog (10 EUR netto/Tag-Referenz), 19 % USt, Rechnungen, Mahnstatus, unveraenderliches Finanz-Ledger.

CREATE SEQUENCE IF NOT EXISTS app.billing_invoice_number_seq
    AS bigint
    START WITH 1
    INCREMENT BY 1
    MINVALUE 1;

CREATE TABLE IF NOT EXISTS app.billing_subscription_plan (
    plan_code text PRIMARY KEY,
    billing_interval text NOT NULL,
    display_name_de text NOT NULL,
    net_amount_cents bigint NOT NULL,
    currency text NOT NULL DEFAULT 'EUR',
    vat_rate_bps integer NOT NULL DEFAULT 1900,
    reference_period_days integer NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_billing_plan_interval CHECK (
        billing_interval IN ('day', 'week', 'month', 'year')
    ),
    CONSTRAINT chk_billing_plan_net_nonneg CHECK (net_amount_cents >= 0),
    CONSTRAINT chk_billing_plan_vat_bps CHECK (vat_rate_bps >= 0 AND vat_rate_bps <= 2700),
    CONSTRAINT chk_billing_plan_ref_days CHECK (reference_period_days > 0)
);

COMMENT ON TABLE app.billing_subscription_plan IS
    'Preisliste Abo: Netto-Cent pro Periode, USt in Basispunkten (1900 = 19 %), Referenz-Tage zur Nachvollziehbarkeit.';

CREATE TABLE IF NOT EXISTS app.tenant_subscription (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    plan_code text NOT NULL REFERENCES app.billing_subscription_plan (plan_code),
    status text NOT NULL DEFAULT 'active',
    dunning_stage text NOT NULL DEFAULT 'none',
    current_period_start date,
    current_period_end date,
    cancel_at_period_end boolean NOT NULL DEFAULT false,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_tenant_subscription_status CHECK (
        status IN ('trialing', 'active', 'past_due', 'canceled', 'expired')
    ),
    CONSTRAINT chk_tenant_subscription_dunning CHECK (
        dunning_stage IN (
            'none',
            'reminder_soft',
            'reminder_firm',
            'service_suspended',
            'subscription_terminated'
        )
    )
);

COMMENT ON TABLE app.tenant_subscription IS
    'Aktuelles Abo pro Tenant; Planwechsel und Kuendigung werden im Finanz-Ledger protokolliert.';

CREATE TABLE IF NOT EXISTS app.billing_invoice (
    invoice_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    invoice_number text NOT NULL,
    invoice_kind text NOT NULL DEFAULT 'standard',
    credits_invoice_id uuid REFERENCES app.billing_invoice (invoice_id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'draft',
    currency text NOT NULL DEFAULT 'EUR',
    total_net_cents bigint NOT NULL,
    total_vat_cents bigint NOT NULL,
    total_gross_cents bigint NOT NULL,
    issued_ts timestamptz,
    due_ts timestamptz,
    paid_ts timestamptz,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_billing_invoice_number UNIQUE (invoice_number),
    CONSTRAINT chk_billing_invoice_kind CHECK (invoice_kind IN ('standard', 'credit')),
    CONSTRAINT chk_billing_invoice_status CHECK (
        status IN ('draft', 'issued', 'paid', 'partially_paid', 'void', 'uncollectible')
    ),
    CONSTRAINT chk_billing_invoice_credit_ref CHECK (
        (invoice_kind = 'credit' AND credits_invoice_id IS NOT NULL)
        OR (invoice_kind = 'standard' AND credits_invoice_id IS NULL)
    ),
    CONSTRAINT chk_billing_invoice_totals_sign CHECK (
        (invoice_kind = 'standard' AND total_gross_cents >= 0)
        OR (invoice_kind = 'credit' AND total_gross_cents <= 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_billing_invoice_tenant_created
    ON app.billing_invoice (tenant_id, created_ts DESC);

COMMENT ON TABLE app.billing_invoice IS
    'Rechnung/Gutschrift; Positionen append-only. Storno durch Gutschrift oder Status void.';

CREATE TABLE IF NOT EXISTS app.billing_invoice_line (
    line_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id uuid NOT NULL REFERENCES app.billing_invoice (invoice_id) ON DELETE CASCADE,
    line_idx integer NOT NULL,
    line_type text NOT NULL,
    description text NOT NULL,
    net_cents bigint NOT NULL,
    vat_cents bigint NOT NULL,
    gross_cents bigint NOT NULL,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_billing_invoice_line_idx UNIQUE (invoice_id, line_idx),
    CONSTRAINT chk_billing_invoice_line_type CHECK (
        line_type IN ('subscription', 'credit', 'adjustment', 'other')
    )
);

COMMENT ON TABLE app.billing_invoice_line IS
    'Rechnungspositionen: nach Erstellung nicht aendern (nueber neue Belege korrigieren).';

CREATE TABLE IF NOT EXISTS app.billing_financial_ledger (
    ledger_entry_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    event_type text NOT NULL,
    currency text NOT NULL DEFAULT 'EUR',
    amount_gross_cents bigint,
    invoice_id uuid REFERENCES app.billing_invoice (invoice_id) ON DELETE SET NULL,
    actor text,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_billing_fin_ledger_event CHECK (
        event_type IN (
            'invoice_issued',
            'credit_issued',
            'payment_allocated',
            'plan_changed',
            'renewal',
            'cancellation',
            'dunning_updated'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_billing_fin_ledger_tenant_ts
    ON app.billing_financial_ledger (tenant_id, created_ts DESC);

COMMENT ON TABLE app.billing_financial_ledger IS
    'Append-only Journal: Abo, Rechnungen, Zahlungszuordnungen, Mahnungen — revisionssicher.';

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
    ('sub_daily_std', 'day', 'Tagesabo', 1000, 'EUR', 1900, 1, true),
    ('sub_week_std', 'week', 'Wochenabo', 7000, 'EUR', 1900, 7, true),
    ('sub_month_std', 'month', 'Monatsabo', 30000, 'EUR', 1900, 30, true),
    ('sub_year_std', 'year', 'Jahresabo', 365000, 'EUR', 1900, 365, true)
ON CONFLICT (plan_code) DO NOTHING;

INSERT INTO app.tenant_subscription (
    tenant_id,
    plan_code,
    status,
    dunning_stage,
    current_period_start,
    current_period_end,
    cancel_at_period_end,
    meta_json
)
VALUES (
    'default',
    'sub_month_std',
    'active',
    'none',
    CURRENT_DATE,
    CURRENT_DATE + 30,
    false,
    '{"seed": "609_subscription_billing_ledger"}'::jsonb
)
ON CONFLICT (tenant_id) DO NOTHING;
