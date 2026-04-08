# Gewinnbeteiligung (10 %) und High-Water-Mark (Prompt 15)

## Fachmodell

- **Kumulative realisierte PnL** (USD-Cent, Ganzzahl): vom Kunden/Handelssystem gelieferte Summe realisierter Gewinne/Verluste bis zum Periodenende — **reproduzierbar** über `pnl_source_ref` und `calculation_json` im Statement.
- **High-Water-Mark (HWM)**: Höchster nach einer **Admin-Freigabe** (`admin_approved`) vereinbarter Stand der kumulativen PnL je `(tenant_id, trading_mode)`.
- **Inkrementelle Gewinnbasis**: `max(0, kumulativ_ende - hwm_vorher)`.
- **Gebühr**: `profit_share_fee_cents` aus `shared_py.commercial_data_model` mit `fee_rate_basis_points` (Default **1000** = **10 %**).

Damit wird dieselbe Gewinnbasis nicht doppelt belastet, solange das HWM-Update nur bei Freigabe erfolgt.

## Datenbank

Migration: `infra/migrations/postgres/611_profit_fee_hwm.sql`

- `app.profit_fee_hwm_state`
- `app.profit_fee_statement`
- `app.profit_fee_calculation_event` (append-only)

## API (Gateway)

| Rolle | Methode | Pfad                                                            |
| ----- | ------- | --------------------------------------------------------------- |
| Kunde | GET     | `/v1/commerce/customer/profit-fee/summary`                      |
| Kunde | POST    | `/v1/commerce/customer/profit-fee/statements/{id}/acknowledge`  |
| Kunde | POST    | `/v1/commerce/customer/profit-fee/statements/{id}/dispute`      |
| Admin | POST    | `/v1/commerce/admin/profit-fee/preview`                         |
| Admin | POST    | `/v1/commerce/admin/profit-fee/statements/draft`                |
| Admin | POST    | `/v1/commerce/admin/profit-fee/statements/{id}/issue`           |
| Admin | POST    | `/v1/commerce/admin/profit-fee/statements/{id}/approve`         |
| Admin | POST    | `/v1/commerce/admin/profit-fee/statements/{id}/void`            |
| Admin | POST    | `/v1/commerce/admin/profit-fee/statements/{id}/resolve-dispute` |
| Admin | GET     | `/v1/commerce/admin/profit-fee/statements`                      |

**Workflow:** Entwurf → `issue` → Kunde **ack** oder **dispute** → Admin **approve** (setzt HWM atomar) oder **void** / Streitfall **resolve-dispute** → erneut **issue**.

**Freigabe:** Erfordert Kunden-ACK **oder** `force_without_customer_ack=true`. Bei Status **disputed** ist **immer** `force_without_customer_ack=true` nötig.

## Konfiguration

- `PROFIT_FEE_MODULE_ENABLED` (Default `true`)
- `PROFIT_FEE_RATE_BASIS_POINTS` (Default `1000`)

## Code

- `shared_py.profit_fee_engine` — reine Berechnung
- `api_gateway.db_profit_fee` — Persistenz
- `api_gateway.routes_commerce_profit_fee` — HTTP

## Hinweis

Anbindung an **Live-/Paper-Broker-PnL** als automatische Datenquelle ist bewusst nicht fest verdrahtet: `cumulative_realized_pnl_cents` und `pnl_source_ref` werden adminseitig gesetzt (Batch/Export), bis eine dedizierte Integrationspipeline folgt.

**Settlement / Treasury (Prompt 16):** siehe `docs/profit_settlement_prompt16.md`.
