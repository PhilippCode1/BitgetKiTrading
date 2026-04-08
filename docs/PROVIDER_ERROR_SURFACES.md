# Bitget, LLM & Co.: Fehlerbilder, Logs, Health

**Ziel:** Gleiches Verständnis bei fehlenden Keys, Rate-Limits und Demo- vs. Live-Modus — **ohne** Geheimnisse in Logs oder Responses.

## Grundregeln

1. **Nie** vollständige API-Keys, Passwörter oder `Authorization`-Header loggen.
2. Strukturierte Logs: `event`, `provider`, `symbol` (falls sinnvoll), `http_status`, `error_code` (anbieterintern, gekürzt), `correlation_id` / `request_id` wenn vorhanden.
3. **`BITGET_DEMO_ENABLED`:** klar trennen — in Health/Ops-Texten „demo“ vs. „live“ erwähnen, nicht nur still schweigen.

## Bitget (REST / WebSocket)

| Situation                           | Erwartetes Verhalten                                                   | Ops-Hinweis                                                             |
| ----------------------------------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Fehlende oder ungültige Credentials | Auth-Fehler vom Client; Service degradiert oder überspringt Live-Pfade | Keys in [`docs/SECRETS_MATRIX.md`](SECRETS_MATRIX.md); Demo-Pfad prüfen |
| Rate-Limit / HTTP 429               | Backoff, Retry mit Jitter; Zähler/Metriken wo vorhanden                | [`docs/monitoring_runbook.md`](monitoring_runbook.md)                   |
| Wartung / 5xx                       | Retry nur idempotent; Circuit-Breaker nach Policy                      | Incident nach Latenz/Fehlerquote                                        |

Konfiguration: [`docs/bitget-config.md`](bitget-config.md).

## LLM-Orchestrator / Provider

| Situation               | Erwartetes Verhalten                                              | Ops-Hinweis                        |
| ----------------------- | ----------------------------------------------------------------- | ---------------------------------- |
| Fehlender Provider-Key  | Klare Konfigurationswarnung beim Start oder deaktiviertes Feature | Env laut Orchestrator-README       |
| Rate-Limit / Quota      | Strukturierter Fehler, kein Rohtext mit Key-Material              | Usage/Metering siehe Commerce-Doku |
| Modell nicht erreichbar | Timeout + sauberer HTTP-/Event-Fehler                             | Netzwerk und DNS prüfen            |

Direktzugriff nur mit internem Key: [`services/llm-orchestrator/README.md`](../services/llm-orchestrator/README.md).

## Health & Monitoring

- Gateway und Services: öffentliche Health-Endpoints sollten **keine** Secrets zurückgeben.
- Zentrale Gauges: [`docs/observability.md`](observability.md) — bei Daten-Staleness oder Provider-Ausfall greifen die bestehenden Alertregeln (`infra/observability/prometheus-alerts.yml`).

### `provider_ops_summary` (Gateway `GET /v1/system/health`)

Aggregat nur mit **Metadaten** (keine Key-Strings):

| Pfad                                 | Bedeutung                                                                                                                 |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `schema_version`                     | Schema-Version des Objekts (Integer)                                                                                      |
| `bitget.exchange_mode`               | `demo` oder `live` (aus Gateway-Konfiguration / `BITGET_DEMO_ENABLED`)                                                    |
| `bitget.trading_plane_hint`          | Kurzlabel Sandbox vs. Live (Hinweis, keine Order-Garantie)                                                                |
| `bitget.credentials_complete`        | Alle fuer den gewaehlten Modus erforderlichen Bitget-Env-Variablen gesetzt (Platzhalter wie `SET_ME` zaehlen als fehlend) |
| `bitget.gap_codes`                   | Liste z. B. `bitget_demo_credentials_incomplete`, `bitget_live_credentials_incomplete`                                    |
| `llm.llm_use_fake_provider`          | Fake-LLM aktiv (Gateway-Sicht)                                                                                            |
| `llm.openai_key_present_gateway_env` | Nur ob im **Gateway**-Prozess ein nicht-leerer OpenAI-Key gesetzt ist (Orchestrator kann eigene Env haben)                |
| `llm.orchestrator_probe`             | Teilfelder aus dem zuletzt geprobten `llm-orchestrator` `/health`, z. B. `llm_provider_gap`, `redis_ok`, `status`         |
| `hint_codes`                         | Vereinigte Ops-Codes; spiegeln sich im gleichen Health-JSON unter `warnings` als `provider:<code>`                        |

Runbook-Anker: [`docs/monitoring_runbook.md#bitget-llm-provider-health`](monitoring_runbook.md#bitget-llm-provider-health).

## Kurz-Runbook (Copy-Paste-Logik)

1. Symptom: „Keine Kurse / keine Signale“ → Health der `market-stream` / Gateway / Bitget-Config.
2. Symptom: „LLM antwortet nicht“ → Orchestrator-Logs, Provider-Quota, `INTERNAL_API_KEY` für interne Routen.
3. Immer: `pnpm rc:health` nach Änderungen an Edge-URLs oder Auth.
