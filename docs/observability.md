# Observability: Prometheus, Grafana, Alerts

**Betriebs-Einstieg (Ketten, SLOs, Playbook):** [`OBSERVABILITY_AND_SLOS.md`](../OBSERVABILITY_AND_SLOS.md) im Repo-Root.

## Inventar (Stand Prompt 32)

| Schicht                         | Ort                                                                                          | Inhalt                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Metriken (pro Service)**      | `shared_py.observability.metrics`                                                            | `http_requests_total`, `http_request_latency_seconds`, `http_errors_total`, `worker_heartbeat_timestamp` (HTTP-Middleware **und** Hintergrund-Loops: Feature/Signal/Structure/Drawing/News, Paper-Consumer, Alert-Threads, Learning-Consumer, Live-Broker-Worker, Monitor-Scheduler, Market-Stream Feed-Health); Mount `/metrics`                                                                                                             |
| **Zentrale Betriebs-Gauges**    | `services/monitor-engine/.../prom_metrics.py` + `trading_db_metrics.py`                      | Frische, Stream-Lag, Drift, Kill-Switch, Reconcile, Orders, Signale, Alerts, Learning, Shadow-Live, **Durchsatz/Bestand/Risk (neu)**                                                                                                                                                                                                                                                                                                          |
| **Traces**                      | `shared_py.eventbus.EventEnvelope.trace`                                                     | Kontext pro Event (Erweiterungspunkt; kein OTLP-Exporter im Repo)                                                                                                                                                                                                                                                                                                                                                                             |
| **Logs**                        | stdlib `logging`, optional `LOG_FORMAT=json`                                                 | **Korrelation:** `corr_*` inkl. `corr_gateway_audit_id` / `corr_tenant_id` bei Gateway-Audit (`api_gateway/audit.py`), plus live-broker Execution-Logs                                                                                                                                                                                                                                                                                        |
| **Request-ID (HTTP)**           | Gateway-Middleware                                                                           | Client kann `x-request-id` / `x-correlation-id` mitsenden; fehlend: UUID bzw. `correlation_id` default = `request_id`. Response-Header: `X-Request-ID`, `X-Correlation-ID`; CORS `expose_headers`. **Logs:** `RequestContextLoggingFilter` (global via `config/logging_config.py`) setzt bei gesetztem Kontext `corr_request_id` / `corr_correlation_id` auf dem LogRecord; `live_broker_forward` reicht die Header an den live-broker weiter |
| **Gateway-Prometheus (Muster)** | `api_gateway/gateway_metrics.py`                                                             | `gateway_live_broker_forward_total{result}`, `gateway_live_broker_forward_latency_seconds`, `gateway_auth_failures_total{action}` — scrapen über bestehendes `/metrics` am Gateway (`instrument_fastapi`)                                                                                                                                                                                                                                     |
| **Dashboards**                  | `infra/observability/grafana/dashboards/bitget-trading-ops.json`, `bitget-sli-security.json` | Trading & Ops (inkl. Gateway→Live-Broker Forward, Pipeline-P95-Latenz, No-Trade-Rate, `worker_heartbeat_timestamp`-Alter); SLI/Sicherheit/Kommerziell                                                                                                                                                                                                                                                                                         |
| **SLO-Vertrag**                 | `docs/observability_slos.md`                                                                 | SLI→Metrik→Alert-Zuordnung                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **Incident-Recovery**           | `docs/observability_incident_recovery.md`                                                    | Kill-Switch, Latch, Flatten, Stale, Gateway, Drift, Billing                                                                                                                                                                                                                                                                                                                                                                                   |
| **Alertregeln**                 | `infra/observability/prometheus-alerts.yml`                                                  | Regeln mit Annotation **`runbook`** → `docs/monitoring_runbook.md#...`                                                                                                                                                                                                                                                                                                                                                                        |
| **Runbooks**                    | `docs/monitoring_runbook.md`                                                                 | Anker pro Alert-Typ, Troubleshooting                                                                                                                                                                                                                                                                                                                                                                                                          |

