-- P76: SaaS — Row Level Security (RLS) für alle Tabellen mit tenant_id; Redis-Keying separat (Code).
-- GUC: SET [LOCAL] app.current_tenant_id = '<id>';
--      optional (nur vertrauenswürdiger Code): app.rls_internal_all_tenants = '1'
-- View app.trades: DoD-Abfrage „SELECT * FROM app.trades“ = usage_ledger mit RLS (security_invoker).

-- Optional: Applikationsrolle (P76-Policies sind TO public; zukuenftig GRANT an trading_app)
DO $role$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'trading_app') THEN
        CREATE ROLE trading_app NOLOGIN;
    END IF;
END
$role$;

-- View mit Invoker-RLS (PG 15+): DoD-SELECT * FROM app.trades
CREATE OR REPLACE VIEW app.trades
WITH (security_invoker = true) AS
SELECT * FROM app.usage_ledger;

COMMENT ON VIEW app.trades IS
    'P76: Alias auf app.usage_ledger fuer DoD (SELECT * FROM app.trades) unter RLS.';

DO $rls$
DECLARE
    sc text;
    rel text;
    fullname text;
    names text[] := ARRAY[
        'app.telegram_link_pending',
        'app.customer_telegram_binding',
        'app.tenant_customer_lifecycle',
        'app.tenant_lifecycle_audit',
        'app.tenant_modul_mate_gates',
        'app.payment_deposit_intent',
        'app.profit_fee_hwm_state',
        'app.profit_fee_statement',
        'app.profit_fee_calculation_event',
        'app.billing_daily_accrual',
        'app.billing_balance_alert',
        'app.customer_domain_event',
        'app.customer_read_model_state',
        'app.profit_fee_settlement_request',
        'app.tenant_contract',
        'app.tenant_contract_document',
        'app.contract_review_queue',
        'app.tenant_subscription',
        'app.billing_invoice',
        'app.billing_financial_ledger',
        'app.subscription_billing_ledger',
        'app.customer_profile',
        'app.customer_wallet',
        'app.customer_payment_event',
        'app.customer_integration_snapshot',
        'app.customer_portal_audit',
        'app.portal_identity_security',
        'app.tenant_commercial_state',
        'app.usage_ledger',
        'app.customer_telegram_notify_prefs',
        'paper.accounts',
        'paper.account_ledger',
        'paper.positions'
    ];
    pol text := $p$
    ( tenant_id = current_setting('app.current_tenant_id', true) )
    OR ( coalesce( nullif( current_setting('app.rls_internal_all_tenants', true), ''), '' ) = '1' )
    $p$;
BEGIN
    FOREACH fullname IN ARRAY names
    LOOP
        sc := split_part(fullname, '.', 1);
        rel := split_part(fullname, '.', 2);
        IF to_regclass(fullname) IS NULL THEN
            RAISE NOTICE 'P76 RLS: Tabelle fehlt, Ueberspringe: %', fullname;
            CONTINUE;
        END IF;
        EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY', sc, rel);
        EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY', sc, rel);
        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I.%I', sc, rel);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_policy ON %I.%I FOR ALL TO public USING ( %s ) WITH CHECK ( %s )',
            sc, rel, pol, pol
        );
    END LOOP;
END
$rls$;

GRANT SELECT ON app.trades TO public;

COMMENT ON TABLE app.tenant_commercial_state IS
    'P76: RLS erzwingt: Zeilen je Mandant; Admin Ueberblick nur mit app.rls_internal_all_tenants=1 (sicherer Anwendungspfad).';
