-- Modul Mate: kommerzielle Gates pro Tenant (Abbild von shared_py.product_policy.CustomerCommercialGates).
-- Live-Broker prueft diese Zeile, wenn MODUL_MATE_GATE_ENFORCEMENT=true.

CREATE TABLE IF NOT EXISTS app.tenant_modul_mate_gates (
    tenant_id text PRIMARY KEY REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    trial_active boolean NOT NULL DEFAULT false,
    contract_accepted boolean NOT NULL DEFAULT false,
    admin_live_trading_granted boolean NOT NULL DEFAULT false,
    subscription_active boolean NOT NULL DEFAULT false,
    account_paused boolean NOT NULL DEFAULT false,
    account_suspended boolean NOT NULL DEFAULT false,
    updated_ts timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE app.tenant_modul_mate_gates IS
    'Steuert Demo/Live-Erlaubnis laut product_policy; Live-API (nicht Demo) zusaetzlich admin_live_trading_granted.';

CREATE INDEX IF NOT EXISTS idx_tenant_modul_mate_gates_updated
    ON app.tenant_modul_mate_gates (updated_ts DESC);

-- Standard-Tenant: Demo-API erlaubt (contract_accepted ohne Live-Freigabe => DEMO-Modus).
-- Echte Bitget-Live-Orders bleiben gesperrt, bis admin_live_trading_granted=true gesetzt wird.
INSERT INTO app.tenant_modul_mate_gates (
    tenant_id,
    trial_active,
    contract_accepted,
    admin_live_trading_granted,
    subscription_active,
    account_paused,
    account_suspended
)
VALUES ('default', false, true, false, true, false, false)
ON CONFLICT (tenant_id) DO NOTHING;