## Ueberblick

- Jeder Python-Service mit `shared_py.observability.instrument_fastapi` exportiert **`/metrics`** (HTTP-Zaehler, Latenz-Histogramm, Heartbeat pro Request). Zusaetzlich setzen langlebige Worker/Schedulers `touch_worker_heartbeat(...)` in ihren Schleifen, damit Prometheus `time() - worker_heartbeat_timestamp` Stalls erkennt.
- Die **monitor-engine** ergaenzt zentrale **Gauges** (Redis-Stream-Lag, Datenfrische, Online-Drift, Shadow/Live-Gate, Live-Reconcile, Kill-Switch, Trading-SQL-Aggregate, Signal-Durchsatz, offene Orders/Positionen, Risk-Blocks, Shadow-Assessment-Mismatch, Exit-Fehler, kritische Audits).
- **Prometheus** (Compose-Profil `observability`) scraped alle Dienste gemaess `infra/observability/prometheus.yml`.
- **Alertregeln** liegen in `infra/observability/prometheus-alerts.yml` (u. a. Drift, Kill-Switch, Staleness, Reconcile, Queue, Order-Fail/Exit, Safety-Latch, Signal-Stall, Alert-Backlog); jede Regel verweist auf ein Runbook.
- **Grafana** (Port **3001** am Host) laedt Datasource + Dashboard per Provisioning aus `infra/observability/grafana/`.

**Architektur-Referenz:** `docs/adr/ADR-0001-bitget-market-universe-platform.md`

Im Zielbild muss Observability nicht nur service-zentriert, sondern auch
instrument- und family-aware sein. Wichtige fachliche Dimensionsfelder bleiben:

- `market_family`
- `instrument_key`
- `symbol`
- `decision_trace_id`
- `specialist_id` bzw. Router-/Playbook-Kontext, wo vorhanden
- `catalog_snapshot_id`
- `instrument_metadata_health`

## Start (Compose)

```bash
COMPOSE_ENV_FILE=.env.local docker compose --profile observability up -d prometheus grafana
```

Oder vollstaendiger Stack mit `WITH_OBSERVABILITY=true bash scripts/start_local.sh` (siehe `docs/Deploy.md`).

- Prometheus UI: `http://localhost:9090`
- Grafana: `http://localhost:3001` (Login `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`, Defaults siehe `docker-compose.yml`)

## Wichtige Metriken (monitor-engine)

