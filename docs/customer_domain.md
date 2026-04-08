# Kundenbereich: Domänenmodell und Grenzen

## Überblick

Das Modell ergänzt die bestehende Commerce-Schicht (`tenant_commercial_state`, `usage_ledger`, Pläne) um **kundenorientierte** Tabellen und APIs, ohne sensible Daten ins Dashboard-Frontend zu leaken.

## Begriffe

| Begriff                  | Speicherort / API                                                        | Hinweis                                                                                                                                                                              |
| ------------------------ | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Nutzer (Subjekt)**     | JWT `sub` + Gateway-Audit `actor`                                        | Kein separates Login-User-Schema in dieser Migration.                                                                                                                                |
| **Rollen**               | JWT `gateway_roles` / `scope`, optional `portal_roles` / `platform_role` | `billing:read` = Kundenbereich; `billing:admin` / `admin:write` = Admin-Commerce. `super_admin`-Portal nur mit `GATEWAY_SUPER_ADMIN_SUBJECT` (siehe `docs/api_gateway_security.md`). |
| **Kundenkonto**          | `tenant_id` ↔ `tenant_commercial_state`                                  | Ein Tenant = ein kommerzieller Account.                                                                                                                                              |
| **Guthaben**             | `app.customer_wallet.prepaid_balance_list_usd`                           | List-USD, manuell durch Betrieb buchbar.                                                                                                                                             |
| **Ledger / Buchungen**   | `app.usage_ledger` (bestehend)                                           | Kunden-API liefert **ohne** `meta_json`.                                                                                                                                             |
| **Zahlungen**            | `app.customer_payment_event`                                             | Nur maskierte Referenzen, Status, öffentliche Notizen.                                                                                                                               |
| **Telegram-Verknüpfung** | `app.customer_integration_snapshot.telegram_*`                           | Nur Status + öffentlicher Kurzhinweis (keine Chat-IDs).                                                                                                                              |
| **Broker-Verknüpfung**   | `app.customer_integration_snapshot.broker_*`                             | Dito.                                                                                                                                                                                |
| **Plan / Freigabe**      | `tenant_commercial_state` + `commercial_plan_definitions`                | Unverändert.                                                                                                                                                                         |
| **Audit**                | `app.customer_portal_audit` + `app.gateway_request_audit`                | Profil-Updates, Wallet, Zahlungen, Integration-Updates.                                                                                                                              |

## Migration

`infra/migrations/postgres/598_customer_portal_domain.sql` legt die Tabellen an und befüllt Default-Zeilen für bestehende Tenants.

`606_platform_super_admin_registry.sql`: Ankerzeile Super-Admin (Anzeigename) und **`app.portal_identity_security`** je Tenant (E-Mail verifiziert, MFA, Passwort-Login konfiguriert — Flags für künftige IdP-/OTP-Anbindung). API: `GET /v1/commerce/customer/security/summary`.

**Prompt 11:** `607_tenant_customer_lifecycle.sql` — Lebenszyklus + Audit. Kunden-API unter `/v1/commerce/customer/lifecycle/*` (Status, Trial, Capabilities, Audit); Admin-Transitions unter `/v1/commerce/admin/customer/lifecycle/*`. Nach jedem Statuswechsel werden die Zeilen in **`app.tenant_modul_mate_gates`** an den Prompt-11-Status angeglichen (Echtgeld erst ab `live_approved`).

## Admin vs. Kunde

- **Kunde**: Routen unter `/v1/commerce/customer/*`, Auth `billing:read` (oder Admin mit gleichem Tenant).
- **Betrieb**: `/v1/commerce/admin/customer/*`, Auth `billing:admin` oder `admin:write`.

## Dashboard

Unter `/console/account` mit Unterseiten Profil, Sprache, Telegram, Broker, Guthaben, API-Kosten, Zahlungen, Verlauf. Server-Rendering spricht das Gateway mit `DASHBOARD_GATEWAY_AUTHORIZATION` an; Profil-Änderungen laufen über `PATCH` am BFF `/api/dashboard/commerce/customer/me`.
