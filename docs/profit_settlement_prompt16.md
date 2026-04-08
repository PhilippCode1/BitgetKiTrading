# Kontrolliertes Settlement zur Bitget-Treasury (Prompt 16)

## Prinzip

- **Interne Gebuehr** (Prompt 15: Statement, HWM) und **externe Auszahlung** sind getrennt: das Gateway fuehrt **keine** automatisierte Bitget-Withdraw-/Transfer-API aus.
- Ablauf: freigegebenes Statement (`admin_approved`, Gebuehr > 0) → **Settlement-Request** → optionale **Treasury-Zweitfreigabe** → **Payout dokumentieren** (Referenz) → **Abschluss bestaetigen**.
- Jeder Schritt erzeugt einen Eintrag in `app.profit_fee_settlement_audit` (append-only).

## Datenbank

Migration: `infra/migrations/postgres/612_profit_fee_settlement_treasury.sql`

- `app.treasury_settlement_config` — Ziel-Asset, Netzwerk, oeffentliche Hinweise, Limits (ohne Private Keys).
- `app.profit_fee_settlement_request` — Statusmaschine, Referenzen, keine Exchange-Responses.
- `app.profit_fee_settlement_audit` — Audit-Trail.

**Idempotenz:** Pro Statement hoechstens ein aktiver Request (partieller Unique-Index); hoechstens ein erfolgreicher `settled`-Datensatz pro Statement.

## Pipeline-Version

`shared_py.settlement_pipeline` — `SETTLEMENT_PIPELINE_VERSION`, erlaubte Uebergaenge.

Zustaende: `pending_treasury` → `approved_for_payout` → `payout_recorded` → `settled`; Abbruch: `cancelled` / `failed`.

## API (Gateway)

| Bereich    | Methode | Pfad                                                           |
| ---------- | ------- | -------------------------------------------------------------- |
| Treasury   | GET     | `/v1/commerce/admin/treasury/configs`                          |
| Treasury   | PATCH   | `/v1/commerce/admin/treasury/configs/{config_id}`              |
| Settlement | POST    | `/v1/commerce/admin/settlements/from-statement/{statement_id}` |
| Settlement | POST    | `/v1/commerce/admin/settlements/{id}/treasury-approve`         |
| Settlement | POST    | `/v1/commerce/admin/settlements/{id}/record-payout`            |
| Settlement | POST    | `/v1/commerce/admin/settlements/{id}/confirm-settled`          |
| Settlement | POST    | `/v1/commerce/admin/settlements/{id}/cancel`                   |
| Settlement | POST    | `/v1/commerce/admin/settlements/{id}/fail`                     |
| Settlement | GET     | `/v1/commerce/admin/settlements`                               |
| Settlement | GET     | `/v1/commerce/admin/settlements/{id}`                          |
| Settlement | GET     | `/v1/commerce/admin/settlements/{id}/audit`                    |

Kunde: `GET /v1/commerce/customer/profit-fee/summary` liefert unter `settlements` eine gekuerzte Liste (Status, Betraege, Referenzen).

## Konfiguration

- `PROFIT_FEE_SETTLEMENT_ENABLED` (Default `true`)
- `PROFIT_FEE_SETTLEMENT_TREASURY_SECONDARY_APPROVAL` (Default `false`) — wenn `true`, Startstatus `pending_treasury`, sonst `approved_for_payout`.

## Code

- `api_gateway.db_settlement`
- `api_gateway.routes_commerce_settlement`
