# Abo-Billing, 19 % USt und Finanz-Ledger (Prompt 13)

## Referenzpreis

- **10 EUR netto pro Tag** (`STANDARD_DAILY_NET_CENTS_EUR` = 1000) — siehe `shared_py/billing_subscription_contract.py`.
- Abgeleitete Perioden (Konvention): Woche = 7 Tage, Monat = 30 Tage, Jahr = 365 Tage.
- **USt:** 19 % als **1900 Basispunkte** im Katalog; Berechnung zentral in `shared_py/subscription_billing_pricing.py` und `commercial_data_model.vat_amounts_from_net_cents`.

## Datenbank (Migration `609_subscription_billing_ledger.sql`)

| Tabelle                         | Rolle                                                                                                               |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `app.billing_subscription_plan` | Konfigurierbare Pläne (Netto-Cent, `vat_rate_bps`, Währung, Intervall).                                             |
| `app.tenant_subscription`       | Aktuelles Abo, Status, **Mahnstufe** (`dunning_stage`), Perioden.                                                   |
| `app.billing_invoice`           | Rechnungen und Gutschriften (`invoice_kind`), Summen netto/USt/brutto.                                              |
| `app.billing_invoice_line`      | Positionen (append-only nach Erstellung).                                                                           |
| `app.billing_financial_ledger`  | **Append-only** Journal: Ausstellung, Gutschrift, Zahlungszuordnung, Planwechsel, Verlängerung, Kündigung, Mahnung. |

Rechnungsnummern: Sequenz `app.billing_invoice_number_seq`, Format `INV-000000001`.

## API-Gateway

### Kunde (`billing:read`)

- `GET /v1/commerce/customer/billing/plans` — Preise inkl. berechneter USt/Brutto.
- `GET /v1/commerce/customer/billing/subscription` — Abo + `pricing_preview`.
- `GET /v1/commerce/customer/billing/invoices`
- `GET /v1/commerce/customer/billing/invoices/{id}/lines`
- `GET /v1/commerce/customer/billing/ledger`

### Admin (`billing:admin`)

- `GET /v1/commerce/admin/billing/subscriptions`
- `GET /v1/commerce/admin/billing/tenant/{tenant_id}/snapshot`
- `POST /v1/commerce/admin/billing/invoices/issue` — Body: `tenant_id`, `plan_code`, optional `period_label`
- `POST /v1/commerce/admin/billing/invoices/credit` — volle Gutschrift zu einer Standard-Rechnung
- `PATCH /v1/commerce/admin/billing/tenant/{tenant_id}/dunning`
- `POST /v1/commerce/admin/billing/tenant/{tenant_id}/plan`
- `POST /v1/commerce/admin/billing/tenant/{tenant_id}/cancel`
- `POST /v1/commerce/admin/billing/tenant/{tenant_id}/renewal`
- `POST /v1/commerce/admin/billing/payments/allocate` — Journal-Eintrag `payment_allocated` (optional `payment_intent_id` im `meta_json`)

## Dashboard

- Kundenbereich: `/console/account/billing` (serverseitige GET über Gateway-JWT).

## Nutzungs-Ledger

- `app.usage_ledger` (Migration 594) bleibt das **API-/Metering-Journal** (List-USD).
- Prompt 13 ergänzt das **Abonnement-/Rechnungs-Ledger** in `app.billing_financial_ledger` — fachlich getrennt.
