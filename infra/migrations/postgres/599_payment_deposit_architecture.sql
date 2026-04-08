-- PROMPT 18: Einzahlungen — Intents, Webhook-Idempotenz, Receipt (ohne Secrets)

CREATE TABLE IF NOT EXISTS app.payment_deposit_intent (
    intent_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL REFERENCES app.tenant_commercial_state (tenant_id) ON DELETE CASCADE,
    idempotency_key text NOT NULL,
    provider text NOT NULL,
    environment text NOT NULL CHECK (environment IN ('sandbox', 'live')),
    amount_list_usd numeric(18, 8) NOT NULL,
    currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL DEFAULT 'created',
    provider_checkout_session_id text,
    provider_payment_intent_id text,
    receipt_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_error_public text,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_payment_intent_idem_len CHECK (char_length(idempotency_key) <= 128),
    CONSTRAINT chk_payment_intent_status CHECK (
        status IN (
            'created',
            'checkout_ready',
            'awaiting_payment',
            'processing',
            'succeeded',
            'failed',
            'canceled',
            'expired'
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_payment_intent_tenant_idem
    ON app.payment_deposit_intent (tenant_id, idempotency_key);

CREATE INDEX IF NOT EXISTS idx_payment_intent_tenant_status
    ON app.payment_deposit_intent (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_payment_intent_checkout_session
    ON app.payment_deposit_intent (provider_checkout_session_id)
    WHERE provider_checkout_session_id IS NOT NULL;

COMMENT ON TABLE app.payment_deposit_intent IS
    'Kundeneinzahlung: Checkout-Session / Provider-IDs; keine Karten- oder Wallet-Tokens.';

CREATE TABLE IF NOT EXISTS app.payment_webhook_inbox (
    inbox_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    provider_event_id text NOT NULL,
    intent_id uuid REFERENCES app.payment_deposit_intent (intent_id) ON DELETE SET NULL,
    processed_ts timestamptz,
    outcome text NOT NULL DEFAULT 'processed',
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_payment_webhook_provider_event UNIQUE (provider, provider_event_id)
);

COMMENT ON TABLE app.payment_webhook_inbox IS
    'Idempotente Webhook-Verarbeitung (Stripe event id, Mock-Nonce).';
