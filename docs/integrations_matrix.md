# Integrationsmatrix (PROMPT 21)

Die Matrix fasst **externe Anbindungen** zusammen: Broker/Exchange, Telegram, Zahlungsprovider, LLM, Monitoring sowie Dashboard/Gateway. Sie wird bei jedem Aufruf von `GET /v1/system/health` (authentifizierte Operator-Aggregate-Auth) berechnet und im Feld `integrations_matrix` ausgeliefert.

## Zeilen (logische Integrationen)

| `integration_key`   | Inhalt                                                                               |
| ------------------- | ------------------------------------------------------------------------------------ |
| `broker_exchange`   | Paper-/Live-Broker + Market-Stream (Bitget-Pfad)                                     |
| `signal_pipeline`   | Feature-, Structure-, Signal-, Drawing-, News-Engine (Marktdaten/Kontext bis Signal) |
| `learning_engine`   | Learning-Engine-Probe (Scores, Drift, Registry-Pfade über Gateway-Proxies)           |
| `telegram`          | Alert-Engine inkl. Outbox-Hinweisen                                                  |
| `payment_provider`  | Stripe/Mock-Konfiguration                                                            |
| `llm_ai`            | LLM-Orchestrator + Fake-Provider-Hinweis                                             |
| `monitoring`        | Monitor-Engine + offene Alerts                                                       |
| `dashboard_gateway` | Postgres + Redis + Gateway-Auth-Flags                                                |

## Inhalt pro Zeile

- **Feature-Flags**: z. B. `LIVE_TRADE_ENABLE`, `TELEGRAM_DRY_RUN`, Checkout- und Stripe-Flags (nur booleans / Modi, keine Secrets).
- **Health**: aggregierter Status aus Gateway-Service-Probes (`HEALTH_URL_*`) und Konfigurationspruefungen (z. B. Stripe live ohne Webhook-Secret → `misconfigured`).
- **Live-Zugriff**: explizite Kombination aus `live_trade_enable` und `live_order_submission_enabled` (siehe Zeile `live_access`).
- **Credential-Referenzen**: nur **Namen** (`env:…`, optional `vault:…`), niemals Klartext.
- **Zeitstempel** (Tabelle `app.integration_connectivity_state`, Migration `602_integration_connectivity_state.sql`):
  - `last_success_ts` / `last_failure_ts` rollieren bei ok/disabled bzw. Fehlerzustaenden.
  - `last_error_public` speichert die letzte verstaendliche Fehlermeldung (ohne Secrets).

## UI

Unter **Console → System & Status** erscheint die Tabelle „Integrationsmatrix“ oberhalb der bestehenden Service-Kacheln; Monitor-Alerts und Telegram-Outbox bleiben darunter sichtbar.

## Betrieb

- Migration **602** muss angewendet sein, damit Zeitstempel persistiert werden; ohne Tabelle liefert das Gateway die Matrix weiterhin, aber ohne DB-Sync.
- Externe API-/HTTP-Fehler der angebundenen Dienste bleiben in `services[]` je Dienst mit `detail` / `http_status` sichtbar; die Matrix spiegelt die wichtigsten davon in `health_error_public` wider.
