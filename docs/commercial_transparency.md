# Kommerzielle Integritaet und Kostenwahrheit

## Prinzipien

- **Verkaufen ja, aber sauber:** keine Dark Patterns, keine stille Ueberberechnung, keine im UI verschleierten Kostenpfade.
- **Auditierbar:** Owner und Operator koennen aus `app.usage_ledger` und Plan-Definitionen die **List-USD**-Groesse jeder belastbaren Zeile nachvollziehen.
- **Keine versteckten Multiplikatoren:** Spalte `platform_markup_factor` ist per DB-Check auf `1.0` fixiert; ausschliesslich dokumentierte Formeln (z. B. LLM: `(tokens/1000) * llm_per_1k_tokens_list_usd`).

## Datenmodell (Migration `594_commercial_usage_entitlements.sql`)

| Tabelle                           | Zweck                                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| `app.commercial_plan_definitions` | Oeffentliche Plan-Metadaten, Entitlements, **Token-Cap**, **Listenpreis** `llm_per_1k_tokens_list_usd`, Transparenz-Text |
| `app.tenant_commercial_state`     | Tenant → Plan, optionales **Budget-Cap** `budget_cap_usd_month` (List-USD / Monat)                                       |
| `app.usage_ledger`                | Append-only Journal: `event_type`, `quantity`, `unit`, `unit_price_list_usd`, `line_total_list_usd`, `meta_json`         |

## API (Gateway)

Voraussetzung: `COMMERCIAL_ENABLED=true` und Migration ausgefuehrt.

| Methode | Pfad                           | Auth                                                           | Beschreibung                                           |
| ------- | ------------------------------ | -------------------------------------------------------------- | ------------------------------------------------------ |
| GET     | `/v1/commerce/plans`           | Sensible Reads (`gateway:read` / JWT / Internal-Key)           | Plan-Katalog inkl. referenzierten List-Preisen         |
| GET     | `/v1/commerce/usage/summary`   | `billing:read` oder Admin                                      | Monats-Summen, Cap-/Budget-Flags                       |
| GET     | `/v1/commerce/usage/ledger`    | `billing:read` oder Admin                                      | Letzte Ledger-Zeilen                                   |
| GET     | `/v1/commerce/invoice-preview` | `billing:read` oder Admin                                      | Aggregat + juengste Positionen (kein externes Billing) |
| POST    | `/v1/commerce/internal/usage`  | Header `X-Commercial-Meter-Secret` = `COMMERCIAL_METER_SECRET` | Dienst-zu-Dienst Metering (z. B. LLM-Orchestrator)     |

**Tenant:** Standard `COMMERCIAL_DEFAULT_TENANT_ID`; sonst JWT-Claim `tenant_id`. Nur `admin:write` darf fremde Tenants per Query `tenant_id` lesen.

## Premium-Rechenzeit / LLM

- Abrechnungsrelevante Eintraege nutzen `event_type=llm_tokens` mit **derselben** `llm_per_1k_tokens_list_usd` wie im Plan hinterlegt — keine zweite Preisstaffel „im Hintergrund“.
- Ueberschreitung von **Token-Cap** oder **Budget-Cap** fuehrt zu **402** auf dem Meter-Ingest (vor Schreiben ins Ledger).

## Frontend

- Keine Exchange-, Provider- oder Gateway-Secrets im Browser; Dashboard nutzt **serverseitigen** Proxy (`DASHBOARD_GATEWAY_AUTHORIZATION`) und **keine** `NEXT_PUBLIC_*` Secrets fuer Auth.
- Billing-UIs sollten nur aggregierte, nicht-geheime Kennzahlen aus den obigen GETs anzeigen.

## Umgebungsvariablen

| Variable                       | Bedeutung                                                                                  |
| ------------------------------ | ------------------------------------------------------------------------------------------ |
| `COMMERCIAL_ENABLED`           | Master-Schalter                                                                            |
| `COMMERCIAL_DEFAULT_TENANT_ID` | Fallback-Tenant                                                                            |
| `COMMERCIAL_METER_SECRET`      | Geheimer Header fuer POST `/internal/usage` (Production: Mindestlaenge wie andere Secrets) |

## Verweise (Launch-Paket)

- `docs/PRODUCT_PLANS_AND_USAGE.md` — Planmatrix aus Seed-Daten, Upgrade/Downgrade-Prozess, Support-Platzhalter
- `docs/LAUNCH_PACKAGE.md` — Gesamtindex Produktbetrieb
- `docs/EXTERNAL_GO_LIVE_DEPENDENCIES.md` — was ausserhalb des Repos fuer Go-Live noetig bleibt