| Metrik                                                           | Bedeutung                                                                      |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `live_reconcile_age_ms`                                          | Alter des letzten Reconcile-Snapshots                                          |
| `live_kill_switch_active_count`                                  | Aktive Kill-Switches                                                           |
| `live_reconcile_drift_total`                                     | Drift-Zaehler aus Reconcile                                                    |
| `data_freshness_seconds{datapoint=...}`                          | Staleness Kerzen/Signale/News/...                                              |
| `instrument_catalog` / `instrument_metadata` im Service-Health   | degradiert bei stale, unvollstaendigen oder inkonsistenten Instrumentmetadaten |
| `redis_stream_lag{stream,group}`                                 | Consumer-Lag / Heuristik                                                       |
| `online_drift_action_rank`                                       | Online-Drift-Stufe (numerisch)                                                 |
| `shadow_live_gate_blocks_24h` / `shadow_live_match_failures_24h` | Shadow-Live-Gate                                                               |
| `live_order_fail_rate_1h`                                        | Fehler-Terminal-Orders / alle Orders (1h)                                      |
| `live_fill_slippage_bps_avg_24h`                                 | Mittlere Slippage Limit-Fills                                                  |
| `live_order_roundtrip_p90_seconds`                               | P90 Order-Lebensdauer (filled)                                                 |
| `learn_drift_events_24h`                                         | Drift-Events Learning                                                          |
| `signal_pipeline_rejected_ratio_24h`                             | Anteil `decision_state=rejected`                                               |
| `alert_outbox_pending` / `monitor_open_alerts`                   | Alert-Backlog                                                                  |
| `signal_pipeline_throughput_1h`                                  | Signale erzeugt (letzte Stunde)                                                |
| `execution_decisions_blocked_24h`                                | Risk-/Gate-Blocks (`decision_action=blocked`)                                  |
| `live_orders_open`                                               | Nicht-terminale `live.orders`                                                  |
| `paper_positions_open`                                           | Offene Paper-Positionen                                                        |
| `live_order_exit_failures_1h`                                    | `error` / `flatten_failed` (1h)                                                |
| `shadow_live_assessment_mismatch_24h`                            | `shadow_live_assessments.match_ok=false`                                       |
| `live_critical_audits_24h`                                       | Kritische Audits im Monitor-Lookback                                           |
| `live_safety_latch_active`                                       | Safety-Latch (bereits vorher; jetzt mit Alert)                                 |
| `monitor_engine_tick_duration_seconds`                           | Histogram: Dauer eines Monitor-Ticks                                           |
| `signal_pipeline_lag_p95_seconds_1h`                             | P95 Feature `computed_ts` → `analysis_ts` (1h)                                 |
| `gateway_manual_action_auth_failures_1h`                         | Manual-Action / Live-Mutation Auth-Fails                                       |
| `execution_drift_or_shadow_decisions_24h`                        | Decisions mit drift/shadow_online im `decision_reason`                         |
| `commerce_ledger_lines_1h` / `commerce_billing_auth_failures_1h` | Metering & Billing-Auth (wenn Tabellen aktiv)                                  |

## Prometheus-Alerts → Zustellung

Die Regeln erzeugen Prometheus-Alerts (`ALERTS` Time-Serie). Fuer Produktion **Alertmanager** konfigurieren (Webhook, PagerDuty, Telegram-Bot-Webhook, etc.). Parallel feuert die **monitor-engine** weiterhin **ops.alerts** + `events:system_alert` fuer das integrierte Alert-Engine-Telegram.

## Strukturierte Logs

`LOG_FORMAT=json` (siehe `Deploy.md`) fuer zentrale Sammlung; keine Secrets in Log-Feldern.

Fuer Korrelation ueber Services hinweg: bei Log-Ausgaben `extra=log_correlation_fields(signal_id=..., execution_id=..., ...)` nutzen. Feldnamen beginnen mit `corr_`, damit sie nicht mit LogRecord-Standardfeldern kollidieren.

### PII und sensible Daten (Gateway & allgemein)

- **Nicht loggen:** `Authorization`-Header, komplette JWTs, API-Keys, Passwoerter, Stripe-Secrets, Rohtext von Zahlungsdaten.
- **Vorsicht:** E-Mail-Adressen und reale Namen nur wenn fachlich noetig und Policy-konform; lieber IDs (`tenant_id`, `gateway_audit_id`) und bereits redigierte Felder (`api_gateway.audit` nutzt `redact_nested_mapping` fuer `detail_json`).
- **Support:** Kunden/User sollen `X-Request-ID` (und ggf. `X-Correlation-ID`) aus der Browser-Network-Antwort mitliefern — Zuordnung zu Gateway-Logs ohne PII-Pflicht.

## Gateway: Metrik-Liste (Muster api-gateway)

| Metrik                                        | Labels                                            | Bedeutung                                                 |
| --------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------- |
| `gateway_live_broker_forward_total`           | `result` = `success` / `http_error` / `url_error` | Kritische POST-Forwards zum live-broker (Safety/Operator) |
| `gateway_live_broker_forward_latency_seconds` | —                                                 | Histogramm Latenz dieser Forwards                         |
| `gateway_auth_failures_total`                 | `action` (gekuerzt)                               | Fehlgeschlagene Auth am Gateway (Audit-Pfad)              |

Ergänzend gelten die generischen FastAPI-Metriken aus `shared_py.observability.metrics` (`http_requests_total`, `http_request_latency_seconds`, …) fuer alle Routen inkl. Gateway.
