-- Prompt 11: Kunden-Lebenszyklus (21-Tage-Trial, Vertrag, Admin-Freigabe) + Audit-Trail.

CREATE TABLE IF NOT EXISTS app.tenant_customer_lifecycle (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    lifecycle_status text NOT NULL DEFAULT 'registered',
    email_verified boolean NOT NULL DEFAULT false,
    trial_started_at timestamptz,
    trial_ends_at timestamptz,
    status_before_suspension text,
    cancelled_ts timestamptz,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_tenant_lifecycle_status CHECK (
        lifecycle_status IN (
            'invited',
            'registered',
            'trial_active',
            'trial_expired',
            'contract_pending',
            'contract_signed_waiting_admin',
            'live_approved',
            'suspended',
            'cancelled'
        )
    ),
    CONSTRAINT chk_status_before_suspension CHECK (
        status_before_suspension IS NULL
        OR status_before_suspension IN (
            'invited',
            'registered',
            'trial_active',
            'trial_expired',
            'contract_pending',
            'contract_signed_waiting_admin',
            'live_approved'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_tenant_customer_lifecycle_status
    ON app.tenant_customer_lifecycle (lifecycle_status);

COMMENT ON TABLE app.tenant_customer_lifecycle IS
    'Prompt-11-Status je Tenant; Trial 21 Kalendertage (shared_py.product_policy.TRIAL_PERIOD_DAYS).';

CREATE TABLE IF NOT EXISTS app.tenant_lifecycle_audit (
    audit_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    from_status text,
    to_status text NOT NULL,
    actor text NOT NULL,
    actor_role text NOT NULL DEFAULT 'system',
    reason_code text,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_lifecycle_audit_tenant_created
    ON app.tenant_lifecycle_audit (tenant_id, created_ts DESC);

COMMENT ON TABLE app.tenant_lifecycle_audit IS
    'Append-only Audit zu Lifecycle-Wechseln (Prompt 11).';

-- Seed aus bestehenden Modul-Mate-Gates (bestehende Mandanten ohne Datenverlust).
INSERT INTO app.tenant_customer_lifecycle (
    tenant_id,
    lifecycle_status,
    email_verified,
    trial_started_at,
    trial_ends_at
)
SELECT
    g.tenant_id,
    CASE
        WHEN g.account_suspended THEN 'suspended'
        WHEN g.admin_live_trading_granted THEN 'live_approved'
        WHEN g.contract_accepted THEN 'contract_signed_waiting_admin'
        WHEN g.trial_active THEN 'trial_active'
        ELSE 'registered'
    END::text,
    true,
    NULL,
    NULL
FROM app.tenant_modul_mate_gates g
ON CONFLICT (tenant_id) DO NOTHING;

INSERT INTO app.tenant_customer_lifecycle (tenant_id, lifecycle_status, email_verified)
SELECT t.tenant_id, 'registered', false
FROM app.tenant_commercial_state t
WHERE NOT EXISTS (
    SELECT 1 FROM app.tenant_customer_lifecycle e WHERE e.tenant_id = t.tenant_id
)
ON CONFLICT (tenant_id) DO NOTHING;
