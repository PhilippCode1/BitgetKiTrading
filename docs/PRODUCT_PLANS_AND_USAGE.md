# Produktlogik: Plaene, Entitlements, Nutzung, Caps

**Ehrliche Beschreibung:** Das Repo liefert **technische** Bausteine fuer Plaene, Entitlements und Usage-Metering. **List-USD** im Nutzungsjournal (`usage_ledger`) bleibt davon getrennt. **Prompt 13** ergänzt ein **Abo-/Rechnungsmodul** (EUR netto, 19 % USt, Rechnungen, Mahnstufen, append-only Finanz-Ledger) — siehe `docs/subscription_billing_prompt13.md`; externes PSP-Rechnungslauf kann darauf aufsetzen.

Siehe auch `docs/commercial_transparency.md` und Migration `594_commercial_usage_entitlements.sql`.

## 1. Planmatrix (Seed-Daten)

Die folgende Matrix entspricht den **Default-INSERTs** in der Migration (anpassbar per SQL/Admin-Prozess, nicht hardcodiert im Gateway-Kern).

| plan_id        | Anzeigename  | LLM (Entitlement) | signals_read | priority_queue | LLM Token-Cap / Monat | List-USD / 1k Tokens |
| -------------- | ------------ | ----------------- | ------------ | -------------- | --------------------- | -------------------- |
| `starter`      | Starter      | `standard`        | ja           | nein           | 500000                | 0.00200000 USD       |
| `professional` | Professional | `standard`        | ja           | ja             | 2000000               | 0.00200000 USD       |

**Transparenz-Hinweis aus Seed:** gleicher Token-Listenpreis; Unterschied = **Cap** und **Entitlements** (`priority_queue`), keine zweite versteckte Preisstaffel in der DB.

## 2. Entitlements

- Gespeichert als JSON in `commercial_plan_definitions.entitlements_json`.
- Semantik ist **produktdefiniert** (z. B. Feature-Flags im Orchestrator/Dashboard); Aenderungen = **Plan- und Release-Disziplin**, nicht stille Runtime-Magie.

## 3. Usage-Metering

- **Intern:** `POST /v1/commerce/internal/usage` mit Header `X-Commercial-Meter-Secret` (siehe Gateway-Routen).
- **Journal:** `app.usage_ledger` append-only; `platform_markup_factor` fix **1.0** (Constraint).
- **Premium-AI (LLM):** transparent ueber `event_type` (z. B. `llm_tokens`), Menge, `unit_price_list_usd`, `line_total_list_usd`.

## 4. Budget- und Token-Caps

| Mechanismus             | Feld / Ort                                     | Wirkung                                             |
| ----------------------- | ---------------------------------------------- | --------------------------------------------------- |
| Token-Cap pro Plan      | `llm_monthly_token_cap`                        | Ueberschreitung: Meter-Ingest **402** (vor Ledger). |
| Monatsbudget (List-USD) | `tenant_commercial_state.budget_cap_usd_month` | Ueberschreitung: Meter-Ingest **402**.              |

Caps sind **technische Schutzgrenzen**; sie ersetzen keine vertraglichen Limits — Vertrag bleibt extern.

## 5. Upgrade / Downgrade

**Im Repo:** kein Self-Service-Checkout. Operativer Standard:

1. Tenant in `app.tenant_commercial_state` auf neuen `plan_id` setzen (Transaktion, Audit).
2. Optional `budget_cap_usd_month` anpassen.
3. Kundenkommunikation und Vertrag **ausserhalb** des Codes.
4. JWT/Rollen ggf. anpassen (`billing:read`, `tenant_id`-Claim).

Downgrade: gleicher Prozess; bereits verbrauchte Ledger-Zeilen bleiben historisch.

## 6. Support- und Incident-Kanaele (Platzhalter)

| Kanal              | Zweck                           | Wo konfigurieren                                                                |
| ------------------ | ------------------------------- | ------------------------------------------------------------------------------- |
| E-Mail Support     | Endkunden / intern              | Organisatorisch; optional ENV `SUPPORT_EMAIL` (siehe `.env.production.example`) |
| Status / Incidents | Oeffentliche oder interne Seite | `STATUS_PAGE_URL` optional                                                      |
| P0 Trading         | On-Call, Telegram-Operator      | `docs/emergency_runbook.md`, Alert-Engine                                       |

**Keine** dieser URLs ersetzt rechtliche Pflichten oder professionelle Anlageberatung.

## 7. Was wir nicht versprechen

- Keine **Gewinn-** oder **Ueberrendite-Garantie**.
- Keine **„beste“** Strategie oder **weltbester** KI-Handel als Produktwahrheit.
- Keine **versteckten** Aufschlaege im Ledger (durch DB-Constraint abgesichert).

Belastbare Eigenschaften: **Auditierbarkeit**, **Rate-Limits**, **Rollen**, **manuelle Freigaben**, **Forensik**, **dokumentierte Gates**.
