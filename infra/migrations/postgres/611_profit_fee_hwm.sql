-- Prompt 15: Gewinnbeteiligung (10 % Ziel) mit High-Water-Mark, Statements, Streitfall, revisionssicheren Events.

CREATE TABLE IF NOT EXISTS app.profit_fee_hwm_state (
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE RESTRICT,
    trading_mode text NOT NULL,
    high_water_mark_cents bigint NOT NULL DEFAULT 0,
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pk_profit_fee_hwm PRIMARY KEY (tenant_id, trading_mode),
    CONSTRAINT chk_profit_fee_hwm_mode CHECK (trading_mode IN ('paper', 'live')),
    CONSTRAINT chk_profit_fee_hwm_nonneg CHECK (high_water_mark_cents >= 0)
);

COMMENT ON TABLE app.profit_fee_hwm_state IS
    'Kumulativer realisierter PnL-Hoechststand nach letzter freigegebener Gebuehr (Cent, USD-Referenz).';

CREATE TABLE IF NOT EXISTS app.profit_fee_statement (
    statement_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE RESTRICT,
    trading_mode text NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    cumulative_realized_pnl_cents bigint NOT NULL,
    hwm_before_cents bigint NOT NULL,
    incremental_profit_cents bigint NOT NULL,
    fee_rate_basis_points integer NOT NULL DEFAULT 1000,
    fee_amount_cents bigint NOT NULL,
    currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL DEFAULT 'draft',
    customer_ack_ts timestamptz,
    customer_ack_note text,
    dispute_reason text,
    void_reason text,
    superseded_by uuid REFERENCES app.profit_fee_statement (statement_id) ON DELETE SET NULL,
    corrects_statement_id uuid REFERENCES app.profit_fee_statement (statement_id) ON DELETE SET NULL,
    calculation_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    admin_approved_ts timestamptz,
    admin_approved_by text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_profit_fee_stmt_mode CHECK (trading_mode IN ('paper', 'live')),
    CONSTRAINT chk_profit_fee_stmt_period CHECK (period_end >= period_start),
    CONSTRAINT chk_profit_fee_stmt_status CHECK (
        status IN (
            'draft',
            'issued',
            'disputed',
            'admin_approved',
            'voided',
            'superseded'
        )
    ),
    CONSTRAINT chk_profit_fee_stmt_rate CHECK (
        fee_rate_basis_points >= 0 AND fee_rate_basis_points <= 10000
    ),
    CONSTRAINT chk_profit_fee_stmt_fee_nonneg CHECK (fee_amount_cents >= 0),
    CONSTRAINT chk_profit_fee_stmt_incr_nonneg CHECK (incremental_profit_cents >= 0)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_profit_fee_statement_active_period
    ON app.profit_fee_statement (tenant_id, trading_mode, period_start, period_end)
    WHERE status NOT IN ('voided', 'superseded');

CREATE INDEX IF NOT EXISTS idx_profit_fee_statement_tenant_period
    ON app.profit_fee_statement (tenant_id, period_end DESC, trading_mode);

COMMENT ON TABLE app.profit_fee_statement IS
    'Gebuehren-Statement je Zeitraum und Handelsmodus; Freigabe setzt HWM atomar.';

CREATE TABLE IF NOT EXISTS app.profit_fee_calculation_event (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_ts timestamptz NOT NULL DEFAULT now(),
    tenant_id text NOT NULL,
    trading_mode text NOT NULL,
    period_start date NOT NULL,
    period_end date NOT NULL,
    actor text NOT NULL DEFAULT '',
    engine_version text NOT NULL DEFAULT 'profit-fee-engine-1',
    input_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    statement_id uuid REFERENCES app.profit_fee_statement (statement_id) ON DELETE SET NULL,
    CONSTRAINT chk_profit_fee_calc_mode CHECK (trading_mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_profit_fee_calc_tenant_ts
    ON app.profit_fee_calculation_event (tenant_id, created_ts DESC);

COMMENT ON TABLE app.profit_fee_calculation_event IS
    'Append-only: jede Berechnung/Erstellung fuer Revision und Reproduzierbarkeit.';
