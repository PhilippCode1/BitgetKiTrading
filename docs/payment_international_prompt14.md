# Internationale Zahlungsschiene (Prompt 14)

## Stripe (Kunde)

- Checkout: `PAYMENT_STRIPE_*`, Methoden über `PAYMENT_STRIPE_METHOD_TYPES` (z. B. `card`, `link`, `alipay`, `wechat_pay`).
- Wallets (Apple Pay / Google Pay) erscheinen im Stripe Payment Sheet, sofern Konto und Domain es zulassen.
- **Alipay / WeChat Pay:** in den Capabilities als `wallet_topup_only` markiert — keine wiederkehrende Abrechnung über diese Schiene; Abos laufen über konfigurierte Abo-Preise / Stripe wo möglich.
- Webhook: `POST /v1/commerce/payments/webhooks/stripe` — asynchrone Zahlungen erst nach `checkout.session.async_payment_succeeded` voll verbuchen.

## Wise (Treasury / Backoffice)

- **Kein** Kunden-Checkout-Button: Eingang für Server-zu-Server-Webhooks.
- ENV: `PAYMENT_WISE_WEBHOOK_ENABLED`, `PAYMENT_WISE_WEBHOOK_SECRET`.
- Request: Roh-JSON-Body; Header **`X-Wise-Signature`**: HMAC-SHA256 über den Body, Hex-String (dieses Repo). Vor Live-Betrieb mit [Wise API-Dokumentation](https://api-docs.wise.com) zur tatsächlichen Signaturvariante abgleichen.
- Idempotenz: `app.payment_rail_webhook_inbox` (`rail=wise`).

## PayPal (Stub)

- Bis eine produktive PayPal Commerce / Subscriptions-Anbindung existiert: `POST /v1/commerce/payments/webhooks/paypal` mit Header **`X-Paypal-Stub-Secret`** (`PAYMENT_PAYPAL_STUB_*`).
- Produktive PayPal-Abos sind in den Capabilities als eigene, derzeit deaktivierte Methode ausgewiesen (`paypal_subscriptions`).

## Admin-Diagnose

- `GET /v1/commerce/admin/payments/diagnostics` (JWT mit `billing:admin` oder `admin:write`, bzw. Dev ohne erzwungenes Auth wie andere Commerce-Admin-Routen).
- Liefert Capabilities-Kurzform, letzte Einträge aus `payment_webhook_failure_log`, Aggregat `payment_rail_webhook_inbox`.

## Migration

- `infra/migrations/postgres/610_payment_international_rails.sql`
