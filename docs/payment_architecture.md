# Zahlungsarchitektur (Kundeneinzahlungen)

Kurzmatrix Sandbox vs. Live und Beispiel-Kontext fuer Freigaben: **`docs/PRODUCTION_READINESS_AND_API_CONTRACTS.md`**.

## Ziele

- **Erweiterbarkeit**: Neue Provider implementieren denselben Ablauf (Checkout → Webhook → Idempotenz → Wallet/Receipt).
- **Sandbox vs. Live**: `PAYMENT_MODE=sandbox|live` steuert Umgebung; Live erzwingt in Production vollständige Stripe-Webhook-Konfiguration (siehe `GatewaySettings`-Validierung).
- **Keine Secrets im Browser**: Checkout-URLs und Webhooks nur serverseitig; das Dashboard nutzt BFF-Routen mit `DASHBOARD_GATEWAY_AUTHORIZATION`, Mock-Abschluss mit `PAYMENT_MOCK_WEBHOOK_SECRET` nur auf dem Next.js-Server.

## Datenmodell

- `app.payment_deposit_intent`: Intent pro Tenant + `idempotency_key`, Status, Stripe-Session-ID, Receipt (`receipt_json`).
- `app.payment_webhook_inbox`: Idempotenz über `(provider, provider_event_id)`.
- `app.payment_webhook_failure_log` / `app.payment_rail_webhook_inbox` (Migration `610_payment_international_rails.sql`): Settlement-Fehler und Nicht-Stripe-Webhooks.

## API (API-Gateway)

| Methode | Pfad                                                         | Zweck                                                                                                                                                                    |
| ------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GET     | `/v1/commerce/customer/payments/capabilities`                | Feature-Flags je Zahlungsart (`payment-capabilities-v2`: Karte, Wallets über Stripe, PayPal über `link`, Alipay/WeChat nur Top-up, Wise/PayPal-Stub-Rails), ohne Secrets |
| POST    | `/v1/commerce/customer/payments/deposit/checkout`            | Header `Idempotency-Key`, Body `provider`, `amount_list_usd`, `currency`                                                                                                 |
| POST    | `/v1/commerce/customer/payments/deposit/resume`              | Stripe-Checkout-URL erneut, wenn Session noch offen                                                                                                                      |
| GET     | `/v1/commerce/customer/payments/deposit/intents/{intent_id}` | Status/Receipt (maskierte Session-ID)                                                                                                                                    |
| POST    | `/v1/commerce/payments/webhooks/stripe`                      | Rohbody + `Stripe-Signature`; u. a. `checkout.session.completed`, `async_payment_succeeded` / `async_payment_failed` (Alipay o. ä.)                                      |
| POST    | `/v1/commerce/payments/webhooks/mock`                        | Nur Sandbox/Test; Header `X-Payment-Mock-Secret`, Body `{ "intent_id": "…" }`                                                                                            |
| POST    | `/v1/commerce/payments/webhooks/wise`                        | Rohbody + `X-Wise-Signature` (HMAC-SHA256 hex, mit Wise-Live-Doku abgleichen); Idempotenz `app.payment_rail_webhook_inbox`                                               |
| POST    | `/v1/commerce/payments/webhooks/paypal`                      | Stub: Rohbody + `X-Paypal-Stub-Secret` bis PayPal Commerce produktiv; Inbox wie oben                                                                                     |
| GET     | `/v1/commerce/admin/payments/diagnostics`                    | `billing:admin` / `admin:write`: Capabilities-Kurzform, letzte `payment_webhook_failure_log`, Zähler Rail-Inbox                                                          |

## Zahlungsarten (Zielbild)

Über **Stripe Checkout** konfigurierbar (`PAYMENT_STRIPE_METHOD_TYPES`):

- Karten (`card`)
- Apple Pay / Google Pay (von Stripe angeboten, wenn am Payment Sheet verfügbar)
- PayPal (wo Stripe **Link** mit PayPal unterstützt: `link` in Method Types)
- `alipay`, `wechat_pay` je nach Stripe-Konto und Region

**Mock-Provider** (`provider=mock`): Lokaler Flow ohne PSP — Abschluss per Mock-Webhook.

## Lokaler Sandbox-Flow (Mock)

1. `COMMERCIAL_ENABLED=true`, `PAYMENT_CHECKOUT_ENABLED=true`, `PAYMENT_MOCK_ENABLED=true`, `PAYMENT_MOCK_WEBHOOK_SECRET` setzen (Gateway + optional Dashboard).
2. Migration `599_payment_deposit_architecture.sql` anwenden.
3. Checkout mit `provider: "mock"` starten; anschließend Mock-Webhook aufrufen (z. B. über Dashboard-BFF oder `curl`).

## Stripe Live

- Test- und Live-Keys strikt trennen; Webhook-Endpunkt in Stripe Dashboard auf `/v1/commerce/payments/webhooks/stripe` zeigen.
- Verarbeitet u. a. `checkout.session.completed` und asynchrone Zahlungen (`async_payment_succeeded` / `async_payment_failed`); Signatur mit `PAYMENT_STRIPE_WEBHOOK_SECRET`. Alipay/ähnliche Methoden: Gutschrift erst bei bezahltem Status (kein Abo über Alipay — siehe Capabilities `usage_constraint`).

## Internationale Rails (Wise, PayPal-Stub)

Siehe **`docs/payment_international_prompt14.md`** (ENV, Header, Produktionshinweise).

## Code-Module

- `api_gateway.payments.capabilities` — öffentliche Fähigkeiten
- `api_gateway.payments.stripe_checkout` — Session-Erstellung, Webhook-Parse
- `api_gateway.payments.deposit` — Checkout-Start, Verbuchung, Idempotenz
- `api_gateway.db_payment_intents` — Persistenz
- `api_gateway.routes_commerce_payments` — Webhook-Routen
