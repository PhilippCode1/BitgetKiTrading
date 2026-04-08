-- Prompt 14: Observability fuer Webhook-Fehlschlaege (Zahlungsschiene international).

CREATE TABLE IF NOT EXISTS app.payment_webhook_failure_log (
    log_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider text NOT NULL,
    provider_event_id text,
    intent_id uuid REFERENCES app.payment_deposit_intent (intent_id) ON DELETE SET NULL,
    error_class text,
    error_message text,
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_payment_webhook_fail_provider_len CHECK (char_length(provider) <= 64)
);

CREATE INDEX IF NOT EXISTS idx_payment_webhook_failure_log_created
    ON app.payment_webhook_failure_log (created_ts DESC);

COMMENT ON TABLE app.payment_webhook_failure_log IS
    'Nachvollziehbarkeit bei Settlement-Fehlern; Stripe/PayPal/Wise koennen erneut senden wenn Inbox outcome failed_processing.';

CREATE TABLE IF NOT EXISTS app.payment_rail_webhook_inbox (
    inbox_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rail text NOT NULL,
    event_fingerprint text NOT NULL,
    outcome text NOT NULL DEFAULT 'received',
    meta_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_ts timestamptz NOT NULL DEFAULT now(),
    updated_ts timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_payment_rail_webhook_fp UNIQUE (rail, event_fingerprint),
    CONSTRAINT chk_payment_rail_webhook_rail CHECK (char_length(rail) <= 32)
);

COMMENT ON TABLE app.payment_rail_webhook_inbox IS
    'Idempotenz fuer Nicht-Stripe-Webhooks (wise, paypal_stub, …).';
