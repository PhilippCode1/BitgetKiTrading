# Billing-Engine (Prepaid API-Flatrate, PROMPT 19)

## Regeln

- **Taegliche Pauschale**: Vom `app.customer_wallet.prepaid_balance_list_usd` wird pro UTC-Tag hoechstens `BILLING_DAILY_API_FEE_USD` (Standard 50) abgebucht; das Saldo wird nicht negativ.
- **Neue Trades**: Eroeffnung nur wenn Prepaid **≥ `BILLING_MIN_BALANCE_NEW_TRADE_USD`** (Standard 50), sofern `BILLING_PREPAID_GATE_ENABLED=true` im **paper-broker** oder **live-broker**.
- **Laufende Trades**: Keine automatischen Zwangs-Schliessungen bei niedrigem Guthaben; **reduce-only** / **Safety-Bypass** bleiben unberuehrt.

## Schwellen (nach Tagesabzug)

| Stufe      | Bedingung (Standard) |
| ---------- | -------------------- |
| `warning`  | Saldo ≤ 100 USD      |
| `critical` | Saldo ≤ 50 USD       |
| `depleted` | Saldo ≤ 0 USD        |

Pro Stufe und UTC-Tag hoechstens ein Eintrag in `app.billing_balance_alert` plus `customer_portal_audit` (`billing_balance_alert`). Zusaetzlich `billing_daily_charge_recorded` je erfolgreichem Lauf.

## Datenmodell

- `app.billing_daily_accrual`: idempotent pro `(tenant_id, accrual_date)`.
- `app.billing_balance_alert`: revisionssichere Warnungen.
- `app.usage_ledger`: Zeilen `api_daily_flat_fee` mit Meta (Saldo vor/nach, konfigurierte Pauschale).

## API / Jobs

| Aktion                   | Ort                                                                                                              |
| ------------------------ | ---------------------------------------------------------------------------------------------------------------- |
| Tageslauf (alle Tenants) | `POST /v1/commerce/internal/billing/run-daily` mit Header `X-Commercial-Meter-Secret` (wie Metering)             |
| Kunden-Transparenz       | `GET /v1/commerce/customer/balance` → `billing.status`, `daily_accruals_recent`, `balance_alerts_recent`         |
| Lokal simulieren         | `python scripts/simulate_billing_day.py` (Migration **600** anwenden, `DATABASE_URL`, `COMMERCIAL_ENABLED=true`) |

## Konfiguration

Gateway: `BILLING_*` in `config/gateway_settings.py`.  
Broker: `BILLING_PREPAID_GATE_ENABLED`, `BILLING_PREPAID_TENANT_ID`, `BILLING_MIN_BALANCE_NEW_TRADE_USD`.
